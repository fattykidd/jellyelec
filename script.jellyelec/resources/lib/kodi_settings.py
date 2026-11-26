"""Reading and changing Kodi's own settings (sound, display, CoreELEC) through JSON-RPC.

CoreELEC forks don't agree on the numbers behind each choice: "Off" might be 0 on one
build and 5 on another. So instead of hard-coding numbers, JellyELEC asks the running
build for a setting's choices and picks one by its label, the words shown on screen.
"""

import xbmc

from resources.lib import jsonrpc
from resources.lib.kodi import log


class KodiSettingError(Exception):
    """Kodi refused to read or change a setting."""


def get_value(setting_id):
    """The current value of a Kodi setting."""
    return _call("Settings.GetSettingValue", setting=setting_id)["value"]


def set_value(setting_id, value):
    """Change a Kodi setting. Raises KodiSettingError if Kodi refuses."""
    global _cached_settings
    _call("Settings.SetSettingValue", setting=setting_id, value=value)
    # One setting's choices can depend on another (time zones on the country), so the
    # list of settings is fetched again next time.
    _cached_settings = None
    log(f"Kodi setting {setting_id} set to {value!r}.")


def choices(setting_id):
    """A setting's choices as a list of (value, label), or [] if it has none or doesn't exist."""
    for setting in _all_settings():
        if setting.get("id") == setting_id:
            return [(option["value"], option["label"]) for option in setting.get("options", [])]
    return []


def set_by_label(setting_id, *wanted_labels, exact=False):
    """Pick the first choice whose label contains one of wanted_labels (ignoring case).

    With exact=True the whole label must match, so "Off" doesn't also match "Dolby Vision Off".
    Returns True if the setting was changed or already right, False if no choice matched.
    """
    options = choices(setting_id)
    for wanted in wanted_labels:
        for value, label in options:
            if _label_matches(label, wanted, exact):
                if get_value(setting_id) != value:
                    set_value(setting_id, value)
                return True
    shown = ", ".join(f"{value}={label}" for value, label in options) or "none"
    log(f"Kodi setting {setting_id}: no choice matching {wanted_labels}; choices are {shown}.", xbmc.LOGWARNING)
    return False


# Helpers ----------------------------------------------------------------------------

_cached_settings = None


def _label_matches(label, wanted, exact):
    label, wanted = label.strip().lower(), wanted.lower()
    return label == wanted if exact else wanted in label


def _all_settings():
    """Every setting Kodi has, at the Expert level so CoreELEC's are included. Fetched once."""
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = _call("Settings.GetSettings", level="expert").get("settings", [])
    return _cached_settings


def _call(method, **params):
    try:
        return jsonrpc.call(method, **params)
    except jsonrpc.JsonRpcError as error:
        raise KodiSettingError(f"{error} {params.get('setting', '')}".strip()) from error
