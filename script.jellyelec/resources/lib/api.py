"""A small Jellyfin API client.

This module has no Kodi imports, so it can be tested on a PC.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

CLIENT_NAME = "JellyELEC"
REQUEST_TIMEOUT = 10


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
            "EnableImageTypes": "Primary,Backdrop",
        })
        return self._request("GET", f"/Users/{self.user_id}/Items/Resume?{query}")["Items"]

    def image_url(self, item_id, image_type, tag, max_width=None, max_height=None):
        """Address of an item's image, resized by the server. Images don't need sign-in."""
        params = {"tag": tag, "quality": 90}
        if max_width:
            params["maxWidth"] = max_width
        if max_height:
            params["maxHeight"] = max_height
        query = urllib.parse.urlencode(params)
        return f"{self.server_url}/Items/{item_id}/Images/{image_type}?{query}"

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
