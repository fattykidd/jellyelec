"""Hands Kodi a Live TV channel's stream when that channel is played.

Kodi runs this (through plugin.py) each time it reaches a channel in the Live TV playlist,
for example when the user presses Next or Previous. It runs separately from the rest of
JellyELEC, so it signs in from the saved connection rather than sharing a client.
"""

import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import storage
from resources.lib.kodi import log
from resources.lib.live_playback import prepare_live_item, remember_tuned_stream, resolve_channel_stream
from resources.lib.session import make_client


def run(argv):
    """argv is Kodi's plugin call: [address, handle, "?channel=...&name=..."]."""
    handle = int(argv[1])
    params = dict(urllib.parse.parse_qsl(argv[2].lstrip("?")))
    channel = {"Id": params.get("channel", ""), "Name": params.get("name", "")}

    connection = storage.load()
    if not channel["Id"] or not connection.signed_in:
        log("Live TV: asked to play a channel without a channel ID or a sign-in.", xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem(offscreen=True))
        return

    url, live_stream_id, container = resolve_channel_stream(make_client(connection), channel)
    if live_stream_id:
        remember_tuned_stream(live_stream_id)

    item = xbmcgui.ListItem(path=url or "", offscreen=True)
    if url:
        prepare_live_item(item, container)
    xbmcplugin.setResolvedUrl(handle, bool(url), item)
