# Changelog

Every add-on version is listed from 0.0.77 on. Earlier versions are summarised by area.

## 0.0.90
- Player: the OSD's buttons sit on a near-black pill, with a lighter fill and full-white icons,
  and the focused button's name is larger and brighter.
- OK closes Player info's stats (JellyELEC's key map sends OK there to the close command).

## 0.0.89
- Estuary's top bar (logo, chapter, a second clock) no longer shows over playing video: its
  overlay window is replaced with an empty one.
- Player info keeps the OSD open underneath, faded out: OK hides the stats again, and closing
  the OSD closes them too.

## 0.0.88
- Player info closes the OSD and shows Kodi's player process info on its own; the seek bar
  stays hidden while it's up.

## 0.0.87
- Player: the seek bar and OSD are much darker behind their text and buttons, so they read
  over bright scenes.
- Player info opens Kodi's player process info (and closes it on a second press).
- The skin's own full-screen top bar no longer shows above JellyELEC's; the full-screen window
  only shows buffering and Kodi's zoom and aspect messages.
- The seek bar shows "Chapter 4 of 20" (some files name chapters by their time).

## 0.0.86
- The player has JellyELEC's own OSD and seek bar in place of the skin's.
  - Seek bar: clear logo or title, episode or year line, badges, a Jellyfin-blue progress bar,
    the time (where a seek will land, while seeking), the chapter name, and Ends at.
  - OSD buttons: Chapters, back 10 seconds, Play/Pause, forward 30 seconds, Audio, Subtitles,
    Player info (Kodi's player process info) and Stop.
- Audio and subtitle pickers in JellyELEC's look, with Jellyfin's track names. Live TV gets them too.
- The skin patch (and the image build) copies in the OSD, the seek bar and their textures.

## 0.0.85
- Detail page: the studio, genre and director chips can be selected, as can anyone in Cast and
  crew. Each opens every title in your libraries that shares it.

## 0.0.84
- Detail page: a **Media info** panel (the file, then a card for each video, audio and subtitle
  track, including the Dolby Vision profile) and an **Artwork** viewer.

## 0.0.83
- Home: refreshing the rows after a detail page no longer empties them for a moment, which could
  leave the row above showing in place of the focused one.

## 0.0.82
- Detail page: the studio and genres show as chips, and the directors on their own line.
- More readable over bright fanart: darker fade, text shadows, and badges with a dark fill.
- The plot has its own space, so it can't run into the lines above.
- Cast headshots are true circles.

## 0.0.81
- New detail page in the v2 look: pill buttons (Resume or Play, From start, Trailer, Version),
  Watched and Favourite toggles saved to Jellyfin, Ends at, and rows for Seasons, Cast and crew,
  More like this, and Special features.

## 0.0.80
- Home: Left from Settings goes to the last library, so the top bar wraps both ways.

## 0.0.79
- Home: Right from Settings goes back to the first library.

## 0.0.78
- The box name is also saved in CoreELEC's settings add-on, so it stops putting "CoreELEC" back
  at boot.

## 0.0.77
- Home: a shade at the top of the fanart and text shadows, so the top bar and weather read over
  bright artwork.

## Earlier (0.0.1 to 0.0.76)

### Home and library
- The v2 home screen: library bar, spotlight, and rows of landscape cards and posters.
- Library pills in Jellyfin blue (#00A4DC), sized to their names and sliding along, with a blue
  underline for the library being shown.
- Ends at, a resolution and audio line, then badges as the default (with a Text option in
  Settings).
- Collection artwork borrowed from a movie in the collection.
- Weather icons, Open-Meteo in place of Gismeteo, and regional settings in JellyELEC.
- Back from a row returns to the library bar, and Down then goes to the first row.

### Setup, sound and picture
- Quick and Custom setup, server discovery, Quick Connect and password sign-in.
- How the box is connected (TV, AV receiver, or receiver and video processor), with audio
  passthrough set to plain HDMI.
- Dolby Vision module installation, LLDV detection (including p3i's "DV-LL" label), and p3i T5's
  "DV Output Signal Type for Video Processor", defaulting to HDR10 4:2:2 12-bit.
- Wi-Fi, box name (applied to the network and Samba too), time zone, SSH, file sharing,
  Bluetooth, weather, and remote control from other devices.

### Playback and Live TV
- Direct play with progress reported to Jellyfin, versions, trailers, special features,
  episodes, and the chapter list on Back.
- Live TV: channel list, guide with the live picture in a corner, channel up and down, and a
  watchdog that reconnects stalled channels.

### Appliance, images and updates
- Appliance mode, the jellyfish splash, and JellyELEC's startup screen in place of Kodi's home
  screen. The skin copy in /storage is patched too, so Estuary no longer flashes at boot.
- JellyELEC images remastered from p3i releases, with update tars that update a box without
  reflashing.
- After a system update, Kodi's CoreELEC settings are reset and the Dolby Vision settings redone.
- Settings > Check for updates for the add-on and the system.
- A GitHub workflow that watches for new p3i releases, opens a pull request, and builds a test
  image; another that publishes images.
