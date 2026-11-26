#!/usr/bin/env bash
#
# Look inside a p3i (CoreELEC) image and gather what's needed to plan the JellyELEC remaster.
#
# Usage:   bash image/inspect.sh path/to/CoreELEC-...img.gz
# Result:  p3i-report.tar.gz in the current folder.
#
# Reads the image as plain files: nothing is mounted and root isn't needed.
# Needs: gzip, python3, mtools, squashfs-tools, and debugfs (e2fsprogs, normally installed).
#   Fedora/RHEL:   sudo dnf install mtools squashfs-tools
#   Ubuntu/Debian: sudo apt install mtools squashfs-tools

set -euo pipefail

IMAGE_GZ="${1:?Usage: bash image/inspect.sh path/to/CoreELEC-...img.gz}"
REPORT_NAME="p3i-report"
SECTOR_SIZE=512

# Files copied out of the system part of the image (paths inside SYSTEM).
EXTRACT_PATHS=(
    etc/os-release
    usr/config
    usr/lib/kodi/kodi-config
    usr/lib/kodi/kodi.sh
    usr/lib/kodi/kodi.conf
    usr/lib/tmpfiles.d/kodi.conf
    usr/lib/tmpfiles.d/kodi-userdirs.conf
    usr/lib/tmpfiles.d/provision.conf
    usr/lib/systemd/system/kodi.service
    usr/lib/systemd/system/kodi-autostart.service
    usr/share/kodi/config
    usr/share/kodi/system/addon-manifest.xml
    usr/share/kodi/system/advancedsettings.xml
    usr/share/kodi/system/settings
    usr/share/kodi/addons/service.coreelec.settings
    usr/share/kodi/addons/skin.p3i.estuary/addon.xml
    usr/share/kodi/addons/skin.p3i.estuary/xml/Home.xml
    usr/share/kodi/addons/skin.p3i.estuary/xml/Startup.xml
    usr/share/kodi/addons/skin.estuary/xml/Home.xml
    usr/share/kodi/addons/skin.estuary/xml/Startup.xml
)

for tool in gzip python3 mdir mcopy unsquashfs; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool (see the top of this script)"; exit 1; }
done

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
report="$work/$REPORT_NAME"
mkdir -p "$report"

echo "Unpacking the image..."
gzip -dc "$IMAGE_GZ" > "$work/image.img"

echo "Reading the partition table..."
# CoreELEC images use an MBR partition table: four 16-byte entries from byte 446, each
# holding the partition's type, first sector and size in sectors.
python3 - "$work/image.img" > "$report/partitions.txt" <<'PYTHON'
import struct, sys
with open(sys.argv[1], "rb") as image:
    mbr = image.read(512)
for number in range(4):
    entry = mbr[446 + number * 16 : 462 + number * 16]
    kind, start, size = entry[4], *struct.unpack("<II", entry[8:16])
    if size:
        print(f"partition{number + 1} type=0x{kind:02x} start={start} size={size}")
PYTHON

# The first partition is COREELEC (FAT): kernel, SYSTEM, device trees, config files.
read -r boot_start boot_size < <(
    awk '/^partition1 / { sub("start=", "", $3); sub("size=", "", $4); print $3, $4 }' "$report/partitions.txt"
)
dd if="$work/image.img" of="$work/boot.img" bs="$SECTOR_SIZE" skip="$boot_start" count="$boot_size" status=none

echo "Listing the COREELEC partition..."
mdir -i "$work/boot.img" -/ :: > "$report/coreelec-partition.txt"
for file in config.ini cfgload resolution.ini; do
    mcopy -n -i "$work/boot.img" "::$file" "$report/" 2>/dev/null || true
done

echo "Reading the system part (SYSTEM)..."
mcopy -n -i "$work/boot.img" ::SYSTEM "$work/SYSTEM"
unsquashfs -s "$work/SYSTEM" > "$report/system-format.txt"
unsquashfs -l "$work/SYSTEM" | gzip > "$report/system-files.txt.gz"
unsquashfs -l "$work/SYSTEM" | grep -E '^squashfs-root/usr/share/kodi/addons/[^/]+$' \
    | sed 's|.*/||' > "$report/system-addons.txt"

echo "Copying out the files to study..."
unsquashfs -no-xattrs -d "$report/system" "$work/SYSTEM" "${EXTRACT_PATHS[@]}" > /dev/null 2>&1 || true

echo "Listing the STORAGE partition..."
read -r storage_start storage_size < <(
    awk '/^partition2 / { sub("start=", "", $3); sub("size=", "", $4); print $3, $4 }' "$report/partitions.txt"
)
dd if="$work/image.img" of="$work/storage.img" bs="$SECTOR_SIZE" skip="$storage_start" count="$storage_size" status=none
if command -v debugfs >/dev/null; then
    debugfs -R "ls -l -p /" "$work/storage.img" > "$report/storage-partition.txt" 2>&1 || true
    mkdir -p "$report/storage"
    debugfs -R "rdump / $report/storage" "$work/storage.img" > /dev/null 2>&1 || true
else
    echo "debugfs not found" > "$report/storage-partition.txt"
fi

tar -czf "$REPORT_NAME.tar.gz" -C "$work" "$REPORT_NAME"
echo "Done: $(pwd)/$REPORT_NAME.tar.gz"
