"""Application startup: install the key map, run first-run setup if needed, sign in, then show home."""

from resources.lib import setup, storage
from resources.lib.home import HomeWindow
from resources.lib.keymap import install_keymap
from resources.lib.kodi import ADDON_PATH
from resources.lib.session import start_session


def run():
    install_keymap()
    first_run = not setup.is_complete()
    if first_run and not setup.run_before_sign_in():
        return

    connection = storage.load()
    while True:
        client = start_session(connection)
        if client is None:
            return
        if first_run:
            setup.run_after_sign_in()
            first_run = False

        window = HomeWindow("jellyelec-home.xml", ADDON_PATH, "Default", "1080i")
        window.client = client
        window.connection = connection
        window.doModal()
        signed_out = window.signed_out
        del window

        if not signed_out:
            return
