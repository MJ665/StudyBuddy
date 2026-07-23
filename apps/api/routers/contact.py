# contact.py — moved to modules/platform/routers/contact.py (5a).
# True module alias: `routers.contact` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.platform.routers import contact as _moved

sys.modules[__name__] = _moved
