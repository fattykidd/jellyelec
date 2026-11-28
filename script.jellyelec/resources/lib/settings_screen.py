"""The Settings screen, opened from the end of the home screen's library bar.

Each row shows a setting and its current value; OK changes it. Rows that need the home
screen to do something (sign out, run setup) close Settings and report it in next_step.
"""

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import (
    appliance,
    box_name,
    build_info,
    device_options,
    media_details,
    output_setup,
    remote_control,
    updater,
)
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, ADDON_VERSION, log
from resources.lib.setup import show_settings_warning

# Control IDs, matching jellyelec-settings.xml.
SETTINGS_LIST = 1000

# What Settings can ask the home screen to do once it closes.
SIGN_OUT = "sign_out"
RUN_SETUP = "run_setup"
EXIT_TO_KODI = "exit_to_kodi"
RESTART = "restart"  # after an update, so the new version runs

# The power menu's choices, and the Kodi commands that carry them out.
POWER_CHOICES = (("Restart", "Reboot"), ("Power off", "Powerdown"))

# Add-on settings for the Live TV guide, shared with live_tv.py.
GUIDE_CORNER_SETTING = "guide_video_corner"
GUIDE_CORNERS = ("Top right", "Top left")
GUIDE_OK_SETTING = "guide_ok_action"
GUIDE_OK_ACTIONS = ("Watch full-screen", "Preview in the corner")

# Add-on setting for grouping movie collections, shared with library.py.
GROUP_COLLECTIONS_SETTING = "group_collections"

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# Row keys.
CONNECTION = "connection"
COLLECTIONS = "collections"
MEDIA_DETAILS = "media_details"
DOLBY_VISION = "dolby_vision"
GUIDE_CORNER = "guide_corner"
GUIDE_OK = "guide_ok"
REMOTE_CONTROL = "remote_control"
BOX_NAME = "box_name"
TIME_ZONE = "time_zone"
# Kodi's regional settings (Region, Temperature unit, Clock) have keys made from their IDs.
REGION_PREFIX = "region:"
WIFI = "wifi"
SSH = "ssh"
FILE_SHARING = "file_sharing"
BLUETOOTH = "bluetooth"
WEATHER = "weather"
APPLIANCE_MODE = "appliance_mode"
RUN_SETUP_ROW = "run_setup"
SIGN_OUT_ROW = "sign_out"
POWER = "power"
EXIT_TO_KODI_ROW = "exit_to_kodi"
UPDATES = "updates"


def show_settings(connection):
    """Open Settings. Returns SIGN_OUT, RUN_SETUP, EXIT_TO_KODI, RESTART, or None for just going back."""
    window = SettingsWindow("jellyelec-settings.xml", ADDON_PATH, "Default", "1080i")
    window.connection = connection
    window.doModal()
    next_step = window.next_step
    del window
    return next_step


