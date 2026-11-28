"""Keeping JellyELEC's startup screen, player screens and fonts in the skin Kodi actually uses.

JellyELEC images patch the skins built into the system: the startup screen shows JellyELEC's
splash instead of Kodi's home screen, the full-screen video window, OSD and seek bar are
JellyELEC's (with the textures they use), and JellyELEC's fonts are added. But a skin can also be
installed or updated into Kodi's own add-on folder (/storage/.kodi/addons), and Kodi then uses
that copy instead, without the patches, so Kodi's home screen flashes up at boot again.

So at each start, JellyELEC checks the active skin: if it's a copy in Kodi's add-on folder
(which can be written to, unlike the system), it gets the same patches remaster.sh makes. They
take effect from the next time Kodi starts. The files come from resources/skin_patch/, the
same ones remaster.sh uses.
"""

import os
import re
import shutil

import xbmcvfs

from resources.lib import kodi_settings
from resources.lib.kodi import ADDON_PATH, log

PATCH_DIR = os.path.join(ADDON_PATH, "resources", "skin_patch")
MEDIA_DIR = os.path.join(ADDON_PATH, "resources", "skins", "Default", "media")
# The skin's own screens that JellyELEC replaces, from PATCH_DIR.
SKIN_WINDOWS = ("Startup.xml", "VideoFullScreen.xml", "VideoOSD.xml", "DialogSeekBar.xml")
# Textures those screens use, from MEDIA_DIR: the OSD's icons, and these.
SKIN_TEXTURES = ("jellyelec-pill.png", "jellyelec-white.png", "jellyelec-fade-bottom.png",
                 "jellyelec-badge-filled.png")
OSD_ICON_PREFIX = "jellyelec-osd-"
FONT_DEFINITIONS = os.path.join(PATCH_DIR, "jellyelec-fonts.xml")
FONTS_DIR = os.path.join(PATCH_DIR, "fonts")
FONT_FILE_ENDINGS = (".ttf", ".otf")

# Marks Font.xml as already having JellyELEC's fonts.
FONTS_MARKER = "<name>JE_Title</name>"


def patch_active_skin():
    """Patch the active skin if it's a copy in Kodi's add-on folder. Returns True if anything
    changed (it shows from the next start)."""
    try:
        skin_id = kodi_settings.get_value("lookandfeel.skin")
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't tell which skin is in use: {error}")
        return False
    skin_dir = xbmcvfs.translatePath(f"special://home/addons/{skin_id}")
    if not os.path.isdir(os.path.join(skin_dir, "xml")):
        return False  # the system's own copy, patched when the image was made

    changed = _patch_windows(skin_dir)
    changed = _patch_fonts(skin_dir) or changed
    if changed:
        log(f"Patched {skin_id} in Kodi's add-on folder (startup screen, player screens, fonts); "
            "it takes effect from the next start.")
    return changed


def _patch_windows(skin_dir):
    """Copy in JellyELEC's screens, and the textures they use, where they differ."""
    changed = False
    for name in SKIN_WINDOWS:
        changed = _copy_if_changed(os.path.join(PATCH_DIR, name), os.path.join(skin_dir, "xml", name)) or changed
    textures = list(SKIN_TEXTURES) + [name for name in os.listdir(MEDIA_DIR) if name.startswith(OSD_ICON_PREFIX)]
    media = os.path.join(skin_dir, "media")
    os.makedirs(media, exist_ok=True)
    for name in textures:
        changed = _copy_if_changed(os.path.join(MEDIA_DIR, name), os.path.join(media, name)) or changed
    return changed


def _copy_if_changed(source, target):
    if _same_contents(source, target):
        return False
    shutil.copyfile(source, target)
    return True


def _patch_fonts(skin_dir):
    changed = False
    fonts_dir = os.path.join(skin_dir, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    for name in os.listdir(FONTS_DIR):
        if name.endswith(FONT_FILE_ENDINGS) and not os.path.exists(os.path.join(fonts_dir, name)):
            shutil.copyfile(os.path.join(FONTS_DIR, name), os.path.join(fonts_dir, name))
            changed = True

    font_xml = os.path.join(skin_dir, "xml", "Font.xml")
    with open(font_xml, encoding="utf-8") as file:
        text = file.read()
    if FONTS_MARKER not in text:
        with open(FONT_DEFINITIONS, encoding="utf-8") as file:
            fonts = re.sub(r"<!--.*?-->", "", file.read(), flags=re.S).strip()
        # The same change remaster.sh makes: JellyELEC's fonts in every fontset.
        with open(font_xml, "w", encoding="utf-8") as file:
            file.write(text.replace("</fontset>", f"{fonts}\n</fontset>"))
        changed = True
    return changed


def _same_contents(path_a, path_b):
    try:
        with open(path_a, "rb") as a, open(path_b, "rb") as b:
            return a.read() == b.read()
    except OSError:
        return False
