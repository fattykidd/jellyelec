"""The Media info panel's contents: one card for the file, then one per video, audio and
subtitle track, much like the Media Info screen in Jellyfin's web app.

This module has no Kodi imports, so it can be tested on a PC.
"""

import os
from collections import namedtuple

from resources.lib.formatting import CHANNEL_LAYOUTS, runtime_text

# One card: a heading ("Audio 2"), a second line (the track's display title) and its details
# as (name, value) pairs.
Card = namedtuple("Card", "heading subheading rows")

# Jellyfin's VideoRangeType values, as people know them.
VIDEO_RANGE_NAMES = {
    "SDR": "SDR",
    "HDR10": "HDR10",
    "HDR10Plus": "HDR10+",
    "HLG": "HLG",
    "DOVI": "Dolby Vision",
    "DOVIWithHDR10": "Dolby Vision with HDR10",
    "DOVIWithHDR10Plus": "Dolby Vision with HDR10+",
    "DOVIWithHLG": "Dolby Vision with HLG",
    "DOVIWithSDR": "Dolby Vision with SDR",
}


def cards(item, source):
    """The cards for one version of an item. Empty if Jellyfin knows nothing about its files."""
    if not source:
        return []
    streams = [stream for stream in source.get("MediaStreams") or [] if stream.get("Type") in STREAM_CARDS]
    totals = {}
    for stream in streams:
        totals[stream["Type"]] = totals.get(stream["Type"], 0) + 1

    # Tracks are numbered (Audio 1, Audio 2) only when there's more than one of a kind.
    result = [_general_card(item, source)]
    counts = {}
    for stream in streams:
        kind = stream["Type"]
        counts[kind] = counts.get(kind, 0) + 1
        number = counts[kind] if totals[kind] > 1 else 0
        result.append(STREAM_CARDS[kind](stream, number))
    return result


# Cards ----------------------------------------------------------------------------------

def _general_card(item, source):
    path = source.get("Path") or ""
    rows = [
        ("Container", (source.get("Container") or "").upper()),
        ("Size", file_size(source.get("Size"))),
        ("Bitrate", bitrate(source.get("Bitrate"))),
        ("Runtime", runtime_text(source["RunTimeTicks"]) if source.get("RunTimeTicks") else ""),
        ("Location", os.path.dirname(path)),
    ]
    return Card("General", os.path.basename(path) or item.get("Name", ""), _filled(rows))


def _video_card(stream, number):
    rows = [
        ("Codec", (stream.get("Codec") or "").upper()),
        ("Profile", stream.get("Profile")),
        ("Level", _level(stream)),
        ("Resolution", _resolution(stream)),
        ("Aspect ratio", stream.get("AspectRatio")),
        ("Frame rate", _frame_rate(stream)),
        ("Bitrate", bitrate(stream.get("BitRate"))),
        ("Bit depth", f"{stream['BitDepth']} bit" if stream.get("BitDepth") else ""),
        ("Video range", VIDEO_RANGE_NAMES.get(stream.get("VideoRangeType"), stream.get("VideoRangeType"))),
        ("Dolby Vision", _dolby_vision(stream)),
        ("Colour space", stream.get("ColorSpace")),
        ("Colour transfer", stream.get("ColorTransfer")),
        ("Colour primaries", stream.get("ColorPrimaries")),
        ("Pixel format", stream.get("PixelFormat")),
        ("Interlaced", "Yes" if stream.get("IsInterlaced") else ""),
    ]
    return Card(_numbered("Video", number), stream.get("DisplayTitle") or "", _filled(rows))


def _audio_card(stream, number):
    channels = stream.get("Channels")
    rows = [
        ("Language", _language(stream)),
        ("Codec", (stream.get("Codec") or "").upper()),
        ("Profile", stream.get("Profile")),
        ("Layout", stream.get("ChannelLayout") or CHANNEL_LAYOUTS.get(channels, "")),
        ("Channels", f"{channels} ch" if channels else ""),
        ("Bitrate", bitrate(stream.get("BitRate"))),
        ("Sample rate", f"{stream['SampleRate']:,} Hz" if stream.get("SampleRate") else ""),
        ("Bit depth", f"{stream['BitDepth']} bit" if stream.get("BitDepth") else ""),
        ("Default", "Yes" if stream.get("IsDefault") else ""),
    ]
    return Card(_numbered("Audio", number), stream.get("DisplayTitle") or "", _filled(rows))


def _subtitle_card(stream, number):
    rows = [
        ("Language", _language(stream)),
        ("Title", stream.get("Title")),
        ("Codec", (stream.get("Codec") or "").upper()),
        ("Default", "Yes" if stream.get("IsDefault") else ""),
        ("Forced", "Yes" if stream.get("IsForced") else ""),
        ("Hearing impaired", "Yes" if stream.get("IsHearingImpaired") else ""),
        ("External", "Yes" if stream.get("IsExternal") else ""),
    ]
    return Card(_numbered("Subtitles", number), stream.get("DisplayTitle") or "", _filled(rows))


STREAM_CARDS = {"Video": _video_card, "Audio": _audio_card, "Subtitle": _subtitle_card}


# Values -----------------------------------------------------------------------------

def file_size(size):
    """58.3 GB, or 700 MB."""
    if not size:
        return ""
    if size >= 1000 ** 3:
        return f"{size / 1000 ** 3:.1f} GB"
    return f"{size / 1000 ** 2:.0f} MB"


def bitrate(bits_per_second):
    """48.2 Mbps, or 640 kbps."""
    if not bits_per_second:
        return ""
    if bits_per_second >= 1_000_000:
        return f"{bits_per_second / 1_000_000:.1f} Mbps"
    return f"{bits_per_second / 1000:.0f} kbps"


def _numbered(kind, number):
    return f"{kind} {number}" if number else kind


def _filled(rows):
    """Leave out details Jellyfin didn't give."""
    return [(name, str(value)) for name, value in rows if value not in (None, "", 0)]


def _level(stream):
    level = stream.get("Level")
    if not level:
        return ""
    # HEVC levels come as 150 for 5.0; H.264 as 41 for 4.1.
    if (stream.get("Codec") or "").lower() in ("hevc", "h265"):
        return f"{level / 30:.1f}"
    return f"{level / 10:.1f}" if level >= 10 else str(level)


def _resolution(stream):
    if stream.get("Width") and stream.get("Height"):
        return f"{stream['Width']} × {stream['Height']}"
    return ""


def _frame_rate(stream):
    rate = stream.get("RealFrameRate") or stream.get("AverageFrameRate")
    if not rate:
        return ""
    return f"{rate:.3f}".rstrip("0").rstrip(".") + " fps"


def _dolby_vision(stream):
    """Profile 8.1, level 6, with RPU and BL: Dolby Vision's details, when it's there."""
    profile = stream.get("DvProfile")
    if not profile:
        return ""
    parts = [f"Profile {profile}"]
    compatibility = stream.get("DvBlSignalCompatibilityId")
    if compatibility:
        parts[0] += f".{compatibility}"
    if stream.get("DvLevel"):
        parts.append(f"level {stream['DvLevel']}")
    layers = [name for name, key in (("RPU", "RpuPresentFlag"), ("EL", "ElPresentFlag"), ("BL", "BlPresentFlag"))
              if stream.get(key)]
    if layers:
        parts.append(" ".join(layers))
    return ",  ".join(parts)


def _language(stream):
    return stream.get("DisplayLanguage") or (stream.get("Language") or "").upper()
