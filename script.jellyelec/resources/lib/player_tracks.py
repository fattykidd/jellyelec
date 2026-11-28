"""Picking the audio track and subtitles of what's playing, from the OSD's Audio and
Subtitles buttons.

Kodi says which tracks the file has, and switches between them (through JSON-RPC). The names
come from Jellyfin when it describes the same tracks, as "English - Dolby TrueHD + Dolby Atmos
7.1 - Default"; otherwise from what Kodi knows (language, codec, channels).
"""

from resources.lib import picker
from resources.lib.jsonrpc import JsonRpcError, call
from resources.lib.kodi import log

CHANNEL_NAMES = {1: "Mono", 2: "Stereo", 6: "5.1", 8: "7.1"}


def choose_audio(source=None):
    """Show the audio tracks and switch to the one picked. source: the Jellyfin media source
    playing, for its track names (None for Live TV)."""
    player_id = _video_player()
    if player_id is None:
        return
    properties = call("Player.GetProperties", playerid=player_id,
                      properties=["audiostreams", "currentaudiostream"])
    streams = properties.get("audiostreams") or []
    if not streams:
        return
    names = _jellyfin_names(source, "Audio", len(streams))
    options = [
        (names[number] if names else _kodi_audio_name(stream), "" if names else _kodi_audio_detail(stream))
        for number, stream in enumerate(streams)
    ]
    current_index = (properties.get("currentaudiostream") or {}).get("index")
    current = next((number for number, stream in enumerate(streams) if stream["index"] == current_index), -1)

    choice = picker.choose("Audio", options, current)
    if choice is None or choice == current:
        return
    _call("Player.SetAudioStream", playerid=player_id, stream=streams[choice]["index"])
    log(f"Audio track: {options[choice][0]}")


def choose_subtitles(source=None):
    """Show Off and the subtitle tracks, and switch to the one picked."""
    player_id = _video_player()
    if player_id is None:
        return
    properties = call("Player.GetProperties", playerid=player_id,
                      properties=["subtitles", "currentsubtitle", "subtitleenabled"])
    streams = properties.get("subtitles") or []
    names = _jellyfin_names(source, "Subtitle", len(streams))
    options = [("Off", "")] + [
        (names[number] if names else _kodi_subtitle_name(stream), "" if names else _kodi_subtitle_detail(stream))
        for number, stream in enumerate(streams)
    ]
    current = 0
    if properties.get("subtitleenabled"):
        current_index = (properties.get("currentsubtitle") or {}).get("index")
        current = next((number + 1 for number, stream in enumerate(streams) if stream["index"] == current_index), 0)

    choice = picker.choose("Subtitles", options, current)
    if choice is None or choice == current:
        return
    if choice == 0:
        _call("Player.SetSubtitle", playerid=player_id, subtitle="off")
    else:
        _call("Player.SetSubtitle", playerid=player_id, subtitle=streams[choice - 1]["index"], enable=True)
    log(f"Subtitles: {options[choice][0]}")


# Helpers ----------------------------------------------------------------------------

def _video_player():
    """Kodi's ID for the video player, or None if no video is playing."""
    for player in call("Player.GetActivePlayers") or []:
        if player.get("type") == "video":
            return player["playerid"]
    return None


def _call(method, **params):
    try:
        call(method, **params)
    except JsonRpcError as error:
        log(f"Couldn't switch tracks: {error}")


def _jellyfin_names(source, kind, count):
    """Jellyfin's names for the file's tracks of one kind, if it lists the same number Kodi
    does (then they're the same tracks, in the same order). Otherwise None."""
    if not source:
        return None
    tracks = [
        stream for stream in source.get("MediaStreams") or []
        if stream.get("Type") == kind and not stream.get("IsExternal")
    ]
    if len(tracks) != count:
        return None
    return [stream.get("DisplayTitle") or stream.get("Language") or f"Track {number + 1}"
            for number, stream in enumerate(tracks)]


def _kodi_audio_name(stream):
    return stream.get("name") or _language(stream) or f"Track {stream.get('index', 0) + 1}"


def _kodi_audio_detail(stream):
    parts = [(stream.get("codec") or "").upper(), CHANNEL_NAMES.get(stream.get("channels"), "")]
    if stream.get("name"):
        parts.insert(0, _language(stream))
    return "  ·  ".join(part for part in parts if part)


def _kodi_subtitle_name(stream):
    return stream.get("name") or _language(stream) or f"Subtitle {stream.get('index', 0) + 1}"


def _kodi_subtitle_detail(stream):
    flags = [name for name, key in (("Forced", "isforced"), ("Default", "isdefault"),
                                    ("Hearing impaired", "isimpaired")) if stream.get(key)]
    parts = ([_language(stream)] if stream.get("name") else []) + flags
    return "  ·  ".join(part for part in parts if part)


def _language(stream):
    return (stream.get("language") or "").upper()
