# onboarding.py — moved to modules/platform/routers/onboarding.py (5a).
# True module alias: `routers.onboarding` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.platform.routers import onboarding as _moved

sys.modules[__name__] = _moved
