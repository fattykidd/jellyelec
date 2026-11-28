"""First-run setup: a few guided screens that get a new box ready to play.

Quick setup: welcome, Dolby Vision, how the box is connected, then (in session.py) finding
the server and signing in, and finally a remote control tip and "You're all set".

Custom setup adds, before signing in: Wi-Fi (only without a network cable), the box's
name, the time zone, SSH, file sharing and Bluetooth; and after signing in, the weather.
Everything chosen can be changed later in Settings.
"""

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import box_name, build_info, device_options, output_setup, remote_control
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log

# Control IDs, matching jellyelec-setup.xml.
FIRST_OPTION_BUTTON = 901
MAX_OPTIONS = 3

# Add-on setting that records setup has been finished.
SETUP_COMPLETE_SETTING = "setup_complete"

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)

# What a step returns: move on, go back a screen, or leave setup.
NEXT, BACK, QUIT = "next", "back", "quit"


def is_complete():
    return xbmcaddon.Addon().getSettingBool(SETUP_COMPLETE_SETTING)


class _Choices:
    """What's been chosen so far in this run of setup."""

    custom = False  # Custom setup rather than Quick
    box_name = None  # a name chosen in Custom setup, applied when setup finishes


def run_before_sign_in():
    """The screens before signing in. Returns False if the user leaves setup."""
    _Choices.custom = False
    _Choices.box_name = None
    if not _run_steps([_welcome_step]):
        return False
    steps = [_dolby_vision_step, _connection_step]
    if _Choices.custom:
        steps += [
            _network_step,
            _box_name_step,
            _time_zone_step,
            _ssh_step,
            _file_sharing_step,
            _bluetooth_step,
        ]
    return _run_steps(steps)


def reset():
    """Make setup run again the next time JellyELEC starts (from the add-on settings)."""
    xbmcaddon.Addon().setSettingBool(SETUP_COMPLETE_SETTING, False)
    xbmcgui.Dialog().notification(ADDON_NAME, "Setup will run the next time JellyELEC starts.")
    log("Setup reset; it will run on the next start.")


def run_after_sign_in():
    """The screens after signing in, then setup is marked as done."""
    steps = [_remote_control_step]
    if _Choices.custom:
        steps.append(_weather_step)
    _run_steps(steps + [_finished_step])
    # Done last: renaming restarts the network for a moment.
    if _Choices.box_name:
        device_options.apply_box_name(_Choices.box_name)
    else:
        box_name.name_new_box()
    xbmcaddon.Addon().setSettingBool(SETUP_COMPLETE_SETTING, True)
    log("First-run setup complete.")


def show_settings_warning():
    """Shown when Kodi refuses some of the sound and picture changes."""
    xbmcgui.Dialog().ok(
        ADDON_NAME,
        "Some settings couldn't be changed automatically on this version of CoreELEC.[CR]"
        "Everything else is set up, and the details are in the log.",
    )


# The steps ----------------------------------------------------------------------------

def _welcome_step():
    choice = _show_step(
        heading="Setup",
        title="Welcome to JellyELEC",
        body="Let's get this box ready. Quick setup takes a minute: Dolby Vision, sound, and "
             "then your Jellyfin server.[CR][CR]"
             "Custom setup also covers Wi-Fi, the box's name, time zone, SSH, file sharing, "
             "Bluetooth and the weather.",
        options=["Quick setup", "Custom setup"],
    )
    if choice is None:
        return QUIT
    _Choices.custom = choice == 1
    return NEXT


def _dolby_vision_step():
    if output_setup.dolby_vision_ready():
        choice = _show_step(
            heading="Setup · Dolby Vision",
            title="Dolby Vision is ready",
            body=f"The Dolby Vision module ({build_info.dovi_module()}) is installed, so Dolby Vision "
                 "and FEL titles will play as intended.",
            options=["Continue"],
        )
        return NEXT if choice == 0 else BACK

    choice = _show_step(
        heading="Setup · Dolby Vision",
        title="Dolby Vision isn't set up yet",
        body=output_setup.dovi_instructions() + "[CR]Setup picks up where it left off when the box starts again.",
        options=["Shut down so I can add it", "Skip for now"],
    )
    if choice == 0:
        log(f"Shutting down so {build_info.dovi_module()} can be added.")
        xbmc.executebuiltin("Powerdown")
        return QUIT
    return NEXT if choice == 1 else BACK


def _connection_step():
    choice = _show_step(
        heading="Setup · Sound and picture",
        title="How is this box connected?",
        body="This sets up the sound and picture to suit your equipment. You can change it later in Settings.",
        options=[name for _connection_type, name in output_setup.CONNECTIONS],
    )
    if choice is None:
        return BACK

    connection_type = output_setup.CONNECTIONS[choice][0]
    if not output_setup.apply_connection(connection_type):
        show_settings_warning()
    elif connection_type == output_setup.VIDEO_PROCESSOR and output_setup.waiting_for_lldv():
        xbmcgui.Dialog().ok("Dolby Vision", output_setup.LLDV_WAITING_MESSAGE)
    return NEXT


