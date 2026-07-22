from auth_utils import verify_token
from database import get_async_db
from fastapi import Depends
from models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user_with_db_role(
    current_user: dict = Depends(verify_token), db: AsyncSession = Depends(get_async_db)
):
    user_id = int(current_user["sub"])
    role_res = await db.execute(select(User.role).where(User.id == user_id))
    role = role_res.scalar()
    if role:
        current_user["role"] = role
    return current_user
