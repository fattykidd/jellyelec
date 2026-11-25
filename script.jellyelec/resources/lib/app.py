"""Application startup: install the key map, run first-run setup if needed, sign in, then show home."""

from resources.lib import appliance, output_setup, setup, storage
from resources.lib.home import HomeWindow
from resources.lib.keymap import install_keymap, remove_live_tv_keymap
from resources.lib.kodi import ADDON_PATH
from resources.lib.session import start_session
from resources.lib.settings_screen import EXIT_TO_KODI, RUN_SETUP, SIGN_OUT


def run(splash):
    """Run JellyELEC until it's left. splash is the backdrop default.py has already put up."""
    install_keymap()
    remove_live_tv_keymap()
    if setup.is_complete():
        # Finishes video processor mode once dovi.ko has been added after setup.
        output_setup.apply_pending_dolby_vision()
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

        next_step = _show_home(client, connection)
        if next_step == RUN_SETUP:
            if not setup.run_before_sign_in():
                return
            closing_steps_due = True
        elif next_step == EXIT_TO_KODI:
            appliance.leave_for_maintenance()
            return
        elif next_step != SIGN_OUT:
            return


def _show_home(client, connection):
    """Show the home screen until it closes. Returns its next_step."""
    window = HomeWindow("jellyelec-home.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.connection = connection
    window.doModal()
    next_step = window.next_step
    del window
    return next_step
