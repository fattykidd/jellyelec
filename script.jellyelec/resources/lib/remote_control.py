"""Remote control from other devices, as the Unfolded Circle Kodi integration needs.

That integration talks to Kodi over the network: through Kodi's web server, and through
control from applications on other systems. Turning this on lets any device on the home
network control the box, so it's a choice in setup and Settings rather than always on.
"""

import xbmc

from resources.lib import kodi_settings
from resources.lib.kodi import log

WEB_SERVER = "services.webserver"
SETTINGS_WHEN_ON = (
    (WEB_SERVER, True),
    ("services.webserverauthentication", False),
    ("services.esallinterfaces", True),
)
SETTINGS_WHEN_OFF = (
    (WEB_SERVER, False),
    ("services.esallinterfaces", False),
)


def is_enabled():
    try:
        return bool(kodi_settings.get_value(WEB_SERVER))
    except kodi_settings.KodiSettingError:
        return False


def set_enabled(enabled):
    """Turn remote control on or off. Returns True if Kodi accepted every change."""
    worked = True
    for setting_id, value in SETTINGS_WHEN_ON if enabled else SETTINGS_WHEN_OFF:
        try:
            kodi_settings.set_value(setting_id, value)
        except kodi_settings.KodiSettingError as error:
            log(f"Couldn't change remote control: {error}", xbmc.LOGWARNING)
            worked = False
    return worked
