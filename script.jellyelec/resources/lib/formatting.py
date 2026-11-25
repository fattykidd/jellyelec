"""Short display text built from Jellyfin item details.

This module has no Kodi imports, so it can be tested on a PC.
"""

import re
from datetime import datetime

from resources.lib.api import TICKS_PER_SECOND

# Jellyfin dates look like 2026-11-23T18:00:00.0000000Z (seven decimal places, UTC).
_JELLYFIN_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?$")

EXTRA_TYPE_NAMES = {
    "BehindTheScenes": "Behind the scenes",
    "Clip": "Clip",
    "DeletedScene": "Deleted scene",
    "Featurette": "Featurette",
    "Interview": "Interview",
    "Sample": "Sample",
    "Scene": "Scene",
    "Short": "Short",
    "ThemeSong": "Theme song",
    "ThemeVideo": "Theme video",
    "Trailer": "Trailer",
}

AUDIO_CODEC_NAMES = {
    "aac": "AAC",
    "ac3": "Dolby Digital",
    "dts": "DTS",
    "eac3": "Dolby Digital+",
    "flac": "FLAC",
    "mp3": "MP3",
    "opus": "Opus",
    "truehd": "Dolby TrueHD",
}

CHANNEL_LAYOUTS = {1: "Mono", 2: "Stereo", 6: "5.1", 8: "7.1"}


def format_time(seconds):
    """1:02:03, or 2:03 when under an hour."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def runtime_text(ticks):
    """2h 46m, or 46m when under an hour."""
    minutes = round(ticks / TICKS_PER_SECOND / 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def meta_line(item):
    """Year · runtime · age rating · community rating."""
    parts = []
    if item.get("ProductionYear"):
        parts.append(str(item["ProductionYear"]))
    if item.get("RunTimeTicks"):
        parts.append(runtime_text(item["RunTimeTicks"]))
    if item.get("OfficialRating"):
        parts.append(item["OfficialRating"])
    if item.get("CommunityRating"):
        parts.append(f"★ {item['CommunityRating']:.1f}")
    return "  ·  ".join(parts)


def episode_line(item):
    """Season 1 · Episode 2, for episodes only."""
    if item.get("Type") != "Episode":
        return ""
    parts = []
    if item.get("ParentIndexNumber") is not None:
        parts.append(f"Season {item['ParentIndexNumber']}")
    if item.get("IndexNumber") is not None:
        parts.append(f"Episode {item['IndexNumber']}")
    return "  ·  ".join(parts)


def media_summary(item, source=None):
    """Resolution, HDR format and main audio track, like "4K · Dolby Vision · Dolby TrueHD Atmos 7.1".

    source: which version to describe. Leave it out for the first.
    """
    if source is None:
        sources = item.get("MediaSources") or []
        source = sources[0] if sources else None
    streams = (source.get("MediaStreams") if source else None) or item.get("MediaStreams") or []

    video = next((stream for stream in streams if stream.get("Type") == "Video"), None)
    audio_streams = [stream for stream in streams if stream.get("Type") == "Audio"]
    audio = next((stream for stream in audio_streams if stream.get("IsDefault")), None)
    audio = audio or (audio_streams[0] if audio_streams else None)

    parts = []
    if video:
        parts.append(_resolution(video))
        dynamic_range = _dynamic_range(video)
        if dynamic_range:
            parts.append(dynamic_range)
    if audio:
        parts.append(_audio(audio))
    return "  ·  ".join(part for part in parts if part)


def watch_status(item):
    """Watched, 45% watched, or nothing."""
    user_data = item.get("UserData") or {}
    if user_data.get("Played"):
        return "Watched"
    if user_data.get("PlaybackPositionTicks") and user_data.get("PlayedPercentage"):
        return f"{round(user_data['PlayedPercentage'])}% watched"
    return ""


def unwatched_text(item):
    """3 unwatched, for a season or show."""
    count = (item.get("UserData") or {}).get("UnplayedItemCount") or 0
    return f"{count} unwatched" if count else ""


def extra_type_name(extra_type):
    return EXTRA_TYPE_NAMES.get(extra_type or "", "Extra")


# Live TV times ----------------------------------------------------------------------

def parse_date(text):
    """A Jellyfin date as a timezone-aware datetime, or None if it can't be read."""
    match = _JELLYFIN_DATE.match(text or "")
    if not match:
        return None
    base, offset = match.groups()
    if not offset or offset == "Z":
        offset = "+00:00"
    return datetime.fromisoformat(base + offset)


def clock_text(moment):
    """6:05 PM, in the box's local time."""
    local = moment.astimezone()
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def time_range_text(start, end):
    """6:00 PM – 7:00 PM."""
    if not start or not end:
        return ""
    return f"{clock_text(start)} – {clock_text(end)}"


def elapsed_and_length(start, end, now):
    """Seconds into a programme, and its length in seconds. (0, 0) if the times are missing."""
    if not start or not end or end <= start:
        return 0, 0
    length = (end - start).total_seconds()
    elapsed = min(max((now - start).total_seconds(), 0), length)
    return elapsed, length


# Helpers --------------------------------------------------------------------------

def _resolution(video):
    width = video.get("Width") or 0
    height = video.get("Height") or 0
    if width >= 3200 or height >= 2000:
        return "4K"
    if width >= 1900 or height >= 1000:
        return "1080p"
    if width >= 1200 or height >= 700:
        return "720p"
    return "SD" if width or height else ""


def _dynamic_range(video):
    range_type = video.get("VideoRangeType") or ""
    if "DOVI" in range_type:
        return "Dolby Vision"
    if range_type == "HDR10Plus":
        return "HDR10+"
    if range_type in ("HDR10", "HLG"):
        return range_type
    if video.get("VideoRange") == "HDR":
        return "HDR"
    return ""


def _audio(audio):
    codec = (audio.get("Codec") or "").lower()
    profile = audio.get("Profile") or ""

    if "DTS:X" in profile:
        name = "DTS:X"
    elif codec == "dts" and profile.startswith("DTS"):
        name = profile
    elif codec.startswith("pcm"):
        name = "PCM"
    else:
        name = AUDIO_CODEC_NAMES.get(codec, codec.upper())

    if "Atmos" in profile:
        name += " Atmos"

    layout = (audio.get("ChannelLayout") or "").split("(")[0].strip()
    if not layout:
        layout = CHANNEL_LAYOUTS.get(audio.get("Channels"), "")
    return f"{name} {layout}".strip()
