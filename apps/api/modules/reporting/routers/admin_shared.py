"""Shared imports/helpers/schemas for the split admin router (moved verbatim from routers/admin.py — do not re-type)."""

import datetime

import logging

from typing import List, Optional

import models

import schemas

import tasks

from auth_utils import (
    assert_batch_in_org,
    assert_group_in_org,
    assert_user_in_org,
    require_ldadmin,
    require_mentor_or_above,
)

from database import get_async_db, get_db

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from services.ai_reporting import ai_executive

from services.audit_service import log_admin_action, log_email_dispatch

from services.performance_engine import performance_engine

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from config import settings  # noqa: E402

from cache_manager import cache_manager  # noqa: E402

from pagination import paginate  # noqa: E402
