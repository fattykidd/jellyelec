"""JellyELEC entry point. Kodi runs this file when the add-on starts.

The add-on settings' "Run setup again" button runs it with the argument reset_setup.
"""

import sys

from resources.lib import appliance
from resources.lib.splash import open_splash

if "reset_setup" in sys.argv[1:]:
    from resources.lib.setup import reset

    reset()
else:
    # The flag tells the appliance service JellyELEC is open; it's cleared however this ends.
    appliance.mark_running(True)
    # The backdrop goes up before the rest of JellyELEC is loaded, so it appears as early as
    # possible and Kodi's own home screen is barely seen.
    splash = open_splash()
    try:
        from resources.lib.app import run

        run(splash)
    finally:
        splash.close()
        del splash
        appliance.mark_running(False)
