"""Entry point Kodi uses to get a Live TV channel's stream when that channel is played."""

import sys

from resources.lib.channel_resolver import run

run(sys.argv)
