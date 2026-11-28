"""Box options offered in Custom setup and in Settings: name, time zone, Wi-Fi, SSH, file
sharing, Bluetooth and weather.

Each change_ or set_up_ function asks what it needs on screen, makes the change, and returns
True if something changed. The *_summary functions say how each option is set right now.
"""

import re
import time

import xbmc
import xbmcgui

from resources.lib import box_name, kodi_addons, kodi_settings, system_services
from resources.lib.kodi import ADDON_NAME, log

# Wi-Fi and Bluetooth pairing are done in CoreELEC's own settings screens.
COREELEC_SETTINGS_ADDON = "service.coreelec.settings"
COREELEC_SETTINGS_WINDOW = "service-CoreELEC-Settings-mainWindow.xml"
WIRED_CARRIER_FILE = "/sys/class/net/eth0/carrier"

# The weather add-on offered in setup: no account or API key needed.
# Open-Meteo, from Kodi's add-on repository: free, no account, and finds places reliably.
WEATHER_ADDON = "weather.openmeteo"
# Kodi's dialogs that the weather add-on can open while it's being set up: its settings, and
# the location search it may run the first time it's used.
WEATHER_DIALOGS = (
    "addonsettings", "virtualkeyboard", "selectdialog", "yesnodialog", "okdialog",
    "progressdialog", "busydialog", "busydialognocancel",
)

MIN_PASSWORD_LENGTH = 6
# A network name: letters, numbers and hyphens, not starting or ending with a hyphen.
VALID_BOX_NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


# Box name -----------------------------------------------------------------------------

def ask_box_name(current):
    """Ask for a new name. Returns it, or None if cancelled or left unchanged."""
    while True:
        name = xbmcgui.Dialog().input("Box name", defaultt=current).strip()
        if not name or name == current:
            return None
        if VALID_BOX_NAME.match(name):
            return name
        xbmcgui.Dialog().ok(
            "Box name", "Use letters, numbers and hyphens only, with no spaces, up to 63 characters."
        )


def change_box_name():
    name = ask_box_name(box_name.current_name() or box_name.JELLYELEC_NAME)
    if name is None:
        return False
    apply_box_name(name)
    return True


def apply_box_name(name):
    """The name on the network, and the name Kodi gives itself (shown on Jellyfin's Devices page)."""
    box_name.set_name(name)
    try:
        kodi_settings.set_value("services.devicename", name)
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't set Kodi's device name: {error}")


def keep_box_name():
    """Put the box's name back if something (a system update) changed it since JellyELEC set it.

    A box JellyELEC hasn't named yet, still on CoreELEC's name, gets the JellyELEC name.
    """
    wanted = box_name.wanted_name()
    current = box_name.current_name()
    if not wanted:
        if current in ("", box_name.COREELEC_NAME):
            wanted = box_name.JELLYELEC_NAME
        else:
            return
    if current != wanted:
        log(f"The box is named {current or 'nothing'}; putting its name back to {wanted}.")
        apply_box_name(wanted)
    elif box_name.settings_addon_name() != wanted:
        # Right for now, but CoreELEC's settings add-on would change it at the next start.
        log(f"Saving the box name {wanted} in CoreELEC's settings too.")
        box_name.save_in_settings_addon(wanted)


# Region -------------------------------------------------------------------------------

# Kodi's regional settings offered in JellyELEC's Settings: (setting, name, explanation).
REGION_SETTINGS = (
    ("locale.country", "Region",
     "Date and time formats and units, as used in a country. Temperature and clock follow it "
     "unless they're set on their own."),
    ("locale.temperatureunit", "Temperature unit", "For the weather."),
    ("locale.use24hourclock", "Clock", "12-hour or 24-hour time, here and in the Live TV guide."),
)


