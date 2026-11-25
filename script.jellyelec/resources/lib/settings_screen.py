"""The Settings screen, opened from the end of the home screen's library bar.

Each row shows a setting and its current value; OK changes it. Rows that need the home
screen to do something (sign out, run setup) close Settings and report it in next_step.
"""

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import appliance, output_setup, remote_control
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, ADDON_VERSION, log
from resources.lib.setup import show_settings_warning

# Control IDs, matching jellyelec-settings.xml.
SETTINGS_LIST = 1000

# What Settings can ask the home screen to do once it closes.
SIGN_OUT = "sign_out"
RUN_SETUP = "run_setup"
EXIT_TO_KODI = "exit_to_kodi"

# The power menu's choices, and the Kodi commands that carry them out.
POWER_CHOICES = (("Restart", "Reboot"), ("Power off", "Powerdown"))

# Add-on setting for the guide's live picture, shared with live_tv.py.
GUIDE_CORNER_SETTING = "guide_video_corner"
GUIDE_CORNERS = ("Top right", "Top left")

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# Row keys.
CONNECTION = "connection"
DOLBY_VISION = "dolby_vision"
GUIDE_CORNER = "guide_corner"
REMOTE_CONTROL = "remote_control"
APPLIANCE_MODE = "appliance_mode"
RUN_SETUP_ROW = "run_setup"
SIGN_OUT_ROW = "sign_out"
POWER = "power"
EXIT_TO_KODI_ROW = "exit_to_kodi"


def show_settings(connection):
    """Open Settings. Returns SIGN_OUT, RUN_SETUP, EXIT_TO_KODI, or None when the user just goes back."""
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
            GUIDE_CORNER: self._change_guide_corner,
            REMOTE_CONTROL: self._toggle_remote_control,
            APPLIANCE_MODE: self._toggle_appliance_mode,
            RUN_SETUP_ROW: self._run_setup,
            SIGN_OUT_ROW: self._sign_out,
            POWER: self._show_power_menu,
            EXIT_TO_KODI_ROW: self._exit_to_kodi,
        }
        key = self.getControl(SETTINGS_LIST).getSelectedItem().getProperty("key")
        handlers[key]()

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
                 "Whether the Dolby Vision module (dovi.ko) is installed. Press OK for details."),
            _row(GUIDE_CORNER, "Live TV guide: live picture", xbmcaddon.Addon().getSetting(GUIDE_CORNER_SETTING),
                 "Which top corner the live picture sits in while the guide is open."),
            _row(REMOTE_CONTROL, "Remote control from other devices",
                 "On" if remote_control.is_enabled() else "Off",
                 "Needed by the Unfolded Circle Kodi integration. Lets devices on your home network "
                 "control this box."),
            _row(APPLIANCE_MODE, "Open JellyELEC when the box starts",
                 "On" if appliance.is_enabled() else "Off",
                 "Starts JellyELEC with the box and reopens it if it ever closes, so the box always "
                 "shows JellyELEC."),
            _row(RUN_SETUP_ROW, "Run setup again", "",
                 "Go through the first-run screens again: Dolby Vision, connection and remote control."),
            _row(SIGN_OUT_ROW, "Sign out",
                 f"{self.connection.user_name} on {self.connection.server_name}",
                 "Sign out of this server, to sign in as someone else or choose another server."),
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
        if output_setup.apply_connection(output_setup.CONNECTIONS[choice][0]):
            _notify("Sound and picture settings updated.")
        else:
            show_settings_warning()
        self._fill_list()

    def _check_dolby_vision(self):
        if not output_setup.dolby_vision_ready():
            xbmcgui.Dialog().textviewer("Dolby Vision", output_setup.DOVI_INSTRUCTIONS)
        elif output_setup.dolby_vision_pending():
            if output_setup.apply_pending_dolby_vision():
                _notify("Dolby Vision settings finished.")
            else:
                xbmcgui.Dialog().ok(
                    "Dolby Vision",
                    "CoreELEC isn't offering its Dolby Vision settings yet. That usually means the "
                    "display chain doesn't support Dolby Vision.[CR]"
                    "They'll be finished automatically once it does.",
                )
        else:
            xbmcgui.Dialog().ok("Dolby Vision", "The Dolby Vision module is installed and set up.")
        self._fill_list()

    def _change_guide_corner(self):
        current = xbmcaddon.Addon().getSetting(GUIDE_CORNER_SETTING)
        new_corner = GUIDE_CORNERS[1] if current == GUIDE_CORNERS[0] else GUIDE_CORNERS[0]
        xbmcaddon.Addon().setSetting(GUIDE_CORNER_SETTING, new_corner)
        self._fill_list()

    def _toggle_remote_control(self):
        if not remote_control.set_enabled(not remote_control.is_enabled()):
            _notify("Couldn't change remote control. Details are in the log.")
        self._fill_list()

    def _toggle_appliance_mode(self):
        appliance.set_enabled(not appliance.is_enabled())
        self._fill_list()

    def _run_setup(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, "Run setup again now?"):
            log("Running setup again from Settings.")
            self.next_step = RUN_SETUP
            self.close()

    def _sign_out(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, f"Sign out of {self.connection.server_name}?"):
            self.next_step = SIGN_OUT
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


def _dolby_vision_status():
    if not output_setup.dolby_vision_ready():
        return "Not installed"
    if output_setup.dolby_vision_pending():
        return "Installed · settings waiting"
    return "Installed"


def _notify(message):
    xbmcgui.Dialog().notification(ADDON_NAME, message)
