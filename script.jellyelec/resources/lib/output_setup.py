"""Setting up sound and picture for how the box is connected: TV, AV receiver, or video processor."""

import os

import xbmc
import xbmcaddon

from resources.lib import kodi_settings
from resources.lib.kodi import log

# The three answers to "How is this box connected?", in the order they're offered.
TV = "tv"
RECEIVER = "receiver"
VIDEO_PROCESSOR = "video_processor"
CONNECTIONS = (
    (TV, "Straight to the TV"),
    (RECEIVER, "Through an AV receiver"),
    (VIDEO_PROCESSOR, "Through an AV receiver and a video processor"),
)

# Add-on setting that remembers the answer.
CONNECTION_SETTING = "box_connection"

# CoreELEC loads the Dolby Vision module from the boot partition at startup.
DOVI_MODULE_PATH = "/flash/dovi.ko"

# Shown when video processor mode is chosen but the display chain isn't offering LLDV.
LLDV_WAITING_MESSAGE = (
    "Your display chain isn't offering LLDV right now, so the Dolby Vision type was left as "
    "it is. Everything else is set up.[CR][CR]"
    "JellyELEC will switch to LLDV by itself the first time it starts with the video "
    "processor connected and offering LLDV."
)

# How to add dovi.ko, shown during setup and in Settings.
DOVI_INSTRUCTIONS = (
    "JellyELEC can't include the Dolby Vision module (dovi.ko), so it's added by hand:[CR][CR]"
    "1.  Shut down this box and put its card or USB stick in a computer.[CR]"
    "2.  Copy dovi.ko onto the drive named COREELEC (into the top folder, not a subfolder).[CR]"
    "3.  Put the card back and turn the box on.[CR][CR]"
    "Without it, Dolby Vision titles play in HDR10 instead."
)

# Add-on setting: video processor mode was chosen, but its Dolby Vision settings are still to
# be made. CoreELEC hides those settings until dovi.ko is installed, so they can wait.
DOLBY_VISION_PENDING_SETTING = "dolby_vision_pending"

# Passthrough has to go out of the HDMI port: the S/PDIF device that's often chosen by default
# can't carry E-AC-3, TrueHD or DTS-HD, so Kodi hides those switches. This is the Amlogic HDMI
# device's ID, used if Kodi doesn't list its devices.
HDMI_PASSTHROUGH_DEVICE = "ALSA:hdmi:CARD=AMLAUGESOUND,DEV=0|AML-AUGESOUND"

PASSTHROUGH_FORMATS = (
    "audiooutput.ac3passthrough",
    "audiooutput.eac3passthrough",
    "audiooutput.dtspassthrough",
    "audiooutput.truehdpassthrough",
    "audiooutput.dtshdpassthrough",
)

# Kodi's speaker layouts, numbered 1 (2.0) to 10 (7.1).
SPEAKERS_7_1 = 10

DOLBY_VISION_TYPE = "coreelec.amlogic.dolbyvision.type"
VS10_SETTINGS = (
    "coreelec.amlogic.dolbyvision.vs10.sdr8",
    "coreelec.amlogic.dolbyvision.vs10.sdr10",
    "coreelec.amlogic.dolbyvision.vs10.hdr10",
    "coreelec.amlogic.dolbyvision.vs10.hdr10plus",
    "coreelec.amlogic.dolbyvision.vs10.hdrhlg",
    "coreelec.amlogic.dolbyvision.vs10.dv",
)


def dolby_vision_ready():
    """True if dovi.ko has been copied to the boot partition."""
    return os.path.isfile(DOVI_MODULE_PATH)


def dolby_vision_pending():
    """True if video processor mode's Dolby Vision settings are still to be made."""
    return xbmcaddon.Addon().getSettingBool(DOLBY_VISION_PENDING_SETTING)


def current_connection():
    """The saved answer (TV, RECEIVER or VIDEO_PROCESSOR), or "" if setup hasn't asked yet."""
    return xbmcaddon.Addon().getSetting(CONNECTION_SETTING)


def connection_name(connection_type):
    return dict(CONNECTIONS).get(connection_type, "Not set")


