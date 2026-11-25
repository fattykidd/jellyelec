"""JellyELEC's backdrop: a plain screen with the name, open behind everything while it runs.

It goes up the moment JellyELEC starts, so Kodi's own home screen isn't seen while the
server is contacted, and it fills any gap between JellyELEC's other screens.
"""

import xbmcgui

from resources.lib.kodi import ADDON_PATH


def open_splash():
    """Show the backdrop and return it. Call close() on it when JellyELEC finishes."""
    splash = SplashWindow("jellyelec-splash.xml", ADDON_PATH, "Default", "1080i")
    splash.show()
    return splash


class SplashWindow(xbmcgui.WindowXML):
    """Stays open beneath JellyELEC's other screens."""

    def onAction(self, action):
        # Nothing to go back to from here, so Back and every other key are ignored.
        pass

    def set_status(self, text):
        """A short line under the name, such as "Connecting to Jellyfin…"."""
        self.setProperty("status", text)
