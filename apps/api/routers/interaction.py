# interaction.py — moved to modules/assessment/routers/interaction.py (5a).
# True module alias: `routers.interaction` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.assessment.routers import interaction as _moved

sys.modules[__name__] = _moved
