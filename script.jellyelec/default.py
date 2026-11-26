"""JellyELEC entry point. Kodi runs this file when the add-on starts.

The add-on settings' "Run setup again" button runs it with the argument reset_setup.
"""

import sys

from resources.lib import appliance
from resources.lib.splash import open_splash, start_new_version

if "reset_setup" in sys.argv[1:]:
    from resources.lib.setup import reset

    reset()
else:
    # The flag tells the appliance service JellyELEC is open.
    appliance.mark_running(True)
    # The backdrop goes up before the rest of JellyELEC is loaded, so it appears as early as
    # possible and Kodi's own home screen is barely seen.
    splash = open_splash()
    updated = False
    try:
        from resources.lib.app import run

        updated = run(splash)
    finally:
        splash.close()
        del splash
        # After an update, the new version starts straight away and takes over the running
        # flag. Otherwise, or if it doesn't start, the flag is cleared, and appliance mode
        # opens JellyELEC again.
        if not (updated and start_new_version()):
            appliance.mark_running(False)
