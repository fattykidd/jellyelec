"""Key presses during full-screen video, passed from JellyELEC's key map to its players.

While video is full-screen, Kodi handles every key itself and add-ons never see them.
JellyELEC's key map (keymap.py) turns the keys it cares about into a property on Kodi's
home window instead, and whichever JellyELEC player is running picks it up from there:
live_playback.py for Live TV.
"""

import xbmcgui

from resources.lib.kodi import ADDON_ID

HOME_WINDOW_ID = 10000
REQUEST_PROPERTY = f"{ADDON_ID}.request"

# The property's possible values.
GUIDE_REQUEST = "guide"
CHANNEL_UP_REQUEST = "channelup"
CHANNEL_DOWN_REQUEST = "channeldown"


def take_request():
    """The key waiting to be handled, or "" if none. Taking it clears it."""
    home = xbmcgui.Window(HOME_WINDOW_ID)
    request = home.getProperty(REQUEST_PROPERTY)
    if request:
        home.clearProperty(REQUEST_PROPERTY)
    return request


def clear_requests():
    """Forget any key left over from before, so it isn't acted on by the next player."""
    xbmcgui.Window(HOME_WINDOW_ID).clearProperty(REQUEST_PROPERTY)
