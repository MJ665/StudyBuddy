"""Shared imports/helpers/schemas for the split reports router (moved verbatim from routers/reports.py — do not re-type)."""

import datetime

import json

import logging

from typing import Optional

import models

from auth_utils import (
    assert_batch_in_org,
    assert_group_in_org,
    assert_user_in_org,
    require_ldadmin,
    require_mentor_or_above,
    verify_token,
)

from database import get_async_db, get_db

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, HTTPException, status

from services.ai_reporting import ai_executive

from services.redis_service import redis_client

from sqlalchemy import or_

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

import math  # noqa: E402

import io  # noqa: E402

from openpyxl import Workbook  # noqa: E402

from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
