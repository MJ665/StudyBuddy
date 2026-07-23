# billing.py — moved to modules/platform/routers/billing.py (5a).
# True module alias: `routers.billing` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.platform.routers import billing as _moved

sys.modules[__name__] = _moved