def region_settings():
    """The regional settings this Kodi has, as (setting, name, explanation, current choice)."""
    available = []
    for setting_id, name, explanation in REGION_SETTINGS:
        try:
            choices = dict(kodi_settings.choices(setting_id))
            current = kodi_settings.get_value(setting_id)
        except kodi_settings.KodiSettingError:
            continue
        if choices:
            available.append((setting_id, name, explanation, choices.get(current, str(current))))
    return available


def change_region_setting(setting_id, name):
    return _pick(setting_id, name)


# Time zone ----------------------------------------------------------------------------

def time_zone_summary():
    try:
        return kodi_settings.get_value("locale.timezone")
    except kodi_settings.KodiSettingError:
        return ""


def change_time_zone():
    """Pick the country, then the time zone within it."""
    if not _pick("locale.timezonecountry", "Country"):
        return False
    _pick("locale.timezone", "Time zone")
    return True


# Wi-Fi --------------------------------------------------------------------------------

def wired_connected():
    try:
        with open(WIRED_CARRIER_FILE, encoding="utf-8") as file:
            return file.read().strip() == "1"
    except OSError:
        return False


def open_network_settings():
    """CoreELEC's settings screen, where Wi-Fi networks are joined (under Connections)."""
    _open_coreelec_settings()


# SSH ----------------------------------------------------------------------------------

def ssh_summary():
    return "On" if system_services.is_enabled(system_services.SSH) else "Off"


def change_ssh():
    """Turn SSH off, or on with a new root password (CoreELEC's own is public knowledge)."""
    if system_services.is_enabled(system_services.SSH):
        if not xbmcgui.Dialog().yesno("SSH", "Turn SSH off?"):
            return False
        system_services.set_enabled(system_services.SSH, False)
        return True
    return turn_on_ssh()


def turn_on_ssh():
    while True:
        password = _ask_new_password()
        if password is None:
            return False
        refused_because = system_services.set_root_password(password)
        if refused_because is None:
            break
        xbmcgui.Dialog().ok(
            "SSH",
            f"That password was refused: {refused_because}.[CR]"
            "Choose a different one, unlike the box's name and not too simple.",
        )
    system_services.set_enabled(system_services.SSH, True)
    xbmcgui.Dialog().ok(
        "SSH", f"SSH is on. Sign in as root, with the password you just set, at {_box_address()}."
    )
    return True


# File sharing (Samba) -----------------------------------------------------------------

def file_sharing_summary():
    return "On" if system_services.is_enabled(system_services.SAMBA) else "Off"


def change_file_sharing():
    enable = not system_services.is_enabled(system_services.SAMBA)
    system_services.set_enabled(system_services.SAMBA, enable)
    return True


# Bluetooth ----------------------------------------------------------------------------

def bluetooth_summary():
    return "On" if system_services.is_enabled(system_services.BLUETOOTH) else "Off"


def set_bluetooth(enabled):
    system_services.set_enabled(system_services.BLUETOOTH, enabled)


def open_bluetooth_pairing():
    """CoreELEC's settings screen, where Bluetooth devices are paired (under Bluetooth)."""
    if not system_services.is_enabled(system_services.BLUETOOTH):
        set_bluetooth(True)
    _open_coreelec_settings()


# Weather ------------------------------------------------------------------------------

def current_weather_addon():
    """The weather add-on Kodi uses, or "" if the weather is off."""
    try:
        return kodi_settings.get_value("weather.addon") or ""
    except kodi_settings.KodiSettingError:
        return ""


def weather_summary():
    return "On" if current_weather_addon() else "Off"


def set_up_weather():
    """Install the weather add-on if needed, choose a location in its settings, then use it.

    A weather add-on already in use (one chosen in Kodi, say) is kept; otherwise Open-Meteo.
    """
    addon_id = current_weather_addon() or WEATHER_ADDON
    if not kodi_addons.is_installed(addon_id):
        xbmcgui.Dialog().notification("Weather", "Finding the weather add-on…")
        if not kodi_addons.install(addon_id):
            xbmcgui.Dialog().ok(
                "Weather", "The weather add-on couldn't be installed. Check the network and try again."
            )
            return False
    xbmcgui.Dialog().ok("Weather", "Next, choose your location in the weather add-on's settings, then go back.")
    xbmc.executebuiltin(f"Addon.OpenSettings({addon_id})", True)
    _wait_for_weather_dialogs(appear_seconds=2)
    try:
        kodi_settings.set_value("weather.addon", addon_id)
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't turn on the weather: {error}")
        return False
    # Kodi runs the add-on straight away, and it may ask for a location the first time.
    # Setup waits for that, so it doesn't pop up after setup has moved on.
    _wait_for_weather_dialogs(appear_seconds=5)
    return True


