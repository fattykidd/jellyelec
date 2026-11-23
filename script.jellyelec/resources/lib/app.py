"""Application startup and the home window."""

import xbmcgui

from resources.lib import storage
from resources.lib.kodi import ADDON_NAME, ADDON_PATH, ADDON_VERSION
from resources.lib.session import start_session

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


class HomeWindow(xbmcgui.WindowXML):
    """The JellyELEC home screen. For now it shows who is signed in."""

    connection = None
    signed_out = False

    def onInit(self):
        self.setProperty("version", ADDON_VERSION)
        self.setProperty("server_name", self.connection.server_name)
        self.setProperty("user_name", self.connection.user_name)

    def onAction(self, action):
        action_id = action.getId()
        if action_id in CLOSE_ACTIONS:
            self.close()
        elif action_id == xbmcgui.ACTION_CONTEXT_MENU:
            self._confirm_sign_out()

    def _confirm_sign_out(self):
        if xbmcgui.Dialog().yesno(ADDON_NAME, f"Sign out of {self.connection.server_name}?"):
            self.connection.sign_out()
            storage.save(self.connection)
            self.signed_out = True
            self.close()


def run():
    connection = storage.load()
    while True:
        client = start_session(connection)
        if client is None:
            return

        window = HomeWindow("jellyelec-home.xml", ADDON_PATH, "Default", "1080i")
        window.connection = connection
        window.doModal()
        signed_out = window.signed_out
        del window

        if not signed_out:
            return
