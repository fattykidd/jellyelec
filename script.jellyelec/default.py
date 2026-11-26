"""JellyELEC entry point. Kodi runs this file when the add-on starts.

The add-on settings' "Run setup again" button runs it with the argument reset_setup.
"""

import sys

from resources.lib import appliance
from resources.lib.splash import hand_over_to_new_version, open_splash

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
        # After an update, the new version takes over the running flag and puts up its own
        # backdrop before this one closes, so nothing else shows in between. If it doesn't
        # start, the flag is cleared so appliance mode opens JellyELEC again.
        if not (updated and hand_over_to_new_version(splash)):
            appliance.mark_running(False)
        splash.close()
        del splash
