"""Saved connection details, kept as JSON in the add-on's data folder."""

import json
import os
import uuid
from dataclasses import asdict, dataclass, fields

from resources.lib.kodi import PROFILE_PATH, log

CONNECTION_FILE = os.path.join(PROFILE_PATH, "connection.json")


@dataclass
class Connection:
    """Which server this box uses and who is signed in."""

    device_id: str
    server_url: str = ""
    server_name: str = ""
    user_id: str = ""
    user_name: str = ""
    token: str = ""

    @property
    def signed_in(self):
        return bool(self.server_url and self.user_id and self.token)

    def sign_out(self):
        self.user_id = ""
        self.token = ""


def load():
    """Load the saved connection, or start a new one with a fresh device ID."""
    try:
        with open(CONNECTION_FILE, encoding="utf-8") as file:
            data = json.load(file)
        known = {field.name for field in fields(Connection)}
        return Connection(**{key: value for key, value in data.items() if key in known})
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError) as error:
        log(f"Ignoring unreadable {CONNECTION_FILE}: {error}")

    connection = Connection(device_id=uuid.uuid4().hex)
    save(connection)
    return connection


def save(connection):
    """Write the connection to disk, replacing the old file in one step."""
    os.makedirs(PROFILE_PATH, exist_ok=True)
    temp_file = CONNECTION_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(asdict(connection), file, indent=2)
    os.replace(temp_file, CONNECTION_FILE)