def _network_step():
    """Wi-Fi, asked only when there's no network cable plugged in."""
    if device_options.wired_connected():
        return NEXT
    choice = _show_step(
        heading="Setup · Network",
        title="Connect to Wi-Fi",
        body="No network cable is plugged in. A cable is best for 4K and lossless audio, but "
             "Wi-Fi works too.[CR][CR]"
             "Wi-Fi networks are joined in CoreELEC's settings, under Connections. Go back "
             "when you're connected, and setup carries on.",
        options=["Choose a Wi-Fi network", "Continue"],
    )
    if choice == 0:
        device_options.open_network_settings()
        return _network_step()
    return NEXT if choice == 1 else BACK


def _box_name_step():
    saved = box_name.current_name()
    if saved in ("", box_name.COREELEC_NAME):
        saved = box_name.JELLYELEC_NAME
    current = _Choices.box_name or saved
    choice = _show_step(
        heading="Setup · Box name",
        title=f"This box is called {current}",
        body="That's the name your router, file manager, Jellyfin's Devices page and other "
             "devices on your network see.",
        options=["Keep this name", "Change it"],
    )
    if choice == 1:
        _Choices.box_name = device_options.ask_box_name(current) or _Choices.box_name
        return _box_name_step()
    return NEXT if choice == 0 else BACK


def _time_zone_step():
    choice = _show_step(
        heading="Setup · Time zone",
        title=f"Time zone: {device_options.time_zone_summary() or 'not set'}",
        body="Used for the clock and the Live TV guide.",
        options=["That's right", "Change it"],
    )
    if choice == 1:
        device_options.change_time_zone()
        return _time_zone_step()
    return NEXT if choice == 0 else BACK


def _ssh_step():
    enabled = device_options.ssh_summary() == "On"
    choice = _show_step(
        heading="Setup · SSH",
        title=f"SSH is {'on' if enabled else 'off'}",
        body="SSH lets you sign in to the box from a computer, for troubleshooting or "
             "tinkering. Most people don't need it.[CR][CR]"
             "Turning it on asks for a new password, since CoreELEC's own is public knowledge.",
        options=["Leave it on" if enabled else "Leave it off", "Turn it off" if enabled else "Turn it on"],
    )
    if choice == 1:
        device_options.change_ssh()
        return _ssh_step()
    return NEXT if choice == 0 else BACK


def _file_sharing_step():
    enabled = device_options.file_sharing_summary() == "On"
    choice = _show_step(
        heading="Setup · File sharing",
        title=f"File sharing is {'on' if enabled else 'off'}",
        body="File sharing (Samba) lets computers on your network open the box's storage, for "
             "copying logs, screenshots or settings. Anyone on your home network can reach it.",
        options=["Leave it on" if enabled else "Leave it off", "Turn it off" if enabled else "Turn it on"],
    )
    if choice == 1:
        device_options.change_file_sharing()
        return _file_sharing_step()
    return NEXT if choice == 0 else BACK


def _bluetooth_step():
    enabled = device_options.bluetooth_summary() == "On"
    choice = _show_step(
        heading="Setup · Bluetooth",
        title=f"Bluetooth is {'on' if enabled else 'off'}",
        body="For a Bluetooth keyboard, remote or game controller. Headphones work too, but "
             "only with regular sound: lossless audio can't go over Bluetooth.[CR][CR]"
             "Devices are paired in CoreELEC's settings, under Bluetooth. Go back when "
             "you're done, and setup carries on.",
        options=["Continue", "Pair a device", "Turn it off" if enabled else "Turn it on"],
    )
    if choice == 1:
        device_options.open_bluetooth_pairing()
        return _bluetooth_step()
    if choice == 2:
        device_options.set_bluetooth(not enabled)
        return _bluetooth_step()
    return NEXT if choice == 0 else BACK


def _weather_step():
    choice = _show_step(
        heading="Setup · Weather",
        title="Show the weather?",
        body="JellyELEC can show the weather for your location, using the Open-Meteo weather "
             "add-on from Kodi's add-on repository. It needs no account.",
        options=["Set up the weather", "No thanks"],
    )
    if choice == 0:
        device_options.set_up_weather()
    return NEXT if choice is not None else BACK


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
        remote_control.set_enabled(True)
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


def _show_step(heading, title, body, options):
    """Show one setup screen. Returns the index of the option chosen, or None for Back."""
    window = SetupStepWindow("jellyelec-setup.xml", ADDON_PATH, "Default", "1080i")
    window.fill({"heading": heading, "title": title, "body": body}, options)
    window.doModal()
    choice = window.choice
    del window
    return choice


class SetupStepWindow(xbmcgui.WindowXMLDialog):
    """Call fill() before doModal(). The answer is left in choice."""

    options = ()
    choice = None

    def fill(self, texts, options):
        """Set the step's texts and option buttons.

        Done before the screen opens: a button without a label is hidden, and Kodi can't
        focus a hidden button, so setting labels as the screen opens left nothing focused
        and the remote did nothing.
        """
        self.options = options
        for name, text in texts.items():
            self.setProperty(name, text)
        for index in range(MAX_OPTIONS):
            label = options[index] if index < len(options) else ""
            self.setProperty(f"option{index + 1}", label)

    def onInit(self):
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
