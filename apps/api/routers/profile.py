# profile.py — moved to modules/identity/routers/profile_social.py (5a).
# True module alias: `routers.profile` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.identity.routers import profile_social as _moved

sys.modules[__name__] = _moved