def apply_connection(connection_type):
    """Change Kodi's settings to suit the connection, and remember it. Returns True if every change worked."""
    log(f"Setting up output for: {connection_type}")
    xbmcaddon.Addon().setSetting(CONNECTION_SETTING, connection_type)
    worked = _set_passthrough(connection_type != TV)

    _set_dolby_vision_pending(connection_type == VIDEO_PROCESSOR)
    if connection_type == VIDEO_PROCESSOR:
        worked = apply_pending_dolby_vision() and worked
    return worked


def apply_pending_dolby_vision():
    """Make video processor mode's Dolby Vision settings, if they're waiting and dovi.ko is in.

    Called during setup and at every start. CoreELEC only offers LLDV when the display chain
    says it accepts it, so the settings stay waiting until a start where LLDV is offered.
    Returns False only if Kodi refused a change.
    """
    if not dolby_vision_pending():
        return True
    if not dolby_vision_ready():
        log("Video processor mode: Dolby Vision settings will be made once dovi.ko is installed.")
        return True

    _log_dolby_vision_choices()
    # The type goes first: it decides which VS10 settings CoreELEC shows.
    lldv_offered = kodi_settings.has_choice(DOLBY_VISION_TYPE, "LLDV")
    if lldv_offered:
        worked = _try(kodi_settings.set_by_label, DOLBY_VISION_TYPE, "LLDV")
    else:
        log("Video processor mode: LLDV isn't offered by this display chain yet, so the "
            "Dolby Vision type is left as it is until a start where it is.")
        worked = True

    for setting_id in VS10_SETTINGS:
        # CoreELEC hides a format's VS10 setting when it doesn't apply.
        if not kodi_settings.choices(setting_id):
            log(f"{setting_id} isn't offered here, so it's skipped.")
            continue
        worked = _try(kodi_settings.set_by_label, setting_id, "Off", exact=True) and worked

    if lldv_offered and worked:
        _set_dolby_vision_pending(False)
        log("Video processor mode: Dolby Vision set to LLDV with VS10 off.")
    return worked


def waiting_for_lldv():
    """True if dovi.ko is in but video processor mode's LLDV setting is still to be made."""
    return dolby_vision_ready() and dolby_vision_pending()


# Sound ------------------------------------------------------------------------------------

def _set_passthrough(enabled):
    """A receiver decodes the audio itself; a TV gets plain sound from Kodi."""
    worked = _try(kodi_settings.set_value, "audiooutput.passthrough", enabled)
    if not enabled:
        return worked

    worked = _try(kodi_settings.set_value, "audiooutput.passthroughdevice", _hdmi_passthrough_device()) and worked
    worked = _try(kodi_settings.set_value, "audiooutput.channels", SPEAKERS_7_1) and worked
    # One at a time, so a format this build doesn't offer doesn't stop the others.
    for setting_id in PASSTHROUGH_FORMATS:
        worked = _try(kodi_settings.set_value, setting_id, True) and worked
    return worked


def _hdmi_passthrough_device():
    """The HDMI device from Kodi's list of passthrough devices."""
    try:
        devices = kodi_settings.choices("audiooutput.passthroughdevice")
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't list passthrough devices: {error}", xbmc.LOGWARNING)
        devices = []
    for value, label in devices:
        if ":hdmi:" in str(value):
            log(f"Passthrough device: {label}")
            return value
    return HDMI_PASSTHROUGH_DEVICE


# Helpers ----------------------------------------------------------------------------------

def _try(change, *args, **kwargs):
    """Run one settings change. Returns False, and logs why, if Kodi refused it."""
    try:
        result = change(*args, **kwargs)
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't change a setting: {error}", xbmc.LOGWARNING)
        return False
    return result is not False


def _set_dolby_vision_pending(pending):
    xbmcaddon.Addon().setSettingBool(DOLBY_VISION_PENDING_SETTING, pending)


def _log_dolby_vision_choices():
    """Write this build's Dolby Vision choices to the log, to help when a fork labels them differently."""
    for setting_id in (DOLBY_VISION_TYPE, *VS10_SETTINGS):
        try:
            options = kodi_settings.choices(setting_id)
        except kodi_settings.KodiSettingError:
            options = []
        shown = ", ".join(f"{value}={label}" for value, label in options) or "not available"
        log(f"{setting_id}: {shown}")
