# gradebook.py — moved to modules/assessment/routers/gradebook.py (5a).
# True module alias: `routers.gradebook` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.assessment.routers import gradebook as _moved

sys.modules[__name__] = _moved
