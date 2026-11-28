"""Appliance mode: JellyELEC opens when the box starts and reopens if it ever closes.

A small background service (service.py) watches a flag that JellyELEC sets on Kodi's home
window while it's running. When the flag goes away, the service opens JellyELEC again.

"Exit to Kodi" in Settings sets a second flag that pauses this until the next restart, so
Kodi's own menus can be reached for maintenance.
"""

import time

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib.kodi import ADDON_ID, log

APPLIANCE_SETTING = "appliance_mode"

# Flags kept on Kodi's home window, which every add-on can see and which clear on restart.
HOME_WINDOW_ID = 10000
RUNNING_PROPERTY = "script.jellyelec.running"
MAINTENANCE_PROPERTY = "script.jellyelec.maintenance"

# Set by the startup screen in JellyELEC images (resources/skin_patch/Startup.xml). That screen shows
# the JellyELEC splash and stays up, instead of going on to Kodi's home screen; JellyELEC
# opens over it, and this service moves on to the home screen when Kodi's menus are wanted.
STARTUP_SCREEN_PROPERTY = "jellyelec.startup_screen"

STARTUP_CHECK_SECONDS = 0.25
CHECK_SECONDS = 2
# How long JellyELEC must have been closed before it's opened again.
REOPEN_AFTER_SECONDS = 4
# After opening it, how long to give it to start before trying again.
STARTUP_GRACE_SECONDS = 20


def is_enabled():
    return xbmcaddon.Addon().getSettingBool(APPLIANCE_SETTING)


def set_enabled(enabled):
    xbmcaddon.Addon().setSettingBool(APPLIANCE_SETTING, enabled)


def mark_running(running):
    """Called by JellyELEC as it starts and stops. Starting also ends maintenance."""
    home = xbmcgui.Window(HOME_WINDOW_ID)
    if running:
        home.setProperty(RUNNING_PROPERTY, "true")
        home.clearProperty(MAINTENANCE_PROPERTY)
    else:
        home.clearProperty(RUNNING_PROPERTY)


def leave_for_maintenance():
    """Stop reopening JellyELEC until the next restart, or until it's opened by hand."""
    xbmcgui.Window(HOME_WINDOW_ID).setProperty(MAINTENANCE_PROPERTY, "true")
    log("Exiting to Kodi for maintenance; JellyELEC won't reopen until the next restart.")


def run_service():
    """The background service: open JellyELEC at startup, and again whenever it closes."""
    monitor = xbmc.Monitor()

    # Wait for Kodi to finish starting: its home screen, or the JellyELEC startup screen.
    # Checked often, so JellyELEC covers the home screen as soon as it appears.
    while not (xbmc.getCondVisibility("Window.IsActive(home)") or _on_startup_screen()):
        if monitor.waitForAbort(STARTUP_CHECK_SECONDS):
            return

    open_at = time.monotonic()  # straight away at startup
    while not monitor.abortRequested():
        now = time.monotonic()
        if not _is_running() and not _should_reopen() and _on_startup_screen():
            # Kodi's menus are wanted (appliance mode off, or Exit to Kodi): leave the splash.
            xbmc.executebuiltin("ReplaceWindow(home)")
        if _is_running() or not _should_reopen():
            open_at = now + REOPEN_AFTER_SECONDS
        elif now >= open_at:
            log("Appliance mode: opening JellyELEC.")
            xbmc.executebuiltin(f"RunScript({ADDON_ID})")
            open_at = now + STARTUP_GRACE_SECONDS
        if monitor.waitForAbort(CHECK_SECONDS):
            return


def _on_startup_screen():
    """True while the JellyELEC startup screen is showing (only in JellyELEC images)."""
    if not xbmcgui.Window(HOME_WINDOW_ID).getProperty(STARTUP_SCREEN_PROPERTY):
        return False
    return xbmc.getCondVisibility("Window.IsActive(startup)")


def _is_running():
    return bool(xbmcgui.Window(HOME_WINDOW_ID).getProperty(RUNNING_PROPERTY))


def _should_reopen():
    return is_enabled() and not xbmcgui.Window(HOME_WINDOW_ID).getProperty(MAINTENANCE_PROPERTY)
