"""The box's network name: what file managers, routers and other devices on the network see.

CoreELEC keeps it in a file and applies it when its network service starts. Changing it
here works the same way as in CoreELEC's own settings add-on (resources/lib/hostname.py in
service.coreelec.settings): write the file, then restart the services that announce it.

JellyELEC also remembers the name it set, because a system update can put CoreELEC's name
back (p3i T5 did). Each start, wanted_name() is compared with the box's name, and JellyELEC
puts its own back if they differ.

CoreELEC's settings add-on keeps a copy of the name too, in its own settings file, and writes
it to the box at every start (from p3i T5 on). Without one saved, it writes "CoreELEC". So the
name is saved there as well, or the two would race at each boot.
"""

import os
import subprocess
import xml.etree.ElementTree as ElementTree

from resources.lib.kodi import PROFILE_PATH, log

HOSTNAME_FILE = "/storage/.cache/hostname"
# CoreELEC's settings add-on's own settings; the name is <settings><system><hostname>.
SETTINGS_ADDON_FILE = "/storage/.kodi/userdata/addon_data/service.coreelec.settings/oe_settings.xml"

# The name JellyELEC last gave the box.
WANTED_NAME_FILE = os.path.join(PROFILE_PATH, "box_name")
JELLYELEC_NAME = "JellyELEC"
# The name CoreELEC gives a new box.
COREELEC_NAME = "CoreELEC"


def current_name():
    try:
        with open(HOSTNAME_FILE, encoding="utf-8") as file:
            return file.read().strip()
    except OSError:
        return ""


def wanted_name():
    """The name JellyELEC last gave the box, or "" if it hasn't named it."""
    try:
        with open(WANTED_NAME_FILE, encoding="utf-8") as file:
            return file.read().strip()
    except OSError:
        return ""


def set_name(name):
    """Rename the box, and announce the new name on the network straight away."""
    try:
        with open(HOSTNAME_FILE, "w", encoding="utf-8") as file:
            file.write(f"{name}\n")
        os.makedirs(PROFILE_PATH, exist_ok=True)
        with open(WANTED_NAME_FILE, "w", encoding="utf-8") as file:
            file.write(f"{name}\n")
    except OSError as error:
        log(f"Couldn't save the box name: {error}")
        return
    save_in_settings_addon(name)
    for command in (
        ["systemctl", "restart", "network-base"],
        # Samba's settings file is written with the box name when it starts, so it's written
        # again, then file sharing restarts if it's on. wsdd2 goes last: it reads its name
        # from those settings.
        ["systemctl", "try-restart", "samba-config"],
        ["systemctl", "try-restart", "nmbd", "smbd"],
        ["systemctl", "try-restart", "avahi-daemon", "wsdd2"],
    ):
        subprocess.run(command, check=False, capture_output=True)
    log(f"Box name set to {name}.")


def settings_addon_name():
    """The name saved in CoreELEC's settings add-on, or "" if it has none (or no file)."""
    try:
        root = ElementTree.parse(SETTINGS_ADDON_FILE).getroot()
    except (OSError, ElementTree.ParseError):
        return ""
    return (root.findtext("settings/system/hostname") or "").strip()


def save_in_settings_addon(name):
    """Save the name in CoreELEC's settings add-on too, so it applies this name at start."""
    try:
        tree = ElementTree.parse(SETTINGS_ADDON_FILE)
    except (OSError, ElementTree.ParseError) as error:
        log(f"Couldn't read CoreELEC's settings to save the box name there: {error}")
        return
    root = tree.getroot()
    settings = root.find("settings")
    if settings is None:
        settings = ElementTree.SubElement(root, "settings")
    system = settings.find("system")
    if system is None:
        system = ElementTree.SubElement(settings, "system")
    hostname = system.find("hostname")
    if hostname is None:
        hostname = ElementTree.SubElement(system, "hostname")
    hostname.text = name
    try:
        tree.write(SETTINGS_ADDON_FILE, encoding="utf-8", xml_declaration=True)
    except OSError as error:
        log(f"Couldn't save the box name in CoreELEC's settings: {error}")


def name_new_box():
    """Give a box still using CoreELEC's name the JellyELEC name. A name chosen by hand stays."""
    if current_name() in ("", COREELEC_NAME):
        set_name(JELLYELEC_NAME)
