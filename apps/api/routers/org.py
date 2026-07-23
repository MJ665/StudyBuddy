# org.py — moved to modules/org/routers/org.py (5a).
# True module alias: `routers.org` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.org.routers import org as _moved

sys.modules[__name__] = _moved
