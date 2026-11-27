#!/usr/bin/env python3
"""The p3i release JellyELEC images are built on, recorded in image/p3i-base.json.

    python3 tools/p3i_base.py fetch DIR   Download that release's flash image and update tar
                                          into DIR (kept for next time), check their SHA-256
                                          checksums, and print the two paths.
    python3 tools/p3i_base.py latest      Print p3i's newest release, in the base file's format.
    python3 tools/p3i_base.py update      Point the base file at p3i's newest release. Prints
                                          the new release's tag, or nothing if it's already the
                                          base. Used by the GitHub workflow that watches p3i.

The base file's "dovi_module" is the Dolby Vision module that release needs on the COREELEC
partition. It isn't in p3i's release data, so "update" keeps the current one: check pannal's
release notes in the pull request, and change it there if the new release needs another.

Only Python's standard library is used, so this runs anywhere, GitHub's build machines too.
"""

import hashlib
import json
import os
import re
import sys
import urllib.request

P3I_REPOSITORY = "pannal/CoreELEC"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{P3I_REPOSITORY}/releases/latest"
BASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "image", "p3i-base.json")

# p3i's asset names: the generic flash image, and the update tar.
IMAGE_PATTERN = re.compile(r"^Flash_CoreELEC-.*_p3i_.*-Generic\.img\.gz$")
UPDATE_PATTERN = re.compile(r"^Update_CoreELEC-.*_p3i_.*\.tar$")

CHUNK_SIZE = 1024 * 1024


def read_base():
    with open(BASE_FILE, encoding="utf-8") as file:
        return json.load(file)


def write_base(base):
    with open(BASE_FILE, "w", encoding="utf-8") as file:
        json.dump(base, file, indent=2)
        file.write("\n")


# Downloading ------------------------------------------------------------------------

def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(asset, folder):
    """The asset's path in folder, downloaded unless a good copy is already there."""
    path = os.path.join(folder, asset["name"])
    if os.path.exists(path) and sha256_of(path) == asset["sha256"]:
        print(f"  have {asset['name']}", file=sys.stderr)
        return path

    print(f"  downloading {asset['name']}", file=sys.stderr)
    partial = path + ".part"
    with urllib.request.urlopen(_request(asset["url"]), timeout=60) as response, open(partial, "wb") as file:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        for chunk in iter(lambda: response.read(CHUNK_SIZE), b""):
            file.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done * 100 // total}%", end="", file=sys.stderr)
    print(file=sys.stderr)

    actual = sha256_of(partial)
    if actual != asset["sha256"]:
        os.remove(partial)
        sys.exit(f"Error: {asset['name']} doesn't match its SHA-256 checksum "
                 f"(expected {asset['sha256']}, got {actual}).")
    os.replace(partial, path)
    return path


def fetch(folder):
    base = read_base()
    os.makedirs(folder, exist_ok=True)
    print(f"p3i {base['release']}:", file=sys.stderr)
    print(download(base["image"], folder))
    print(download(base["update"], folder))


# p3i's releases ---------------------------------------------------------------------

def latest():
    """p3i's newest release, in the base file's format (without dovi_module)."""
    with urllib.request.urlopen(_request(LATEST_RELEASE_URL), timeout=30) as response:
        release = json.load(response)
    assets = release.get("assets", [])
    return {
        "release": release["tag_name"],
        "release_url": release["html_url"],
        "image": _asset(assets, IMAGE_PATTERN),
        "update": _asset(assets, UPDATE_PATTERN),
    }


def _asset(assets, pattern):
    asset = next((asset for asset in assets if pattern.match(asset["name"])), None)
    if asset is None:
        sys.exit(f"Error: p3i's newest release has no file matching {pattern.pattern}.")
    return {"name": asset["name"], "url": asset["browser_download_url"], "sha256": _sha256(asset, assets)}


def _sha256(asset, assets):
    """The asset's checksum: from GitHub's own record of it, else p3i's .sha256 file."""
    digest = asset.get("digest") or ""
    if digest.startswith("sha256:"):
        return digest.split(":", 1)[1]
    checksum_file = next((a for a in assets if a["name"] == asset["name"] + ".sha256"), None)
    if checksum_file is None:
        sys.exit(f"Error: no checksum for {asset['name']}.")
    with urllib.request.urlopen(_request(checksum_file["browser_download_url"]), timeout=30) as response:
        return response.read().decode().split()[0]


def update():
    base = read_base()
    newest = latest()
    if newest["release"] == base["release"]:
        return
    newest["dovi_module"] = base.get("dovi_module", "dovi.ko")
    write_base(newest)
    print(newest["release"])


def _request(url):
    headers = {"User-Agent": "JellyELEC-image-builder"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "fetch" and len(sys.argv) == 3:
        fetch(sys.argv[2])
    elif command == "latest":
        print(json.dumps(latest(), indent=2))
    elif command == "update":
        update()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
