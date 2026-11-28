"""Turn Jellyfin items into Kodi ListItems that the screens can display."""

import xbmcgui

from resources.lib.api import TICKS_PER_SECOND
from resources.lib.formatting import (
    clock_text,
    elapsed_and_length,
    extra_type_name,
    initials,
    parse_date,
    remaining_ticks,
    runtime_text,
    spotlight_meta,
    time_range_text,
    unwatched_text,
    watch_status,
)

POSTER_HEIGHT = 450
BACKDROP_WIDTH = 1280
# Landscape cards (Continue Watching, Next Up) are 384x216 on screen; twice that keeps them sharp.
CARD_WIDTH = 768
EXTRA_THUMB_WIDTH = 480
EPISODE_THUMB_WIDTH = 480
CHANNEL_LOGO_WIDTH = 300
LOGO_WIDTH = 720
# Cast headshots are 180px circles on screen.
HEADSHOT_WIDTH = 360

# Item types that are played in one go (not shows or collections).
PLAYABLE_TYPES = ("Movie", "Episode", "Video", "MusicVideo")


def media_item(client, data):
    """A movie, show, episode or collection, with artwork and basic details."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])
    item.setProperty("type", data.get("Type", ""))

    art = {
        "poster": poster_url(client, data),
        "fanart": backdrop_url(client, data),
        "clearlogo": logo_url(client, data),
        "landscape": card_url(client, data),
    }
    item.setArt({kind: url for kind, url in art.items() if url})
    # Year, age rating, runtime and community rating, for screens that show the focused item.
    item.setProperty("meta", spotlight_meta(data))
    # How long is left to watch, for Ends at; only for things that are played in one go.
    if data.get("Type") in PLAYABLE_TYPES:
        item.setProperty("remaining_seconds", str(remaining_ticks(data) // TICKS_PER_SECOND))
    # The two lines under a landscape card.
    title, subtitle = card_lines(data)
    item.setProperty("card_title", title)
    item.setProperty("card_subtitle", subtitle)

    tag = item.getVideoInfoTag()
    tag.setTitle(data.get("Name", ""))
    tag.setPlot(data.get("Overview", ""))
    if data.get("ProductionYear"):
        tag.setYear(int(data["ProductionYear"]))
    if data.get("RunTimeTicks"):
        tag.setDuration(int(data["RunTimeTicks"] // TICKS_PER_SECOND))
        position = (data.get("UserData") or {}).get("PlaybackPositionTicks") or 0
        if position:
            # Shown as the progress bar on landscape cards (ListItem.PercentPlayed).
            tag.setResumePoint(position / TICKS_PER_SECOND, data["RunTimeTicks"] / TICKS_PER_SECOND)

    if data.get("Type") == "Series":
        tag.setMediaType("tvshow")
    elif data.get("Type") == "BoxSet":
        tag.setMediaType("set")
    elif data.get("Type") == "Episode":
        tag.setMediaType("episode")
        tag.setTvShowTitle(data.get("SeriesName", ""))
        if data.get("ParentIndexNumber") is not None:
            tag.setSeason(int(data["ParentIndexNumber"]))
        if data.get("IndexNumber") is not None:
            tag.setEpisode(int(data["IndexNumber"]))
    else:
        tag.setMediaType("movie")

    return item


def extra_item(client, data, fallback_thumb=None):
    """A special feature tile: its own image if it has one, otherwise the parent's backdrop."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])
    item.setProperty("extra_type", extra_type_name(data.get("ExtraType")))
    if data.get("RunTimeTicks"):
        item.setProperty("runtime", runtime_text(data["RunTimeTicks"]))

    tag = data.get("ImageTags", {}).get("Primary")
    thumb = client.image_url(data["Id"], "Primary", tag, max_width=EXTRA_THUMB_WIDTH) if tag else fallback_thumb
    if thumb:
        item.setArt({"thumb": thumb})
    return item


def person_item(client, person):
    """A cast or crew member: headshot, name, and their role (or job, for crew)."""
    name = person.get("Name", "")
    item = xbmcgui.ListItem(label=name, offscreen=True)
    item.setProperty("id", person.get("Id", ""))
    item.setProperty("initials", initials(name))
    if person.get("Type") in ("Actor", "GuestStar"):
        item.setProperty("role", person.get("Role") or "")
    else:
        item.setProperty("role", person.get("Type", ""))
    tag = person.get("PrimaryImageTag")
    if tag and person.get("Id"):
        item.setArt({"thumb": client.image_url(person["Id"], "Primary", tag, max_width=HEADSHOT_WIDTH)})
    return item


def season_item(client, data):
    """A season poster with its unwatched count."""
    item = xbmcgui.ListItem(label=data.get("Name", ""), offscreen=True)
    item.setProperty("id", data["Id"])
    item.setProperty("unwatched", unwatched_text(data))
    poster = poster_url(client, data)
    if poster:
        item.setArt({"poster": poster})
    return item


def episode_item(client, data):
    """An episode for the episode list: numbered title, its own picture, and watch status."""
    item = media_item(client, data)
    number = data.get("IndexNumber")
    item.setLabel(f"{number}. {data.get('Name', '')}" if number is not None else data.get("Name", ""))
    item.setProperty("status", watch_status(data))
    if data.get("RunTimeTicks"):
        item.setProperty("runtime", runtime_text(data["RunTimeTicks"]))
    thumb = episode_thumb_url(client, data)
    if thumb:
        item.setArt({"thumb": thumb})
    return item


