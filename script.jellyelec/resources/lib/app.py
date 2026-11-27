"""Application startup: install the key map, run first-run setup if needed, sign in, then show home."""

import threading

import xbmc
import xbmcgui

from resources.lib import after_update, appliance, device_options, output_setup, setup, storage, updater
from resources.lib.home import HomeWindow
from resources.lib.keymap import install_keymap, remove_live_tv_keymap
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, log
from resources.lib.session import start_session
from resources.lib.settings_screen import EXIT_TO_KODI, RESTART, RUN_SETUP, SIGN_OUT


def run(splash):
    """Run JellyELEC until it's left. splash is the backdrop default.py has already put up.

    Returns True if it was left to switch to a newly installed version.
    """
    install_keymap()
    remove_live_tv_keymap()
    if after_update.finish_if_updated(splash):
        return
    if setup.is_complete():
        # Finishes video processor mode once dovi.ko has been added after setup.
        output_setup.apply_pending_dolby_vision()
        device_options.keep_box_name()
        closing_steps_due = False
    elif setup.run_before_sign_in():
        closing_steps_due = True
    else:
        return

    connection = storage.load()
    while True:
        splash.set_status("Connecting to your server…")
        client = start_session(connection)
        splash.set_status("")
        if client is None:
            return
        if closing_steps_due:
            setup.run_after_sign_in()
            closing_steps_due = False
        _check_for_updates_in_background()

        next_step = _show_home(client, connection)
        if next_step == RUN_SETUP:
            if not setup.run_before_sign_in():
                return
            closing_steps_due = True
        elif next_step == EXIT_TO_KODI:
            appliance.leave_for_maintenance()
            return
        elif next_step == RESTART:
            return True
        elif next_step != SIGN_OUT:
            return


def _check_for_updates_in_background():
    """Once a day, look for a new version without holding anything up, and mention it if found."""
    if not updater.check_is_due():
        return

    def check():
        try:
            system_update, addon_release = updater.check()
        except updater.UpdateError as error:
            log(f"Background update check failed: {error}", xbmc.LOGWARNING)
            return
        if system_update:
            message = f"A system update is available ({system_update.description}): Settings, Check for updates."
        elif addon_release:
            message = f"Version {addon_release.version} is available: Settings, Check for updates."
        else:
            return
        xbmcgui.Dialog().notification(ADDON_NAME, message, time=10000)

    threading.Thread(target=check, name="JellyELEC update check", daemon=True).start()


def _show_home(client, connection):
    """Show the home screen until it closes. Returns its next_step."""
    window = HomeWindow("jellyelec-home.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.connection = connection
    window.doModal()
    next_step = window.next_step
    del window
    return next_step
