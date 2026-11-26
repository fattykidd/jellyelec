"""Calling Kodi's JSON-RPC interface from inside Kodi."""

import json

import xbmc


class JsonRpcError(Exception):
    """Kodi answered a JSON-RPC call with an error."""


def call(method, **params):
    """Call a JSON-RPC method and return its result. Raises JsonRpcError if Kodi refuses."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        raise JsonRpcError(f"{method}: {response['error'].get('message')}")
    return response.get("result", {})
