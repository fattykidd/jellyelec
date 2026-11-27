"""The box's network name: what file managers, routers and other devices on the network see.

CoreELEC keeps it in a file and applies it when its network service starts. Changing it
here works the same way as in CoreELEC's own settings add-on (resources/lib/hostname.py in
service.coreelec.settings): write the file, then restart the services that announce it.
"""

import subprocess

from resources.lib.kodi import log

HOSTNAME_FILE = "/storage/.cache/hostname"
JELLYELEC_NAME = "JellyELEC"
# The name CoreELEC gives a new box.
COREELEC_NAME = "CoreELEC"


def current_name():
    try:
        with open(HOSTNAME_FILE, encoding="utf-8") as file:
            return file.read().strip()
    except OSError:
        return ""


def set_name(name):
    """Rename the box, and announce the new name on the network straight away."""
    try:
        with open(HOSTNAME_FILE, "w", encoding="utf-8") as file:
            file.write(f"{name}\n")
    except OSError as error:
        log(f"Couldn't save the box name: {error}")
        return
    for command in (
        ["systemctl", "restart", "network-base"],
        # Samba's settings file is written with the box name when it starts, so it's written
        # again, then file sharing restarts if it's on. wsdd2 goes last: it reads its name
        # from those settings.
        ["systemctl", "try-restart", "samba-config"],
        ["systemctl", "try-restart", "nmbd", "smbd"],
        ["systemctl", "try-restart", "avahi-daemon", "wsdd2"],
    ):
        subprocess.run(command, check=False, capture_output=True)
    log(f"Box name set to {name}.")


def name_new_box():
    """Give a box still using CoreELEC's name the JellyELEC name. A name chosen by hand stays."""
    if current_name() in ("", COREELEC_NAME):
        set_name(JELLYELEC_NAME)
