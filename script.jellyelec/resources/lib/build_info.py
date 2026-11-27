"""Which JellyELEC image build this box runs.

remaster.sh records each build in /usr/share/jellyelec/build.json, in the read-only system:

    {"build": "202611271830", "p3i_release": "T4c", "addon_version": "0.0.59",
     "dovi_module": "dovi.ko"}

Images from before 0.0.59 don't have the file; they count as build "0" with dovi.ko.
"""

import json
import os
import re

BUILD_FILE = "/usr/share/jellyelec/build.json"
OS_RELEASE_FILE = "/etc/os-release"
DEFAULT_DOVI_MODULE = "dovi.ko"

# CoreELEC loads the Dolby Vision module from the top folder of the boot partition.
BOOT_PARTITION = "/flash"


def installed_build():
    """This box's build.json, or {} on an image without one (or not on a JellyELEC image)."""
    try:
        with open(BUILD_FILE, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return {}


def build_id():
    """The build's date and time in UTC, such as "202611271830"; "0" if unknown."""
    return installed_build().get("build", "0")


def p3i_release():
    """The p3i release this box runs, such as "T5"; None if it can't be told.

    From build.json, or on older images from the system's own version line, which p3i writes
    as VERSION="...-Omega_p3i_T4c_20260812123738".
    """
    release = installed_build().get("p3i_release")
    if release:
        return release
    try:
        with open(OS_RELEASE_FILE, encoding="utf-8") as file:
            match = re.search(r'^VERSION=".*_p3i_([^_"]+)_', file.read(), re.M)
    except OSError:
        return None
    return match.group(1) if match else None


def dovi_module():
    """The Dolby Vision module file this build's p3i needs, such as "dovi.ko"."""
    return installed_build().get("dovi_module") or DEFAULT_DOVI_MODULE


def dovi_module_path(name=None):
    """Where a Dolby Vision module goes on the boot partition."""
    return os.path.join(BOOT_PARTITION, name or dovi_module())
