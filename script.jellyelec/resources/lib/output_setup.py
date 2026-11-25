"""Setting up sound and picture for how the box is connected: TV, AV receiver, or video processor."""

import os

import xbmc

from resources.lib import kodi_settings
from resources.lib.kodi import log

# The three answers to "How is this box connected?"
TV = "tv"
RECEIVER = "receiver"
VIDEO_PROCESSOR = "video_processor"

# CoreELEC loads the Dolby Vision module from the boot partition at startup.
DOVI_MODULE_PATH = "/flash/dovi.ko"

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


def apply_connection(connection_type):
    """Change Kodi's settings to suit the connection. Returns True if every change worked."""
    log(f"Setting up output for: {connection_type}")
    steps = [_log_dolby_vision_choices, lambda: _set_passthrough(connection_type != TV)]
    if connection_type == VIDEO_PROCESSOR:
        steps.append(_set_video_processor_mode)

    all_worked = True
    for step in steps:
        try:
            all_worked = step() and all_worked
        except kodi_settings.KodiSettingError as error:
            log(f"Couldn't change a setting: {error}", xbmc.LOGWARNING)
            all_worked = False
    return all_worked


# Sound ------------------------------------------------------------------------------------

def _set_passthrough(enabled):
    """A receiver decodes the audio itself; a TV gets plain sound from Kodi."""
    kodi_settings.set_value("audiooutput.passthrough", enabled)
    if enabled:
        kodi_settings.set_value("audiooutput.channels", SPEAKERS_7_1)
        for setting_id in PASSTHROUGH_FORMATS:
            kodi_settings.set_value(setting_id, True)
    return True


# Picture ----------------------------------------------------------------------------------

def _set_video_processor_mode():
    """Dolby Vision as LLDV, and VS10 off for everything: the processor does the tone mapping."""
    worked = kodi_settings.set_by_label(DOLBY_VISION_TYPE, "LLDV", "Player Led")
    for setting_id in VS10_SETTINGS:
        worked = kodi_settings.set_by_label(setting_id, "Off", exact=True) and worked
    return worked


def _log_dolby_vision_choices():
    """Write this build's Dolby Vision choices to the log, to help when a fork labels them differently."""
    for setting_id in (DOLBY_VISION_TYPE, *VS10_SETTINGS):
        options = kodi_settings.choices(setting_id)
        shown = ", ".join(f"{value}={label}" for value, label in options) or "not available"
        log(f"{setting_id}: {shown}")
    return True