class SettingsWindow(xbmcgui.WindowXMLDialog):
    """Set connection before calling doModal(). The home screen's next step is left in next_step."""

    connection = None
    next_step = None

    _loaded = False

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        self.setProperty("about", f"{ADDON_NAME} {ADDON_VERSION}")
        if not self._loaded:
            self._loaded = True
            self._fill_list()
            self.setFocusId(SETTINGS_LIST)

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.close()

    def onClick(self, control_id):
        if control_id != SETTINGS_LIST:
            return
        handlers = {
            CONNECTION: self._change_connection,
            DOLBY_VISION: self._check_dolby_vision,
            COLLECTIONS: self._toggle_collections,
            MEDIA_DETAILS: self._toggle_media_details,
            GUIDE_CORNER: self._change_guide_corner,
            GUIDE_OK: self._change_guide_ok,
            REMOTE_CONTROL: self._toggle_remote_control,
            BOX_NAME: device_options.change_box_name,
            TIME_ZONE: device_options.change_time_zone,
            WIFI: device_options.open_network_settings,
            SSH: device_options.change_ssh,
            FILE_SHARING: device_options.change_file_sharing,
            BLUETOOTH: self._change_bluetooth,
            WEATHER: self._change_weather,
            APPLIANCE_MODE: self._toggle_appliance_mode,
            RUN_SETUP_ROW: self._run_setup,
            SIGN_OUT_ROW: self._sign_out,
            POWER: self._show_power_menu,
            EXIT_TO_KODI_ROW: self._exit_to_kodi,
            UPDATES: self._check_for_updates,
        }
        selected = self.getControl(SETTINGS_LIST).getSelectedItem()
        key = selected.getProperty("key")
        if key.startswith(REGION_PREFIX):
            device_options.change_region_setting(key[len(REGION_PREFIX):], selected.getLabel())
        else:
            handlers[key]()
        if not self.next_step:
            self._fill_list()  # show any value that changed

    # The list ---------------------------------------------------------------------

    def _fill_list(self):
        """Build the rows. Called again after each change so the values stay current."""
        settings_list = self.getControl(SETTINGS_LIST)
        position = settings_list.getSelectedPosition()
        settings_list.reset()
        settings_list.addItems([
            _row(CONNECTION, "How this box is connected",
                 output_setup.connection_name(output_setup.current_connection()),
                 "Sets up sound (passthrough to your receiver) and picture (Dolby Vision mode) to suit "
                 "your equipment."),
            _row(DOLBY_VISION, "Dolby Vision", _dolby_vision_status(),
                 f"Whether the Dolby Vision module ({build_info.dovi_module()}) is installed. "
                 "Press OK for details."),
            _row(COLLECTIONS, "Movie collections",
                 "Grouped" if xbmcaddon.Addon().getSettingBool(GROUP_COLLECTIONS_SETTING) else "Every movie listed",
                 "Grouped shows each collection once in a movie library, in place of the movies in it. "
                 "Opening it lists its movies."),
            _row(MEDIA_DETAILS, "Media details", media_details.style(),
                 "How a title's resolution, HDR format and audio are shown on the home screen and in "
                 "libraries: as badges, or as one line of text."),
            _row(GUIDE_CORNER, "Live TV guide: live picture", xbmcaddon.Addon().getSetting(GUIDE_CORNER_SETTING),
                 "Which top corner the live picture sits in while the guide is open."),
            _row(GUIDE_OK, "Live TV guide: OK on another channel", xbmcaddon.Addon().getSetting(GUIDE_OK_SETTING),
                 "Watch it full-screen straight away, or preview it in the corner first (press OK "
                 "again for full-screen)."),
            _row(REMOTE_CONTROL, "Remote control from other devices",
                 "On" if remote_control.is_enabled() else "Off",
                 "Needed by the Unfolded Circle Kodi integration. Lets devices on your home network "
                 "control this box."),
            _row(BOX_NAME, "Box name", box_name.current_name(),
                 "What your router, file manager, Jellyfin's Devices page and other devices on your "
                 "network call this box."),
            _row(TIME_ZONE, "Time zone", device_options.time_zone_summary(),
                 "Used for the clock and the Live TV guide."),
            *(
                _row(REGION_PREFIX + setting_id, name, current, explanation)
                for setting_id, name, explanation, current in device_options.region_settings()
            ),
            _row(WIFI, "Wi-Fi", "Connected by cable" if device_options.wired_connected() else "",
                 "Join a Wi-Fi network, in CoreELEC's settings under Connections."),
            _row(SSH, "SSH", device_options.ssh_summary(),
                 "Sign in to the box from a computer. Turning it on asks for a new root password."),
            _row(FILE_SHARING, "File sharing (Samba)", device_options.file_sharing_summary(),
                 "Lets computers on your network open the box's storage, for logs, screenshots "
                 "and settings."),
            _row(BLUETOOTH, "Bluetooth", device_options.bluetooth_summary(),
                 "Pair a keyboard, remote, game controller or headphones (regular sound only)."),
            _row(WEATHER, "Weather", device_options.weather_summary(),
                 "The weather for your location, from the Open-Meteo add-on."),
            _row(APPLIANCE_MODE, "Open JellyELEC when the box starts",
                 "On" if appliance.is_enabled() else "Off",
                 "Starts JellyELEC with the box and reopens it if it ever closes, so the box always "
                 "shows JellyELEC."),
            _row(RUN_SETUP_ROW, "Run setup again", "",
                 "Go through the first-run screens again: Dolby Vision, connection and remote control."),
            _row(SIGN_OUT_ROW, "Sign out",
                 f"{self.connection.user_name} on {self.connection.server_name}",
                 "Sign out of this server, to sign in as someone else or choose another server."),
            _row(UPDATES, "Check for updates", _version_summary(),
                 "Look for a newer JellyELEC on GitHub and install it: the add-on, or a system update "
                 "(a newer p3i with JellyELEC built in) that installs with a restart. JellyELEC also "
                 "checks once a day and mentions it when there's one."),
            _row(POWER, "Power", "",
                 "Restart or power off the box."),
            _row(EXIT_TO_KODI_ROW, "Exit to Kodi", "",
                 "Leave JellyELEC for Kodi's own menus, for maintenance. JellyELEC opens again at the "
                 "next restart."),
        ])
        settings_list.selectItem(max(position, 0))

    # Row actions ------------------------------------------------------------------

    def _change_connection(self):
        connection_types = [connection_type for connection_type, _name in output_setup.CONNECTIONS]
        names = [name for _connection_type, name in output_setup.CONNECTIONS]
        current = output_setup.current_connection()
        preselect = connection_types.index(current) if current in connection_types else -1
        choice = xbmcgui.Dialog().select("How is this box connected?", names, preselect=preselect)
        if choice < 0:
            return
        connection_type = output_setup.CONNECTIONS[choice][0]
        if not output_setup.apply_connection(connection_type):
            show_settings_warning()
        elif connection_type == output_setup.VIDEO_PROCESSOR and output_setup.waiting_for_lldv():
            xbmcgui.Dialog().ok("Dolby Vision", output_setup.LLDV_WAITING_MESSAGE)
        else:
            _notify("Sound and picture settings updated.")

    def _check_dolby_vision(self):
        if not output_setup.dolby_vision_ready():
            xbmcgui.Dialog().textviewer("Dolby Vision", output_setup.dovi_instructions())
        elif output_setup.dolby_vision_pending():
            if not output_setup.apply_pending_dolby_vision():
                show_settings_warning()
            elif output_setup.waiting_for_lldv():
                xbmcgui.Dialog().ok("Dolby Vision", output_setup.LLDV_WAITING_MESSAGE)
            else:
                _notify("Dolby Vision settings finished.")
        else:
            xbmcgui.Dialog().ok("Dolby Vision", "The Dolby Vision module is installed and set up.")

    def _toggle_collections(self):
        addon = xbmcaddon.Addon()
        addon.setSettingBool(GROUP_COLLECTIONS_SETTING, not addon.getSettingBool(GROUP_COLLECTIONS_SETTING))

    def _toggle_media_details(self):
        _toggle_setting(media_details.STYLE_SETTING, media_details.STYLES)

    def _change_guide_corner(self):
        _toggle_setting(GUIDE_CORNER_SETTING, GUIDE_CORNERS)

    def _change_guide_ok(self):
        _toggle_setting(GUIDE_OK_SETTING, GUIDE_OK_ACTIONS)

    def _toggle_remote_control(self):
        if not remote_control.set_enabled(not remote_control.is_enabled()):
            _notify("Couldn't change remote control. Details are in the log.")

    def _change_bluetooth(self):
        enabled = device_options.bluetooth_summary() == "On"
        toggle = "Turn Bluetooth off" if enabled else "Turn Bluetooth on"
        choice = xbmcgui.Dialog().select("Bluetooth", ["Pair a device", toggle])
        if choice == 0:
            device_options.open_bluetooth_pairing()
        elif choice == 1:
            device_options.set_bluetooth(not enabled)

    def _change_weather(self):
        if device_options.weather_summary() != "On":
            device_options.set_up_weather()
            return
        choice = xbmcgui.Dialog().select("Weather", ["Change location", "Turn the weather off"])
        if choice == 0:
            device_options.set_up_weather()
        elif choice == 1:
            device_options.turn_off_weather()

    def _toggle_appliance_mode(self):
        appliance.set_enabled(not appliance.is_enabled())

    def _run_setup(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, "Run setup again now?"):
            log("Running setup again from Settings.")
            self.next_step = RUN_SETUP
            self.close()

    def _sign_out(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, f"Sign out of {self.connection.server_name}?"):
            self.next_step = SIGN_OUT
            self.close()

    def _check_for_updates(self):
        progress = xbmcgui.DialogProgress()
        progress.create("Check for updates", "Looking for a newer version…")
        try:
            system_update, addon_release = updater.check()
        except updater.UpdateError as error:
            progress.close()
            log(f"Update check failed: {error}", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok(
                "Check for updates", "Couldn't check for updates. Check the network and try again."
            )
            return
        progress.close()

        # A system update includes the newest add-on, so it comes first.
        if system_update:
            self._offer_system_update(system_update)
        elif addon_release:
            self._offer_addon_update(addon_release)
        else:
            xbmcgui.Dialog().ok("Check for updates", f"JellyELEC is up to date ({_version_summary()}).")

    def _offer_addon_update(self, release):
        if xbmcgui.Dialog().yesno(
            "Check for updates",
            f"JellyELEC {release.version} is available (this is {ADDON_VERSION}).[CR]Install it now?",
            nolabel="Not now",
            yeslabel="Install",
        ):
            self._install_update(release)

    def _offer_system_update(self, update):
        size = f"about {update.tar_size // 2**20} MB" if update.tar_size else "a large download"
        if not xbmcgui.Dialog().yesno(
            "System update",
            f"A system update is available: {update.description}.[CR][CR]"
            f"It downloads now ({size}) and installs when the box restarts, which takes a few "
            "minutes. Settings, sign-in and Dolby Vision setup are kept.",
            nolabel="Not now",
            yeslabel="Download",
        ):
            return

        missing = updater.missing_dovi_module(update)
        if missing and not xbmcgui.Dialog().yesno(
            "System update",
            f"This update needs a different Dolby Vision module: {missing}.[CR][CR]"
            f"Before restarting, shut the box down and copy {missing} onto the drive named "
            "COREELEC, next to the one there now. Without it, Dolby Vision titles play in HDR10.",
            nolabel="Cancel",
            yeslabel="Continue",
        ):
            return

        progress = xbmcgui.DialogProgress()
        progress.create("System update", f"Downloading {update.description}…")
        try:
            updater.download_system_update(
                update, lambda percent: progress.update(percent) or not progress.iscanceled()
            )
        except updater.UpdateError as error:
            progress.close()
            log(f"System update download failed: {error}", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("System update", f"The update didn't download: {error}")
            return
        progress.close()

        if xbmcgui.Dialog().yesno(
            "System update",
            "The update is ready. Restart now to install it?[CR][CR]"
            "The box shows CoreELEC's progress while it installs, then starts JellyELEC again.",
            nolabel="Later",
            yeslabel="Restart now",
        ):
            log(f"Restarting to install system update build {update.build}.")
            xbmc.executebuiltin("Reboot")
        else:
            _notify("The system update installs the next time the box restarts.")

    def _install_update(self, release):
        progress = xbmcgui.DialogProgress()
        progress.create("Updating JellyELEC", f"Installing version {release.version}…")
        try:
            updater.install(release)
        except updater.UpdateError as error:
            progress.close()
            log(str(error), xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("Updating JellyELEC", f"The update didn't install: {error}")
            return
        progress.close()

        xbmcgui.Dialog().ok(
            "Updating JellyELEC", f"Version {release.version} is installed. JellyELEC will now restart into it."
        )
        self.next_step = RESTART
        self.close()

    def _show_power_menu(self):
        choice = xbmcgui.Dialog().select("Power", [label for label, _command in POWER_CHOICES])
        if choice >= 0:
            log(f"Power menu: {POWER_CHOICES[choice][0]}.")
            xbmc.executebuiltin(POWER_CHOICES[choice][1])

    def _exit_to_kodi(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, "Exit to Kodi? JellyELEC opens again at the next restart."):
            self.next_step = EXIT_TO_KODI
            self.close()


# Helpers ----------------------------------------------------------------------------

def _row(key, label, value, description):
    item = xbmcgui.ListItem(label=label, label2=value, offscreen=True)
    item.setProperty("key", key)
    item.setProperty("description", description)
    return item


def _toggle_setting(setting_id, values):
    """Switch a two-choice add-on setting to its other value."""
    current = xbmcaddon.Addon().getSetting(setting_id)
    xbmcaddon.Addon().setSetting(setting_id, values[1] if current == values[0] else values[0])


def _dolby_vision_status():
    if not output_setup.dolby_vision_ready():
        return "Not installed"
    if output_setup.dolby_vision_pending():
        return "Installed · waiting for LLDV"
    return "Installed"


def _version_summary():
    """Version 0.0.59 · p3i T4c, build 202611271830 (or just the version on older images)."""
    build = build_info.installed_build()
    if not build:
        return f"Version {ADDON_VERSION}"
    return f"Version {ADDON_VERSION} · p3i {build.get('p3i_release', '?')}, build {build.get('build', '?')}"


def _notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message)
