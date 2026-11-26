"""JellyELEC's backdrop: the jellyfish splash, open behind everything while JellyELEC runs.

It goes up the moment JellyELEC starts, so Kodi's own home screen isn't seen while the
server is contacted, and it fills any gap between JellyELEC's other screens.

After an update, the old version hands over to the new one without a gap: it starts the new
version and keeps its backdrop up until the new version's backdrop is showing on top.
"""

import xbmc
import xbmcgui

from resources.lib.kodi import ADDON_ID, ADDON_PATH, log

HOME_WINDOW_ID = 10000
# Set on Kodi's home window as each JellyELEC backdrop opens, so the hand-over can tell when
# the new version's backdrop is up.
SPLASH_SHOWN_PROPERTY = "script.jellyelec.splash_shown"
HAND_OVER_TIMEOUT_SECONDS = 20


def open_splash():
    """Show the backdrop and return it. Call close() on it when JellyELEC finishes."""
    splash = SplashWindow("jellyelec-splash.xml", ADDON_PATH, "Default", "1080i")
    splash.show()
    xbmcgui.Window(HOME_WINDOW_ID).setProperty(SPLASH_SHOWN_PROPERTY, "true")
    return splash


def hand_over_to_new_version(splash):
    """Start the newly installed version, and wait until its backdrop covers this one.

    Returns False if the new version didn't show up in time.
    """
    home = xbmcgui.Window(HOME_WINDOW_ID)
    home.clearProperty(SPLASH_SHOWN_PROPERTY)
    splash.set_status("Starting the new version…")
    log("Handing over to the new version.")
    xbmc.executebuiltin(f"RunScript({ADDON_ID})")

    monitor = xbmc.Monitor()
    waited = 0.0
    while not home.getProperty(SPLASH_SHOWN_PROPERTY):
        if waited >= HAND_OVER_TIMEOUT_SECONDS or monitor.waitForAbort(0.1):
            log("The new version didn't start in time.", xbmc.LOGWARNING)
            return False
        waited += 0.1
    return True


class SplashWindow(xbmcgui.WindowXML):
    """Stays open beneath JellyELEC's other screens."""

    def onAction(self, action):
        # Nothing to go back to from here, so Back and every other key are ignored.
        pass

    def set_status(self, text):
        """A short line under the name, such as "Connecting to your server…"."""
        self.setProperty("status", text)
