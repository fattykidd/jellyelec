"""Application startup: sign in, then show the home screen."""

from resources.lib import storage
from resources.lib.home import HomeWindow
from resources.lib.kodi import ADDON_PATH
from resources.lib.session import start_session


def run():
    connection = storage.load()
    while True:
        client = start_session(connection)
        if client is None:
            return

        window = HomeWindow("jellyelec-home.xml", ADDON_PATH, "Default", "1080i")
        window.client = client
        window.connection = connection
        window.doModal()
        signed_out = window.signed_out
        del window

        if not signed_out:
            return
