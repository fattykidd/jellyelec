"""Turning CoreELEC's system services on and off: SSH, Samba (file sharing) and Bluetooth.

This works the same way as CoreELEC's own settings add-on (oe.set_service in
service.coreelec.settings). A service runs while /storage/.cache/services/<name>.conf
exists; its options are written there as KEY="value" lines. Turning it off renames that
file to <name>.disabled, so the options are kept for next time. Either way, the service's
units are then restarted, and they start or stay stopped according to those files.

Samba and Bluetooth are on in a new box, SSH is off.
"""

import os
import subprocess

from resources.lib.kodi import log

SERVICES_DIR = "/storage/.cache/services"

SSH = "sshd"
SAMBA = "samba"
BLUETOOTH = "bluez"

# Each service's systemd units, and whether it's on in a new box.
UNITS = {
    SSH: ("sshd.service",),
    SAMBA: ("nmbd.service", "smbd.service"),
    BLUETOOTH: ("bluetooth.service",),
}
ON_BY_DEFAULT = {SSH: False, SAMBA: True, BLUETOOTH: True}

# The options CoreELEC's settings add-on writes when it turns each service on (its defaults).
DEFAULT_OPTIONS = {
    SSH: {"SSH_ARGS": "", "SSHD_DISABLE_PW_AUTH": "false"},
    SAMBA: {
        "SAMBA_WORKGROUP": "WORKGROUP",
        "SAMBA_SECURE": "false",
        "SAMBA_USERNAME": "coreelec",
        "SAMBA_PASSWORD": "coreelec",
        "SAMBA_MINPROTOCOL": "SMB2",
        "SAMBA_MAXPROTOCOL": "SMB3",
        "SAMBA_AUTOSHARE": "true",
    },
    BLUETOOTH: {},
}


def is_enabled(service):
    if os.path.exists(_path(service, "conf")):
        return True
    return ON_BY_DEFAULT[service] and not os.path.exists(_path(service, "disabled"))


def set_enabled(service, enabled):
    """Turn a service on or off. Its earlier options are kept, or CoreELEC's defaults used."""
    conf, disabled = _path(service, "conf"), _path(service, "disabled")
    os.makedirs(SERVICES_DIR, exist_ok=True)
    if enabled:
        options = _read_options(conf) or _read_options(disabled) or DEFAULT_OPTIONS[service]
        with open(conf, "w", encoding="utf-8") as file:
            file.writelines(f'{key}="{value}"\n' for key, value in options.items())
        if os.path.exists(disabled):
            os.remove(disabled)
    elif os.path.exists(conf):
        os.replace(conf, disabled)
    else:
        open(disabled, "w", encoding="utf-8").close()

    for unit in UNITS[service]:
        subprocess.run(["systemctl", "restart", unit], check=False, capture_output=True)
    log(f"{service} turned {'on' if enabled else 'off'}.")


def set_root_password(password):
    """Set the root password, used to sign in over SSH. Returns True if it was accepted.

    Like CoreELEC's settings add-on, this gives the new password to passwd, which keeps it
    in /storage/.cache/shadow so it survives updates.
    """
    result = subprocess.run(
        ["passwd"], input=f"{password}\n{password}\n", capture_output=True, text=True, check=False
    )
    accepted = result.returncode == 0 and "Bad password" not in result.stdout + result.stderr
    log("Root password changed." if accepted else "The root password wasn't accepted.")
    return accepted


# Helpers ----------------------------------------------------------------------------

def _path(service, kind):
    return os.path.join(SERVICES_DIR, f"{service}.{kind}")


def _read_options(path):
    """The KEY="value" options in a service file, or {} if there's no such file."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = [line.strip() for line in file if "=" in line]
    except OSError:
        return {}
    return {key: value.strip('"') for key, value in (line.split("=", 1) for line in lines)}
