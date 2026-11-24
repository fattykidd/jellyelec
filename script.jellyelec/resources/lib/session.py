"""Getting a signed-in client: reuse the saved session, or walk through sign-in."""

import xbmc
import xbmcgui

from resources.lib import storage
from resources.lib.api import (
    AuthenticationFailed,
    JellyfinClient,
    JellyfinError,
    ServerUnreachable,
    normalize_server_url,
)
from resources.lib.discovery import discover_servers
from resources.lib.kodi import ADDON_NAME, ADDON_VERSION, device_name, log


def start_session(connection):
    """Return a signed-in JellyfinClient, or None if the user cancels."""
    return _restore_session(connection) or _sign_in(connection)


def make_client(connection, server_url=None):
    """A client for the saved server and sign-in (or another server address)."""
    return JellyfinClient(
        server_url or connection.server_url,
        device_id=connection.device_id,
        device_name=device_name(),
        version=ADDON_VERSION,
        token=connection.token,
        user_id=connection.user_id,
    )


# Saved session ----------------------------------------------------------------

def _restore_session(connection):
    """Check the saved token still works. Returns a client, or None to sign in again."""
    if not connection.signed_in:
        return None

    client = make_client(connection)
    while True:
        try:
            user = client.get_current_user()
        except AuthenticationFailed:
            log("Saved sign-in was rejected; asking the user to sign in again.")
            connection.sign_out()
            storage.save(connection)
            return None
        except ServerUnreachable:
            retry = xbmcgui.Dialog().yesno(
                ADDON_NAME,
                f"Couldn't reach {connection.server_name or connection.server_url}.[CR]"
                "Check that the server is running.",
                nolabel="Change server",
                yeslabel="Try again",
            )
            if retry:
                continue
            return None
        except JellyfinError as error:
            log(f"Couldn't restore session: {error}", xbmc.LOGWARNING)
            return None

        connection.user_name = user.get("Name", connection.user_name)
        storage.save(connection)
        return client


# Sign-in ------------------------------------------------------------------------

def _sign_in(connection):
    """Choose a server, then sign in. Returns a client, or None if the user cancels."""
    dialog = xbmcgui.Dialog()
    while True:
        server_url = _choose_server(dialog, connection.server_url)
        if server_url is None:
            return None

        client = make_client(connection, server_url)
        client.token = ""
        try:
            info = client.get_public_info()
        except JellyfinError as error:
            log(f"Server check failed for {server_url}: {error}", xbmc.LOGWARNING)
            dialog.ok(ADDON_NAME, f"Couldn't connect to {server_url}.[CR]Check the address and try again.")
            continue

        user = _ask_credentials(dialog, client, connection.user_name)
        if user is None:
            continue

        connection.server_url = client.server_url
        connection.server_name = info.get("ServerName", "")
        connection.user_id = client.user_id
        connection.user_name = user.get("Name", "")
        connection.token = client.token
        storage.save(connection)
        log(f"Signed in to {connection.server_name} as {connection.user_name}.")
        return client


def _choose_server(dialog, current_url):
    """Show discovered servers plus a manual option. Returns a URL, or None if cancelled."""
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
    try:
        servers = discover_servers()
    finally:
        xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    log(f"Discovery found {len(servers)} server(s).")

    labels = [f"{server['name']}  ({server['address']})" for server in servers]
    labels.append("Enter server address...")

    while True:
        choice = dialog.select("Choose your Jellyfin server", labels)
        if choice < 0:
            return None
        if choice < len(servers):
            return servers[choice]["address"]

        typed = dialog.input("Server address (for example 192.168.1.10:8096)", defaultt=current_url)
        if typed:
            return normalize_server_url(typed)


def _ask_credentials(dialog, client, last_user_name):
    """Ask for a username and password until sign-in works. Returns the user, or None."""
    while True:
        username = dialog.input("Username", defaultt=last_user_name)
        if not username:
            return None
        password = dialog.input("Password", option=xbmcgui.ALPHANUM_HIDE_INPUT)

        try:
            return client.authenticate(username, password)
        except AuthenticationFailed:
            dialog.ok(ADDON_NAME, "Wrong username or password.")
            last_user_name = username
        except JellyfinError as error:
            log(f"Sign-in failed: {error}", xbmc.LOGWARNING)
            dialog.ok(ADDON_NAME, "Lost connection to the server while signing in.")
            return None
