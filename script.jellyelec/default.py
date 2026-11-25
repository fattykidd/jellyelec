"""JellyELEC entry point. Kodi runs this file when the add-on starts.

The add-on settings' "Run setup again" button runs it with the argument reset_setup.
"""

import sys

from resources.lib.app import run
from resources.lib.setup import reset

if "reset_setup" in sys.argv[1:]:
    reset()
else:
    run()
