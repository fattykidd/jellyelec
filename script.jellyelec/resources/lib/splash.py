"""JellyELEC's backdrop: the jellyfish splash, open behind everything while JellyELEC runs.

It goes up the moment JellyELEC starts, so Kodi's own home screen isn't seen while the
server is contacted, and it fills any gap between JellyELEC's other screens.

When a screen like this closes, Kodi goes back to whatever was showing when it opened. In
JellyELEC images that's arranged to be the startup screen (resources/skin_patch/Startup.xml), which
shows the same jellyfish, so closing the backdrop never reveals Kodi's home screen: not
when JellyELEC restarts after an update, and not in any other gap.
"""

import xbmc
import xbmcgui

from resources.lib.kodi import ADDON_ID, ADDON_PATH, log

HOME_WINDOW_ID = 10000
# Set by the startup screen in JellyELEC images, when it first opens.
STARTUP_SCREEN_PROPERTY = "jellyelec.startup_screen"
# Set as each JellyELEC backdrop opens, so a hand-over can tell the new version has started.
SPLASH_SHOWN_PROPERTY = "script.jellyelec.splash_shown"
STARTUP_SCREEN_TIMEOUT_SECONDS = 2
HAND_OVER_TIMEOUT_SECONDS = 20


def open_splash():
    """Show the backdrop and return it. Call close() on it when JellyELEC finishes."""
    _put_startup_screen_behind()
    splash = SplashWindow("jellyelec-splash.xml", ADDON_PATH, "Default", "1080i")
    splash.show()
    xbmcgui.Window(HOME_WINDOW_ID).setProperty(SPLASH_SHOWN_PROPERTY, "true")
    return splash


def start_new_version():
    """After an update: start the newly installed version, once this one's backdrop is closed.

    Returns False if the new version didn't show up in time.
    """
    home = xbmcgui.Window(HOME_WINDOW_ID)
    home.clearProperty(SPLASH_SHOWN_PROPERTY)
    log("Starting the new version.")
    xbmc.executebuiltin(f"RunScript({ADDON_ID})")
    if _wait_for(lambda: home.getProperty(SPLASH_SHOWN_PROPERTY), HAND_OVER_TIMEOUT_SECONDS):
        return True
    log("The new version didn't start in time.", xbmc.LOGWARNING)
    return False


class SplashWindow(xbmcgui.WindowXML):
    """Stays open beneath JellyELEC's other screens."""

    def onAction(self, action):
        # Nothing to go back to from here, so Back and every other key are ignored.
        pass

    def set_status(self, text):
        """A short line under the name, such as "Connecting to your server…"."""
        self.setProperty("status", text)


# Helpers ----------------------------------------------------------------------------

def _put_startup_screen_behind():
    """In JellyELEC images, make sure the startup screen is what's showing as JellyELEC opens.

    Usually it already is. After an update or Exit to Kodi, Kodi's home screen may be
    showing instead; switching to the startup screen first means it's the one that comes
    back when the backdrop closes.
    """
    if not xbmcgui.Window(HOME_WINDOW_ID).getProperty(STARTUP_SCREEN_PROPERTY):
        return  # not a JellyELEC image: the skin's own startup screen goes straight home
    if xbmc.getCondVisibility("Window.IsActive(startup)"):
        return
    xbmc.executebuiltin("ReplaceWindow(startup)")
    _wait_for(lambda: xbmc.getCondVisibility("Window.IsActive(startup)"), STARTUP_SCREEN_TIMEOUT_SECONDS)


def _wait_for(condition, timeout_seconds):
    """Wait until condition() is true. Returns False if timeout_seconds pass first."""
    monitor = xbmc.Monitor()
    waited = 0.0
    while not condition():
        if waited >= timeout_seconds or monitor.waitForAbort(0.1):
            return False
        waited += 0.1
    return True
