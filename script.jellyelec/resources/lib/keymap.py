"""JellyELEC's Kodi key map.

While video is full-screen, Kodi handles every key press itself and add-ons never see
them. This key map makes the Live TV keys set a property on Kodi's Home window instead,
which the Live TV session watches for (see key_requests.py). It applies to keyboards,
IR and CEC remotes, and to remotes that send keyboard keys over Kodi's network control
(such as the Unfolded Circle Kodi integration's "key" command).

The keys do nothing during movies and episodes, since nothing is listening then.
"""

import os

import xbmc
import xbmcvfs

from resources.lib.kodi import log
from resources.lib.key_requests import (
    CHANNEL_DOWN_REQUEST,
    CHANNEL_UP_REQUEST,
    GUIDE_REQUEST,
    REQUEST_PROPERTY,
)

KEYMAP_PATH = "special://profile/keymaps/jellyelec.xml"


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


def install_keymap():
    """Write the key map if it's missing or out of date, then have Kodi reload its key maps."""
    path = xbmcvfs.translatePath(KEYMAP_PATH)
    try:
        with open(path, encoding="utf-8") as file:
            if file.read() == KEYMAP:
                return
    except OSError:
        pass

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(KEYMAP)
    except OSError as error:
        log(f"Couldn't install the key map at {path}: {error}", xbmc.LOGWARNING)
        return
    xbmc.executebuiltin("Action(reloadkeymaps)")
    log(f"Installed the key map at {path}.")
