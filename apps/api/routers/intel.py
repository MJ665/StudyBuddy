# intel.py — moved to modules/reporting/routers/intel.py (5a).
# True module alias: `routers.intel` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.reporting.routers import intel as _moved

sys.modules[__name__] = _moved
