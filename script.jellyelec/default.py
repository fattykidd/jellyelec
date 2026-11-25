"""JellyELEC entry point. Kodi runs this file when the add-on starts.

The add-on settings' "Run setup again" button runs it with the argument reset_setup.
"""

import sys

from resources.lib import appliance
from resources.lib.app import run
from resources.lib.setup import reset

if "reset_setup" in sys.argv[1:]:
    reset()
else:
    # The flag tells the appliance service JellyELEC is open; it's cleared however run() ends.
    appliance.mark_running(True)
    try:
        run()
    finally:
        appliance.mark_running(False)
