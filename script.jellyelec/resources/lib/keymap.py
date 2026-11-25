"""JellyELEC's Kodi key maps.

While video is full-screen, Kodi handles every key press itself and add-ons never see
them. These key maps make the Live TV keys set a property on Kodi's Home window instead,
which the Live TV session watches for (see key_requests.py). They apply to keyboards,
IR and CEC remotes, and to remotes that send keyboard keys over Kodi's network control
(such as the Unfolded Circle Kodi integration's "key" command).

There are two:
  - The main key map is always installed. Guide and the page keys do nothing during
    movies and episodes, since nothing is listening then.
  - The Live TV key map is only installed while a channel is playing, because it takes
    over Up and Down, which skip forward and back in movies.
"""

import os

import xbmc
import xbmcvfs

from resources.lib.key_requests import (
    CHANNEL_DOWN_REQUEST,
    CHANNEL_UP_REQUEST,
    GUIDE_REQUEST,
    REQUEST_PROPERTY,
)
from resources.lib.kodi import log

KEYMAP_PATH = "special://profile/keymaps/jellyelec.xml"
LIVE_TV_KEYMAP_PATH = "special://profile/keymaps/jellyelec-livetv.xml"


def _request(value):
    return f"SetProperty({REQUEST_PROPERTY},{value},home)"


KEYMAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Installed by JellyELEC. Changes here are replaced the next time JellyELEC starts. -->
<keymap>
    <FullscreenVideo>
        <keyboard>
            <g>{_request(GUIDE_REQUEST)}</g>
            <pageup>{_request(CHANNEL_UP_REQUEST)}</pageup>
            <pagedown>{_request(CHANNEL_DOWN_REQUEST)}</pagedown>
        </keyboard>
        <remote>
            <guide>{_request(GUIDE_REQUEST)}</guide>
            <pageplus>{_request(CHANNEL_UP_REQUEST)}</pageplus>
            <pageminus>{_request(CHANNEL_DOWN_REQUEST)}</pageminus>
        </remote>
    </FullscreenVideo>
</keymap>
"""

LIVE_TV_KEYMAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Installed by JellyELEC while Live TV plays, and removed when it stops. -->
<keymap>
    <FullscreenVideo>
        <keyboard>
            <up>{_request(CHANNEL_UP_REQUEST)}</up>
            <down>{_request(CHANNEL_DOWN_REQUEST)}</down>
        </keyboard>
        <remote>
            <up>{_request(CHANNEL_UP_REQUEST)}</up>
            <down>{_request(CHANNEL_DOWN_REQUEST)}</down>
        </remote>
    </FullscreenVideo>
</keymap>
"""


def install_keymap():
    """Write the main key map if it's missing or out of date."""
    _write(KEYMAP_PATH, KEYMAP)


def install_live_tv_keymap():
    """Up and Down change channel, until remove_live_tv_keymap()."""
    _write(LIVE_TV_KEYMAP_PATH, LIVE_TV_KEYMAP)


def remove_live_tv_keymap():
    """Give Up and Down back to Kodi. Also run at startup, in case Live TV didn't end cleanly."""
    path = xbmcvfs.translatePath(LIVE_TV_KEYMAP_PATH)
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
    except OSError as error:
        log(f"Couldn't remove the Live TV key map at {path}: {error}", xbmc.LOGWARNING)
        return
    _reload()
    log("Removed the Live TV key map.")


# Helpers ----------------------------------------------------------------------------

def _write(keymap_path, content):
    """Write a key map unless it's already there as it should be, then have Kodi reload key maps."""
    path = xbmcvfs.translatePath(keymap_path)
    try:
        with open(path, encoding="utf-8") as file:
            if file.read() == content:
                return
    except OSError:
        pass

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
    except OSError as error:
        log(f"Couldn't install the key map at {path}: {error}", xbmc.LOGWARNING)
        return
    _reload()
    log(f"Installed the key map at {path}.")


def _reload():
    xbmc.executebuiltin("Action(reloadkeymaps)")
