# auth.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/identity/routers/{users,session,profile,notifications}.py
from fastapi import APIRouter

from modules.identity.routers import users
from modules.identity.routers import session
from modules.identity.routers import profile
from modules.identity.routers import notifications

from modules.identity.routers.session import get_current_user  # noqa: F401
from modules.identity.routers.auth_shared import get_password_hash  # noqa: F401
from modules.identity.routers.auth_shared import verify_password  # noqa: F401

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(users.router)
router.include_router(session.router)
router.include_router(profile.router)
router.include_router(notifications.router)
