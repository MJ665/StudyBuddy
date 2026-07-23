# assignment.py — moved to modules/assessment/routers/assignment.py (5a).
# True module alias: `routers.assignment` IS the moved module, so
# attribute access, monkeypatching and source inspection all
# behave exactly as before the move.
import sys

from modules.assessment.routers import assignment as _moved

sys.modules[__name__] = _moved