def turn_off_weather():
    try:
        kodi_settings.set_value("weather.addon", "")
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't turn off the weather: {error}")


# Helpers ----------------------------------------------------------------------------

def _wait_for_weather_dialogs(appear_seconds):
    """Wait up to appear_seconds for one of the weather add-on's dialogs to open, then until
    they've all closed. A short pause after each close catches one dialog leading to another,
    such as a location search followed by a list of matching places."""
    monitor = xbmc.Monitor()
    deadline = time.monotonic() + appear_seconds
    while not monitor.abortRequested():
        if any(xbmc.getCondVisibility(f"Window.IsVisible({name})") for name in WEATHER_DIALOGS):
            deadline = time.monotonic() + 1.5
        elif time.monotonic() >= deadline:
            return
        monitor.waitForAbort(0.25)


def _pick(setting_id, heading):
    """Choose a Kodi setting's value from its list. Returns True if one was chosen."""
    try:
        choices = kodi_settings.choices(setting_id)
        current = kodi_settings.get_value(setting_id)
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't read {setting_id}: {error}")
        return False
    if not choices:
        return False
    values = [value for value, _label in choices]
    preselect = values.index(current) if current in values else -1
    choice = xbmcgui.Dialog().select(heading, [label for _value, label in choices], preselect=preselect)
    if choice < 0:
        return False
    try:
        kodi_settings.set_value(setting_id, values[choice])
    except kodi_settings.KodiSettingError as error:
        log(f"Couldn't set {setting_id}: {error}")
        return False
    return True


def _ask_new_password():
    """Ask for a new password twice. Returns it, or None if cancelled."""
    dialog = xbmcgui.Dialog()
    while True:
        first = dialog.input(
            f"New root password (at least {MIN_PASSWORD_LENGTH} characters)",
            option=xbmcgui.ALPHANUM_HIDE_INPUT,
        )
        if not first:
            return None
        if len(first) < MIN_PASSWORD_LENGTH:
            dialog.ok("SSH", f"Use at least {MIN_PASSWORD_LENGTH} characters.")
            continue
        if dialog.input("Type the password again", option=xbmcgui.ALPHANUM_HIDE_INPUT) == first:
            return first
        dialog.ok("SSH", "The two passwords didn't match. Try again.")


def _open_coreelec_settings():
    """Open CoreELEC's settings screen and wait until it's closed again."""
    def is_open():
        return xbmc.getCondVisibility(f"Window.IsVisible({COREELEC_SETTINGS_WINDOW})")

    xbmc.executebuiltin(f"RunAddon({COREELEC_SETTINGS_ADDON})")
    if not _wait_for(is_open, 10):
        xbmcgui.Dialog().notification(ADDON_NAME, "CoreELEC's settings didn't open.")
        return
    _wait_for(lambda: not is_open(), None)


def _wait_for(condition, timeout_seconds):
    """Wait until condition() is true. Returns False if timeout_seconds pass first."""
    monitor = xbmc.Monitor()
    started = time.monotonic()
    while not condition():
        if timeout_seconds is not None and time.monotonic() - started > timeout_seconds:
            return False
        if monitor.waitForAbort(0.5):
            return False
    return True


def _box_address():
    """How to reach the box: its network name, or its IP address if it has none yet."""
    name = box_name.current_name()
    return f"{name}.local" if name else xbmc.getInfoLabel("Network.IPAddress")
