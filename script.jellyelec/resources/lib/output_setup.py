"""Setting up sound and picture for how the box is connected: TV, AV receiver, or video processor."""

import os

import xbmc
import xbmcaddon

from resources.lib import build_info, kodi_settings
from resources.lib.kodi import PROFILE_PATH, log

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

# Shown when video processor mode is chosen but the display chain isn't offering LLDV.
LLDV_WAITING_MESSAGE = (
    "Your display chain isn't offering LLDV right now, so the Dolby Vision type was left as "
    "it is. Everything else is set up.[CR][CR]"
    "JellyELEC will switch to LLDV by itself the first time it starts with the video "
    "processor connected and offering LLDV."
)



def dovi_instructions():
    """How to add the Dolby Vision module, shown during setup and in Settings."""
    module = build_info.dovi_module()
    return (
        f"JellyELEC can't include the Dolby Vision module ({module}), so it's added by hand:[CR][CR]"
        "1.  Shut down this box and put its card or USB stick in a computer.[CR]"
        f"2.  Copy {module} onto the drive named COREELEC (into the top folder, not a subfolder).[CR]"
        "3.  Put the card back and turn the box on.[CR][CR]"
        "Without it, Dolby Vision titles play in HDR10 instead."
    )


# Add-on setting: video processor mode was chosen, but its Dolby Vision settings are still to
# be made. CoreELEC hides those settings until dovi.ko is installed, so they can wait.
DOLBY_VISION_PENDING_SETTING = "dolby_vision_pending"

# Passthrough has to go out of the HDMI port: the S/PDIF device that's often chosen by default
# can't carry E-AC-3, TrueHD or DTS-HD, so Kodi hides those switches. This is the Amlogic HDMI
# device's ID, used for both devices if Kodi doesn't list them.
HDMI_PASSTHROUGH_DEVICE = "ALSA:hdmi:CARD=AMLAUGESOUND,DEV=0|AML-AUGESOUND"
HDMI_AUDIO_DEVICE = HDMI_PASSTHROUGH_DEVICE

PASSTHROUGH_FORMATS = (
    "audiooutput.ac3passthrough",
    "audiooutput.eac3passthrough",
    "audiooutput.dtspassthrough",
    "audiooutput.truehdpassthrough",
    "audiooutput.dtshdpassthrough",
)

# Kodi's speaker layouts, numbered 1 (2.0) to 10 (7.1).
SPEAKERS_7_1 = 10

DOLBY_VISION_PREFIX = "coreelec.amlogic.dolbyvision."
DOLBY_VISION_TYPE = "coreelec.amlogic.dolbyvision.type"

# p3i T5 and later: "VP mode", made for external video processors. The box still decodes
# Dolby Vision (FEL included) but skips the Dolby library's tone mapping, and sends the result
# as HDR10 with the title's real brightness information; the processor does all the tone
# mapping. Found by label, as pannal chose the IDs. 4:2:2 is what capture cards take natively.
VP_OUTPUT_LABEL = "Output Signal Type for Video Processor"
VP_OUTPUT_CHOICE = "HDR10 422"
DV_MODE_LABEL = "DV Mode"
DV_MODE_CHOICE = "On Demand"

# Marks a box whose video processor setup has been redone for VP mode (see upgrade_to_vp_mode).
VP_MODE_MARKER = os.path.join(PROFILE_PATH, "dolby_vision_vp_mode")
# How forks label the LLDV (low-latency Dolby Vision) type: "Player Led (LLDV)" on CoreELEC,
# "Player Led (DV as DV-LL 422 12 Bit)" on p3i.
LLDV_LABELS = ("LLDV", "DV-LL")
VS10_SETTINGS = (
    "coreelec.amlogic.dolbyvision.vs10.sdr8",
    "coreelec.amlogic.dolbyvision.vs10.sdr10",
    "coreelec.amlogic.dolbyvision.vs10.hdr10",
    "coreelec.amlogic.dolbyvision.vs10.hdr10plus",
    "coreelec.amlogic.dolbyvision.vs10.hdrhlg",
    "coreelec.amlogic.dolbyvision.vs10.dv",
)


def dolby_vision_ready():
    """True if the Dolby Vision module has been copied to the boot partition."""
    return os.path.isfile(build_info.dovi_module_path())


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
    if kodi_settings.find_id(VP_OUTPUT_LABEL, DOLBY_VISION_PREFIX):
        return _apply_vp_mode()

    # Before p3i T5: LLDV, where the box tone maps to the display chain's brightness.
    # The type goes first: it decides which VS10 settings CoreELEC shows.
    lldv_offered = any(kodi_settings.has_choice(DOLBY_VISION_TYPE, label) for label in LLDV_LABELS)
    if lldv_offered:
        worked = _try(kodi_settings.set_by_label, DOLBY_VISION_TYPE, *LLDV_LABELS)
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


