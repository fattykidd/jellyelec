"""Signing in with a Quick Connect code, approved from the Jellyfin app or web page."""

import threading
import time

import xbmc
import xbmcgui

from resources.lib.api import JellyfinError
from resources.lib.kodi import ADDON_PATH, log

# Control IDs, matching jellyelec-quickconnect.xml.
USE_PASSWORD_BUTTON = 900

# How often to ask the server whether the code has been approved.
POLL_SECONDS = 2

# Jellyfin keeps a Quick Connect code for 10 minutes. A fresh one is fetched a little
# before that, so nobody starts typing a code that's about to stop working.
CODE_LIFETIME_SECONDS = 10 * 60
REFRESH_BEFORE_EXPIRY_SECONDS = 15

# Returned when the user chooses to sign in with a username and password instead.
USE_PASSWORD = "use_password"

CLOSE_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


def sign_in_with_quick_connect(client, server_name):
    """Show a Quick Connect code and wait for it to be approved.

    Returns the signed-in user, USE_PASSWORD if the server doesn't allow Quick Connect or the
    user asks for a password instead, or None if the user cancels.
    """
    if not client.quick_connect_enabled():
        log("Quick Connect is turned off on the server; asking for a password.")
        return USE_PASSWORD

    window = QuickConnectWindow("jellyelec-quickconnect.xml", ADDON_PATH, "Default", "1080i")
    window.client = client
    window.server_name = server_name
    window.doModal()
    result = window.result
    del window
    return result


class QuickConnectWindow(xbmcgui.WindowXMLDialog):
    """Set client and server_name before calling doModal(). The outcome is left in result."""

    client = None
    server_name = ""
    result = None

    _started = False
    _stop = None

    # Kodi events ------------------------------------------------------------------

    def onInit(self):
        if self._started:
            return
        self._started = True
        self.setProperty("server_name", self.server_name)
        self.setProperty("status", "Getting a code…")
        self.setFocusId(USE_PASSWORD_BUTTON)
        # Wait for approval in the background so the screen stays responsive.
        self._stop = threading.Event()
        threading.Thread(target=self._wait_for_approval, name="JellyELEC Quick Connect", daemon=True).start()

    def onAction(self, action):
        if action.getId() in CLOSE_ACTIONS:
            self._finish(None)

    def onClick(self, control_id):
        if control_id == USE_PASSWORD_BUTTON:
            self._finish(USE_PASSWORD)

    # Background thread --------------------------------------------------------------

    def _wait_for_approval(self):
        """Once a second: update the countdown. Every POLL_SECONDS: check for approval."""
        monitor = xbmc.Monitor()
        secret = None
        expires_at = 0.0
        seconds = 0
        while not self._stop.is_set():
            try:
                if secret is None or time.monotonic() >= expires_at - REFRESH_BEFORE_EXPIRY_SECONDS:
                    secret = self._new_code()
                    expires_at = time.monotonic() + CODE_LIFETIME_SECONDS
                elif seconds % POLL_SECONDS == 0 and self.client.quick_connect_approved(secret):
                    log("Quick Connect code approved; signing in.")
                    self._finish(self.client.authenticate_with_quick_connect(secret))
                    return
            except JellyfinError as error:
                # Most often the code has expired early; a fresh one fixes that.
                log(f"Quick Connect: {error}; getting a new code.", xbmc.LOGWARNING)
                secret = None
            if secret is not None:
                self._show_countdown(expires_at)
            if monitor.waitForAbort(1):
                return
            seconds += 1

    def _new_code(self):
        started = self.client.initiate_quick_connect()
        code = str(started.get("Code", ""))
        # Shown as two groups of three, which is easier to read across a room: 123 456.
        self.setProperty("code", f"{code[:3]} {code[3:]}" if len(code) == 6 else code)
        self.setProperty("status", "Waiting for approval…")
        return started["Secret"]

    def _show_countdown(self, expires_at):
        """Code expires in 9:42, counting down to when the next code arrives."""
        remaining = max(int(expires_at - time.monotonic()) - REFRESH_BEFORE_EXPIRY_SECONDS, 0)
        minutes, seconds = divmod(remaining, 60)
        self.setProperty("expires", f"Code expires in {minutes}:{seconds:02d}")

    # Helpers ------------------------------------------------------------------------

    def _finish(self, result):
        """Record the outcome and close, once (the screen and the thread can both get here)."""
        if self._stop is not None:
            if self._stop.is_set():
                return
            self._stop.set()
        self.result = result
        self.close()
