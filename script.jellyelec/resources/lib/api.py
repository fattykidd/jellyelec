"""A small Jellyfin API client.

This module has no Kodi imports, so it can be tested on a PC.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

CLIENT_NAME = "JellyELEC"
REQUEST_TIMEOUT = 10

# Jellyfin measures time in ticks of 100 nanoseconds.
TICKS_PER_SECOND = 10_000_000


class JellyfinError(Exception):
    """Something went wrong talking to the server."""


class ServerUnreachable(JellyfinError):
    """The server could not be reached at all."""


class AuthenticationFailed(JellyfinError):
    """The server rejected the username and password, or the saved token."""


def normalize_server_url(text):
    """Turn what the user typed into a clean server URL.

    "192.168.1.10:8096" becomes "http://192.168.1.10:8096".
    """
    url = text.strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


class JellyfinClient:
    """Talks to one Jellyfin server on behalf of one device."""

    def __init__(self, server_url, device_id, device_name, version, token="", user_id=""):
        self.server_url = normalize_server_url(server_url)
        self.device_id = device_id
        self.device_name = device_name
        self.version = version
        self.token = token
        self.user_id = user_id

    # Server -----------------------------------------------------------------

    def get_public_info(self):
        """Basic server details. Works without signing in."""
        return self._request("GET", "/System/Info/Public")

    # Users ------------------------------------------------------------------

    def authenticate(self, username, password):
        """Sign in and keep the access token for later requests."""
        result = self._request(
            "POST",
            "/Users/AuthenticateByName",
            body={"Username": username, "Pw": password},
        )
        self.token = result["AccessToken"]
        self.user_id = result["User"]["Id"]
        return result["User"]

    def quick_connect_enabled(self):
        """Whether the server allows signing in with a Quick Connect code."""
        try:
            return bool(self._request("GET", "/QuickConnect/Enabled"))
        except JellyfinError:
            return False

    def initiate_quick_connect(self):
        """Start a Quick Connect sign-in. Returns the code to show and the secret to check with."""
        return self._request("POST", "/QuickConnect/Initiate")

    def quick_connect_approved(self, secret):
        """True once someone has approved this Quick Connect code."""
        query = urllib.parse.urlencode({"secret": secret})
        return bool(self._request("GET", f"/QuickConnect/Connect?{query}").get("Authenticated"))

    def authenticate_with_quick_connect(self, secret):
        """Finish an approved Quick Connect sign-in and keep the access token."""
        result = self._request(
            "POST", "/Users/AuthenticateWithQuickConnect", body={"Secret": secret}
        )
        self.token = result["AccessToken"]
        self.user_id = result["User"]["Id"]
        return result["User"]

    def get_current_user(self):
        """The signed-in user. Fails with AuthenticationFailed if the token is no longer valid."""
        return self._request("GET", "/Users/Me")

    # Libraries and items ----------------------------------------------------

    def get_libraries(self):
        """The signed-in user's libraries (Movies, TV shows, and so on)."""
        return self._request("GET", f"/Users/{self.user_id}/Views")["Items"]

    def get_resume_items(self, library_id, limit=24):
        """Partly watched movies and episodes in one library, most recent first."""
        query = urllib.parse.urlencode({
            "ParentId": library_id,
            "Limit": limit,
            "MediaTypes": "Video",
            "Fields": "Overview",
            "ImageTypeLimit": 1,
            "EnableImageTypes": "Primary,Backdrop,Logo,Thumb",
        })
        return self._request("GET", f"/Users/{self.user_id}/Items/Resume?{query}")["Items"]

    def get_latest_items(self, library_id, limit=24):
        """Most recently added items in one library. New episodes are grouped under their show."""
        query = urllib.parse.urlencode({
            "ParentId": library_id,
            "Limit": limit,
            "GroupItems": "true",
            "Fields": "Overview",
            "ImageTypeLimit": 1,
            "EnableImageTypes": "Primary,Backdrop,Logo,Thumb",
        })
        return self._request("GET", f"/Users/{self.user_id}/Items/Latest?{query}") or []

    def get_random_items(self, library_id, item_type, limit=24):
        """A random selection of movies or shows from one library."""
        return self._get_items(library_id, item_type, sort_by="Random", limit=limit)

    def get_library_items(self, library_id, item_type, group_collections=False):
        """Every movie or show in one library, A to Z.

        group_collections: show each collection once in place of the movies in it.
        """
        extra = {"CollapseBoxSetItems": "true" if group_collections else "false"}
        return self._get_items(library_id, item_type, sort_by="SortName", extra=extra)

    def get_collection_items(self, collection_id):
        """The movies (or shows) in a collection, in release order."""
        return self._get_items(
            collection_id, item_type=None, sort_by="PremiereDate,SortName", recursive=False
        )

    def get_next_up(self, series_id):
        """The next episode to watch in a show, or None if there isn't one."""
        items = self._get_shows_items("/Shows/NextUp", SeriesId=series_id, Limit=1)
        return items[0] if items else None

    def get_next_up_items(self, library_id, limit=24):
        """The next episode to watch in each show you're partway through, in one library."""
        return self._get_shows_items("/Shows/NextUp", ParentId=library_id, Limit=limit)

    def get_seasons(self, series_id):
        """A show's seasons, with how many episodes in each are unwatched."""
        return self._get_shows_items(f"/Shows/{series_id}/Seasons")

    def get_episodes(self, series_id, season_id):
        """Every episode in one season, in order."""
        return self._get_shows_items(f"/Shows/{series_id}/Episodes", SeasonId=season_id)

    def get_first_episode(self, series_id):
        """The show's first episode, or None if it has none."""
        items = self._get_shows_items(f"/Shows/{series_id}/Episodes", Limit=1)
        return items[0] if items else None

    def get_item(self, item_id):
        """Full details of one item, including its files and their audio and video tracks."""
        return self._request("GET", f"/Users/{self.user_id}/Items/{item_id}")

    def get_special_features(self, item_id):
        """The item's extras: behind the scenes, deleted scenes, featurettes and so on."""
        return self._request("GET", f"/Users/{self.user_id}/Items/{item_id}/SpecialFeatures") or []

    def get_local_trailers(self, item_id):
        """Trailer files stored alongside the item (not online trailers)."""
        return self._request("GET", f"/Users/{self.user_id}/Items/{item_id}/LocalTrailers") or []

    def get_similar(self, item_id, limit=16):
        """Titles like this one, from the same libraries, as Jellyfin's "More like this" picks them."""
        query = urllib.parse.urlencode({
            "UserId": self.user_id,
            "Limit": limit,
            "Fields": "Overview",
            "ImageTypeLimit": 1,
            "EnableImageTypes": "Primary,Backdrop,Logo,Thumb",
        })
        return (self._request("GET", f"/Items/{item_id}/Similar?{query}") or {}).get("Items", [])

    def set_played(self, item_id, played):
        """Mark an item (or a whole show) watched or unwatched."""
        method = "POST" if played else "DELETE"
        self._user_item_request(method, "UserPlayedItems", "PlayedItems", item_id)

    def set_favorite(self, item_id, favorite):
        """Add an item to your favourites, or take it out."""
        method = "POST" if favorite else "DELETE"
        self._user_item_request(method, "UserFavoriteItems", "FavoriteItems", item_id)

    def image_url(self, item_id, image_type, tag, max_width=None, max_height=None):
        """Address of an item's image, resized by the server. Images don't need sign-in."""
        params = {"tag": tag, "quality": 90}
        if max_width:
            params["maxWidth"] = max_width
        if max_height:
            params["maxHeight"] = max_height
        query = urllib.parse.urlencode(params)
        return f"{self.server_url}/Items/{item_id}/Images/{image_type}?{query}"

    # Playback ---------------------------------------------------------------

    def get_playback_info(self, item_id):
        """The item's media sources (its files) and a play session ID."""
        query = urllib.parse.urlencode({"UserId": self.user_id})
        return self._request("GET", f"/Items/{item_id}/PlaybackInfo?{query}")

    def stream_url(self, item_id, media_source_id, play_session_id, container=None, live_stream_id=None):
        """Address of the original file (or a tuned live channel), sent as-is with no transcoding."""
        extension = f".{container.split(',')[0]}" if container else ""
        params = {
            "static": "true",
            "mediaSourceId": media_source_id,
            "playSessionId": play_session_id,
            "deviceId": self.device_id,
            "api_key": self.token,
        }
        if live_stream_id:
            params["liveStreamId"] = live_stream_id
        query = urllib.parse.urlencode(params)
        return f"{self.server_url}/Videos/{item_id}/stream{extension}?{query}"

    def report_playback_start(self, item_id, media_source_id, play_session_id, position_ticks):
        body = self._playback_report(item_id, media_source_id, play_session_id, position_ticks)
        self._request("POST", "/Sessions/Playing", body=body)

    def report_playback_progress(self, item_id, media_source_id, play_session_id, position_ticks, is_paused):
        body = self._playback_report(
            item_id, media_source_id, play_session_id, position_ticks, is_paused
        )
        self._request("POST", "/Sessions/Playing/Progress", body=body)

    def report_playback_stopped(self, item_id, media_source_id, play_session_id, position_ticks):
        """Saves the position. The server marks the item watched if it was nearly finished."""
        body = self._playback_report(item_id, media_source_id, play_session_id, position_ticks)
        self._request("POST", "/Sessions/Playing/Stopped", body=body)

    def _get_items(self, parent_id, item_type, sort_by, limit=None, recursive=True, extra=None):
        params = {
            "ParentId": parent_id,
            "Recursive": "true" if recursive else "false",
            "SortBy": sort_by,
            "SortOrder": "Ascending",
            "Fields": "Overview",
            "ImageTypeLimit": 1,
            "EnableImageTypes": "Primary,Backdrop,Logo,Thumb",
            **(extra or {}),
        }
        if item_type:
            params["IncludeItemTypes"] = item_type
        if limit:
            params["Limit"] = limit
        query = urllib.parse.urlencode(params)
        return self._request("GET", f"/Users/{self.user_id}/Items?{query}")["Items"]

    def _get_shows_items(self, path, **extra_params):
        params = {
            "UserId": self.user_id,
            "Fields": "Overview",
            "ImageTypeLimit": 1,
            "EnableImageTypes": "Primary,Backdrop,Logo,Thumb",
            **extra_params,
        }
        query = urllib.parse.urlencode(params)
        return self._request("GET", f"{path}?{query}")["Items"]

    def _user_item_request(self, method, path, old_path, item_id):
        """Watched and favourite changes. Jellyfin 10.9 moved these from /Users/{user}/{old_path}
        to /{path}; the old addresses answer 404 on servers that have dropped them."""
        query = urllib.parse.urlencode({"userId": self.user_id})
        try:
            self._request(method, f"/{path}/{item_id}?{query}")
        except JellyfinError as error:
            if "HTTP 404" not in str(error):
                raise
            self._request(method, f"/Users/{self.user_id}/{old_path}/{item_id}")

    @staticmethod
    def _playback_report(item_id, media_source_id, play_session_id, position_ticks, is_paused=False):
        return {
            "ItemId": item_id,
            "MediaSourceId": media_source_id,
            "PlaySessionId": play_session_id,
            "PositionTicks": int(position_ticks),
            "IsPaused": is_paused,
            "CanSeek": True,
            "PlayMethod": "DirectPlay",
        }

    # Live TV ----------------------------------------------------------------

    def get_channels(self):
        """Every Live TV channel, with what's on now."""
        query = urllib.parse.urlencode({
            "UserId": self.user_id,
            "AddCurrentProgram": "true",
            "EnableImageTypes": "Primary",
            "ImageTypeLimit": 1,
            "EnableUserData": "false",
        })
        return self._request("GET", f"/LiveTv/Channels?{query}")["Items"]

    def get_upcoming_programs(self, channel_ids, start, end):
        """Guide entries starting between start and end (ISO times), earliest first."""
        body = {
            "UserId": self.user_id,
            "ChannelIds": list(channel_ids),
            "MinStartDate": start,
            "MaxStartDate": end,
            "SortBy": ["StartDate"],
            "EnableImages": False,
            "EnableUserData": False,
        }
        return self._request("POST", "/LiveTv/Programs", body=body)["Items"]

    def open_live_stream(self, channel_id):
        """Ask Jellyfin to tune a channel and relay it. Used when there's no direct stream URL."""
        body = {"UserId": self.user_id, "AutoOpenLiveStream": True}
        return self._request("POST", f"/Items/{channel_id}/PlaybackInfo", body=body)

    def close_live_stream(self, live_stream_id):
        """Release a channel Jellyfin tuned for us."""
        query = urllib.parse.urlencode({"liveStreamId": live_stream_id})
        self._request("POST", f"/LiveStreams/Close?{query}")

    # Internals --------------------------------------------------------------

    def _authorization_header(self):
        fields = [
            f'Client="{CLIENT_NAME}"',
            f'Device="{self.device_name}"',
            f'DeviceId="{self.device_id}"',
            f'Version="{self.version}"',
        ]
        if self.token:
            fields.append(f'Token="{self.token}"')
        return "MediaBrowser " + ", ".join(fields)

    def _request(self, method, path, body=None):
        headers = {
            "Accept": "application/json",
            "Authorization": self._authorization_header(),
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.server_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise AuthenticationFailed("The server rejected the sign-in.") from error
            raise JellyfinError(f"The server returned HTTP {error.code} for {path}.") from error
        except (urllib.error.URLError, OSError) as error:
            raise ServerUnreachable(f"Could not reach {self.server_url}.") from error

        if not payload:
            return None
        try:
            return json.loads(payload)
        except ValueError as error:
            raise JellyfinError(f"{self.server_url} did not answer like a Jellyfin server.") from error