def _apply_vp_mode():
    """Video processor mode on p3i T5 and later: DV Mode On Demand, VP output as HDR10 4:2:2,
    VS10 off. Returns False if Kodi refused a change."""
    vp_setting = kodi_settings.find_id(VP_OUTPUT_LABEL, DOLBY_VISION_PREFIX)
    mode_setting = kodi_settings.find_id(DV_MODE_LABEL, DOLBY_VISION_PREFIX, exact=True)
    worked = True
    if mode_setting:
        worked = _try(kodi_settings.set_by_label, mode_setting, DV_MODE_CHOICE)
    # The VP output goes before VS10: it decides which VS10 settings CoreELEC shows.
    worked = _try(kodi_settings.set_by_label, vp_setting, VP_OUTPUT_CHOICE) and worked
    for setting_id in VS10_SETTINGS:
        if not kodi_settings.choices(setting_id):
            continue
        worked = _try(kodi_settings.set_by_label, setting_id, "Off", exact=True) and worked
    if worked:
        _set_dolby_vision_pending(False)
        log(f"Video processor mode: Dolby Vision passed to the processor untouched "
            f"({vp_setting} set to {VP_OUTPUT_CHOICE}), VS10 off.")
    return worked


def upgrade_to_vp_mode():
    """Once per box: in video processor mode, set the Dolby Vision settings to be made again,
    so a box set up before VP mode existed (or before this version) moves to it."""
    if os.path.exists(VP_MODE_MARKER):
        return
    if current_connection() == VIDEO_PROCESSOR:
        log("Video processor mode: making the Dolby Vision settings again, for VP mode.")
        _set_dolby_vision_pending(True)
    os.makedirs(PROFILE_PATH, exist_ok=True)
    with open(VP_MODE_MARKER, "w", encoding="utf-8") as file:
        file.write("1\n")


def waiting_for_lldv():
    """True if dovi.ko is in but video processor mode's LLDV setting is still to be made."""
    return dolby_vision_ready() and dolby_vision_pending()


# Sound ------------------------------------------------------------------------------------

def _set_passthrough(enabled):
    """A receiver decodes the audio itself; a TV gets plain sound from Kodi."""
    worked = _try(kodi_settings.set_value, "audiooutput.passthrough", enabled)
    if not enabled:
        return worked

    # Both devices on HDMI: sound that isn't bitstreamed, such as menus and PCM tracks, then
    # takes the same path as bitstreamed audio, instead of p3i's default "HDMI Multi Ch PCM".
    worked = _try(kodi_settings.set_value, "audiooutput.audiodevice",
                  _hdmi_device("audiooutput.audiodevice", HDMI_AUDIO_DEVICE)) and worked
    worked = _try(kodi_settings.set_value, "audiooutput.passthroughdevice",
                  _hdmi_device("audiooutput.passthroughdevice", HDMI_PASSTHROUGH_DEVICE)) and worked
    worked = _try(kodi_settings.set_value, "audiooutput.channels", SPEAKERS_7_1) and worked
    # One at a time, so a format this build doesn't offer doesn't stop the others.
    for setting_id in PASSTHROUGH_FORMATS:
        worked = _try(kodi_settings.set_value, setting_id, True) and worked
    return worked


def _hdmi_device(setting_id, fallback):
    """The plain HDMI device from the setting's list of devices (not "HDMI Multi Ch PCM")."""
    try:
        devices = kodi_settings.choices(setting_id)
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't list the devices for {setting_id}: {error}", xbmc.LOGWARNING)
        devices = []
    for value, label in devices:
        if ":hdmi:" in str(value):
            log(f"{setting_id}: {label}")
            return value
    return fallback


# Helpers ----------------------------------------------------------------------------------

def _try(change, *args, **kwargs):
    """Run one settings change. Returns False, and logs why, if Kodi refused it."""
    try:
        result = change(*args, **kwargs)
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't change a setting: {error}", xbmc.LOGWARNING)
        return False
    return result is not False


def redo_dolby_vision_settings():
    """After CoreELEC's settings were reset: in video processor mode, make the Dolby Vision
    settings again at the next start, as if setup had just chosen it."""
    if current_connection() == VIDEO_PROCESSOR:
        _set_dolby_vision_pending(True)
        log("Video processor mode: Dolby Vision settings will be made again.")


def _set_dolby_vision_pending(pending):
    xbmcaddon.Addon().setSettingBool(DOLBY_VISION_PENDING_SETTING, pending)


def _log_dolby_vision_choices():
    """Write this build's Dolby Vision settings and their choices to the log, to help when a
    fork adds settings or labels them differently."""
    for setting in kodi_settings.settings_with_prefix(DOLBY_VISION_PREFIX):
        options = setting.get("options") or []
        shown = ", ".join(f"{option['value']}={option['label']}" for option in options) or "no choices"
        log(f"{setting['id']} ({setting.get('label', '')}): {shown}")