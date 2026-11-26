# JellyELEC images

JellyELEC images are built from pannal's [p3i](https://github.com/pannal/CoreELEC) CoreELEC
release images. `remaster.sh` unpacks a p3i image, adds JellyELEC and a handful of settings,
and packs it back up. Everything else is p3i exactly as released.

## Building an image

Needs Linux with `mtools` and `squashfs-tools`:

- Fedora/RHEL: `sudo dnf install mtools squashfs-tools`
- Ubuntu/Debian: `sudo apt install mtools squashfs-tools`

1. Download the p3i Flash image (`.img.gz`) from its GitHub releases page.
2. From the repo folder, run:

   ```
   sudo bash image/remaster.sh ~/Downloads/<p3i image>.img.gz
   ```

The image is written to `dist/`, named for the JellyELEC and p3i versions inside it. It needs
`sudo` so the system files keep their owners when they're unpacked and packed again.

## What JellyELEC changes

In the system (read-only) part:

- JellyELEC is added as a built-in add-on that's always enabled.
- `overlay/` is copied over the system as-is:
  - `usr/lib/tmpfiles.d/jellyelec.conf`: first-boot setup. It skips CoreELEC's first-run
    wizard (JellyELEC's setup replaces it) and turns off p3i's built-in updater, which would
    otherwise replace JellyELEC with stock p3i.
  - `usr/share/jellyelec/oe_settings.xml`: CoreELEC's settings for a new box, with the
    wizard marked done. (JellyELEC's setup names the box JellyELEC on the network.)
- `skin/Startup.xml` replaces the skins' startup screen, so the boot goes from the splash
  straight into JellyELEC without showing Kodi's home screen.
- JellyELEC's still splash (from the add-on, `resources/skins/Default/media/jellyelec-splash.png`)
  becomes Kodi's splash screen, which is turned on. Once Kodi is up, the startup screen and
  JellyELEC's backdrop take over from it with the jellyfish animated. The artwork is drawn
  by `tools/make_splash.py`.
- New installs name Kodi JellyELEC and don't update add-ons automatically: a skin update
  from p3i's add-on repository would undo the startup screen. They also allow installing
  add-ons from zip files ("unknown sources"), for JellyELEC test builds.

On the COREELEC (boot) partition:

- `dtb.img` is set to the Ugoos AM6B+ device tree.
- `boot/remote.conf` is added, so the Ugoos remote works straight away.
- `oemsplash.png` (the same JellyELEC splash) replaces p3i's splash during the early boot.
- The HDMI-CEC name (what the TV shows for this input) is set to JellyELEC.
- Wake-on-LAN is turned on (`wol='1'` in `config.ini`, matched in CoreELEC's settings).

## Dolby Vision: adding dovi.ko

The Dolby Vision module can't be included in the image, so it's added by hand once, after
flashing:

1. Put the freshly flashed card or USB stick in a computer.
2. Open the drive named **COREELEC**.
3. Copy `dovi.ko` into it: the top folder, next to `kernel.img`, not into a subfolder.
4. Eject it, put it back in the box, and turn it on.

This works the same on Linux, macOS and Windows. JellyELEC's setup checks for the file and
explains these steps if it's missing.

## Looking inside an image

`inspect.sh` reports what's in a p3i image (partition layout, how SYSTEM is packed, and the
files JellyELEC changes) without changing anything. It was used to plan `remaster.sh`, and
is worth re-running on each new p3i release to check nothing has moved.

## Credits

JellyELEC images are p3i by pannal and the p3i contributors, based on U3k by Jamal and the
CoreELEC, LibreELEC and Kodi projects. Their code is GPLv2 and owned by its authors.
`boot/remote.conf` is the standard key map for the Ugoos UR-01 remote.