def channel_item(client, channel, next_program, now):
    """A Live TV channel: logo, number, name, what's on now (with progress) and what's next."""
    item = xbmcgui.ListItem(label=channel.get("Name", ""), offscreen=True)
    item.setProperty("id", channel["Id"])
    item.setProperty("number", channel.get("Number") or channel.get("ChannelNumber") or "")

    logo_tag = channel.get("ImageTags", {}).get("Primary")
    if logo_tag:
        item.setArt({"thumb": client.image_url(channel["Id"], "Primary", logo_tag, max_width=CHANNEL_LOGO_WIDTH)})

    current = channel.get("CurrentProgram") or {}
    start, end = parse_date(current.get("StartDate")), parse_date(current.get("EndDate"))
    item.setProperty("now_title", current.get("Name", ""))
    item.setProperty("now_time", time_range_text(start, end))

    # The progress bar reads the resume point, as Kodi does for partly watched videos.
    elapsed, length = elapsed_and_length(start, end, now)
    tag = item.getVideoInfoTag()
    tag.setTitle(current.get("Name") or channel.get("Name", ""))
    if length:
        tag.setResumePoint(elapsed, length)

    if next_program:
        item.setProperty("next_title", next_program.get("Name", ""))
        next_start = parse_date(next_program.get("StartDate"))
        item.setProperty("next_time", clock_text(next_start) if next_start else "")
    return item


def poster_url(client, data):
    """Episodes use their show's poster; seasons without their own fall back to it too."""
    series_poster = None
    if data.get("SeriesId") and data.get("SeriesPrimaryImageTag"):
        series_poster = client.image_url(
            data["SeriesId"], "Primary", data["SeriesPrimaryImageTag"], max_height=POSTER_HEIGHT
        )
    if data.get("Type") == "Episode" and series_poster:
        return series_poster

    tag = data.get("ImageTags", {}).get("Primary")
    if tag:
        return client.image_url(data["Id"], "Primary", tag, max_height=POSTER_HEIGHT)
    return series_poster


def card_url(client, data):
    """A landscape picture for a card: an episode's still, a title's own thumb, or its backdrop."""
    if data.get("Type") == "Episode":
        return episode_thumb_url(client, data)
    tag = data.get("ImageTags", {}).get("Thumb")
    if tag:
        return client.image_url(data["Id"], "Thumb", tag, max_width=CARD_WIDTH)
    return backdrop_url(client, data)


def card_lines(data):
    """The title and second line under a landscape card.

    An episode: its show, then "S1 E3 · Episode name". A show or collection: its name, then
    how many episodes are unwatched (or its year). Anything else: its name, then how long is
    left (once started) or how long it runs.
    """
    if data.get("Type") == "Episode":
        numbers = []
        if data.get("ParentIndexNumber") is not None:
            numbers.append(f"S{data['ParentIndexNumber']}")
        if data.get("IndexNumber") is not None:
            numbers.append(f"E{data['IndexNumber']}")
        parts = [" ".join(numbers), data.get("Name", "")]
        return data.get("SeriesName", ""), "  ·  ".join(part for part in parts if part)
    if data.get("Type") in ("Series", "BoxSet"):
        # A show (Recently Added groups new episodes under it) or a collection.
        return data.get("Name", ""), unwatched_text(data) or str(data.get("ProductionYear") or "")
    remaining = remaining_ticks(data)
    runtime = data.get("RunTimeTicks") or 0
    if remaining and remaining < runtime:
        return data.get("Name", ""), f"{runtime_text(remaining)} left"
    return data.get("Name", ""), runtime_text(runtime) if runtime else ""


def episode_thumb_url(client, data):
    """An episode's own still image, falling back to its show's backdrop."""
    tag = data.get("ImageTags", {}).get("Primary")
    if tag:
        return client.image_url(data["Id"], "Primary", tag, max_width=EPISODE_THUMB_WIDTH)
    return backdrop_url(client, data)


def backdrop_url(client, data):
    """The item's own backdrop, or its parent's (an episode borrows its show's)."""
    if data.get("BackdropImageTags"):
        return client.image_url(
            data["Id"], "Backdrop", data["BackdropImageTags"][0], max_width=BACKDROP_WIDTH
        )
    if data.get("ParentBackdropImageTags") and data.get("ParentBackdropItemId"):
        return client.image_url(
            data["ParentBackdropItemId"],
            "Backdrop",
            data["ParentBackdropImageTags"][0],
            max_width=BACKDROP_WIDTH,
        )
    return None


def logo_url(client, data):
    """The title's clearlogo, or its show's for an episode. None if it has none."""
    tag = data.get("ImageTags", {}).get("Logo")
    if tag:
        return client.image_url(data["Id"], "Logo", tag, max_width=LOGO_WIDTH)
    if data.get("ParentLogoItemId") and data.get("ParentLogoImageTag"):
        return client.image_url(
            data["ParentLogoItemId"], "Logo", data["ParentLogoImageTag"], max_width=LOGO_WIDTH
        )
    return None
