"""Short display text built from Jellyfin item details.

This module has no Kodi imports, so it can be tested on a PC.
"""

from resources.lib.api import TICKS_PER_SECOND

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


def media_summary(item):
    """Resolution, HDR format and main audio track, like "4K · Dolby Vision · Dolby TrueHD Atmos 7.1"."""
    sources = item.get("MediaSources") or []
    streams = (sources[0].get("MediaStreams") if sources else None) or item.get("MediaStreams") or []

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


def extra_type_name(extra_type):
    return EXTRA_TYPE_NAMES.get(extra_type or "", "Extra")


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
