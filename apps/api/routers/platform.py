# platform.py — moved to modules/platform/routers/platform.py (5a).
# True module alias: `routers.platform` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.platform.routers import platform as _moved

sys.modules[__name__] = _moved
