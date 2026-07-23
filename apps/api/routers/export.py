# export.py — moved to modules/reporting/routers/export.py (5a).
# True module alias: `routers.export` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.reporting.routers import export as _moved

sys.modules[__name__] = _moved
