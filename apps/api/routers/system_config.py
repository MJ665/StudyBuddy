# system_config.py — moved to modules/platform/routers/system_config.py (5a).
# True module alias: `routers.system_config` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.platform.routers import system_config as _moved

sys.modules[__name__] = _moved
