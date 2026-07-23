# resources.py — moved to modules/platform/routers/resources.py (5a).
# True module alias: `routers.resources` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.platform.routers import resources as _moved

sys.modules[__name__] = _moved
