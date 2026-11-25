"""First-run setup: a few guided screens that get a new box ready to play.

The order is: welcome, Dolby Vision, how the box is connected, then (in session.py) finding
the server and signing in, and finally a remote control tip and "You're all set".
"""

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import kodi_settings, output_setup
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log

# Control IDs, matching jellyelec-setup.xml.
FIRST_OPTION_BUTTON = 901
MAX_OPTIONS = 3

# Add-on settings that remember the answers.
SETUP_COMPLETE_SETTING = "setup_complete"
CONNECTION_SETTING = "box_connection"

# Kodi settings the Unfolded Circle Kodi integration needs: the web server, and control
# from other devices on the network.
REMOTE_CONTROL_SETTINGS = (
    ("services.webserver", True),
    ("services.webserverauthentication", False),
    ("services.esallinterfaces", True),
)

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# What a step returns: move on, go back a screen, or leave setup.
NEXT, BACK, QUIT = "next", "back", "quit"


def is_complete():
    return xbmcaddon.Addon().getSettingBool(SETUP_COMPLETE_SETTING)


def run_before_sign_in():
    """Welcome, Dolby Vision, and connection screens. Returns False if the user leaves setup."""
    return _run_steps([_welcome_step, _dolby_vision_step, _connection_step])


def reset():
    """Make setup run again the next time JellyELEC starts (from the add-on settings)."""
    xbmcaddon.Addon().setSettingBool(SETUP_COMPLETE_SETTING, False)
    xbmcgui.Dialog().notification(ADDON_NAME, "Setup will run the next time JellyELEC starts.")
    log("Setup reset; it will run on the next start.")


def run_after_sign_in():
    """The remote control tip and the closing screen, then setup is marked as done."""
    _run_steps([_remote_control_step, _finished_step])
    xbmcaddon.Addon().setSettingBool(SETUP_COMPLETE_SETTING, True)
    log("First-run setup complete.")


# The steps ----------------------------------------------------------------------------

def _welcome_step():
    choice = _show_step(
        heading="Setup",
        title="Welcome to JellyELEC",
        body="Let's get this box ready. It only takes a minute: Dolby Vision, sound, "
             "and then your Jellyfin server.",
        options=["Get started"],
    )
    return NEXT if choice == 0 else QUIT


def _dolby_vision_step():
    if output_setup.dolby_vision_ready():
        choice = _show_step(
            heading="Setup · Dolby Vision",
            title="Dolby Vision is ready",
            body="The Dolby Vision module (dovi.ko) is installed, so Dolby Vision and FEL titles "
                 "will play as intended.",
            options=["Continue"],
        )
        return NEXT if choice == 0 else BACK

    choice = _show_step(
        heading="Setup · Dolby Vision",
        title="Dolby Vision isn't set up yet",
        body="JellyELEC can't include the Dolby Vision module (dovi.ko), so it's added by hand:[CR][CR]"
             "1.  Shut down this box and put its card or USB stick in a computer.[CR]"
             "2.  Copy dovi.ko onto the drive named COREELEC (into the top folder, not a subfolder).[CR]"
             "3.  Put the card back and turn the box on. Setup picks up where it left off.[CR][CR]"
             "Without it, Dolby Vision titles play in HDR10 instead.",
        options=["Shut down so I can add it", "Skip for now"],
    )
    if choice == 0:
        log("Shutting down so dovi.ko can be added.")
        xbmc.executebuiltin("Powerdown")
        return QUIT
    return NEXT if choice == 1 else BACK


def _connection_step():
    choice = _show_step(
        heading="Setup · Sound and picture",
        title="How is this box connected?",
        body="This sets up the sound and picture to suit your equipment. You can change it later in Settings.",
        options=[
            "Straight to the TV",
            "Through an AV receiver",
            "Through an AV receiver and a video processor",
        ],
    )
    if choice is None:
        return BACK

    connection_type = (output_setup.TV, output_setup.RECEIVER, output_setup.VIDEO_PROCESSOR)[choice]
    if not output_setup.apply_connection(connection_type):
        xbmcgui.Dialog().ok(
            ADDON_NAME,
            "Some settings couldn't be changed automatically on this version of CoreELEC.[CR]"
            "Everything else is set up, and the details are in the log.",
        )
    xbmcaddon.Addon().setSetting(CONNECTION_SETTING, connection_type)
    return NEXT


def _remote_control_step():
    choice = _show_step(
        heading="Setup · Remote control",
        title="Using an Unfolded Circle remote?",
        body="The Kodi integration on the remote can control JellyELEC. It needs remote control "
             "turned on, which lets devices on your home network control this box.[CR][CR]"
             "The Guide button opens the TV guide. For channel up and down, map those buttons to "
             "the commands  key pageup  and  key pagedown.",
        options=["Turn on remote control", "Not now"],
    )
    if choice == 0:
        _enable_network_control()
    return NEXT if choice is not None else BACK


def _finished_step():
    _show_step(
        heading="Setup",
        title="You're all set",
        body="Enjoy your media. Every answer from setup can be changed later in Settings.",
        options=["Start watching"],
    )
    return NEXT


# Helpers ----------------------------------------------------------------------------

def _run_steps(steps):
    """Show steps in order. Back returns to the previous one. Returns False if setup was left."""
    index = 0
    while index < len(steps):
        result = steps[index]()
        if result == QUIT:
            return False
        if result == BACK:
            index = max(index - 1, 0)
        else:
            index += 1
    return True


def _enable_network_control():
    for setting_id, value in REMOTE_CONTROL_SETTINGS:
        try:
            kodi_settings.set_value(setting_id, value)
        except kodi_settings.KodiSettingError as error:
            log(f"Couldn't turn on remote control: {error}", xbmc.LOGWARNING)


def _show_step(heading, title, body, options):
    """Show one setup screen. Returns the index of the option chosen, or None for Back."""
    window = SetupStepWindow("jellyelec-setup.xml", ADDON_PATH, "Default", "1080i")
    window.texts = {"heading": heading, "title": title, "body": body}
    window.options = options
    window.doModal()
    choice = window.choice
    del window
    return choice


class SetupStepWindow(xbmcgui.WindowXMLDialog):
    """Set texts and options before calling doModal(). The answer is left in choice."""

    texts = None
    options = None
    choice = None

    def onInit(self):
        for name, text in self.texts.items():
            self.setProperty(name, text)
        for index in range(MAX_OPTIONS):
            label = self.options[index] if index < len(self.options) else ""
            self.setProperty(f"option{index + 1}", label)
        self.setFocusId(FIRST_OPTION_BUTTON)

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self.choice = None
            self.close()

    def onClick(self, control_id):
        index = control_id - FIRST_OPTION_BUTTON
        if 0 <= index < len(self.options):
            self.choice = index
            self.close()
