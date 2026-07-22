"""Shared imports/helpers/schemas for the split auth router (moved verbatim from routers/auth.py — do not re-type)."""

import asyncio

import logging

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from fastapi.responses import StreamingResponse

from pydantic import BaseModel

logger = logging.getLogger("auth")

import datetime  # noqa: E402

import random  # noqa: E402

import re  # noqa: E402

import bcrypt  # noqa: E402

import jwt  # noqa: E402

import models  # noqa: E402

import schemas  # noqa: E402

from auth_utils import (
    assert_group_in_org,  # noqa: E402
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    get_user_jwt_payload,
    require_admin,
    require_ldadmin,
    verify_token,
)

from database import get_async_db, get_db

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload  # noqa: E402

from services.ai_reporting import ai_executive  # noqa: E402

from services.audit_service import log_admin_action  # noqa: E402

from services.email_service import send_otp_email  # noqa: E402

from services.s3_service import generate_profile_upload_url  # noqa: E402

from sqlalchemy import func  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

if not hasattr(bcrypt, "original_hashpw"):
    bcrypt.original_hashpw = bcrypt.hashpw  # type: ignore

    def patched_hashpw(password, salt):
        if isinstance(password, str):
            password = password.encode("utf-8")
        if len(password) > 72:
            password = password[:72]
        return bcrypt.original_hashpw(password, salt)  # type: ignore

    bcrypt.hashpw = patched_hashpw
else:
    patched_hashpw = bcrypt.hashpw

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("about", (object,), {"__version__": bcrypt.__version__})  # type: ignore

try:
    import passlib.handlers.bcrypt

    # Inject patch into passlib's internal reference
    passlib.handlers.bcrypt._bcrypt.hashpw = patched_hashpw  # type: ignore
    # Disable the wrap bug detection which crashes on bcrypt 4.0+
    passlib.handlers.bcrypt.detect_wrap_bug = lambda ident: False  # type: ignore
    # Also patch the class-level method if it exists
    if hasattr(passlib.handlers.bcrypt, "BcryptBackend"):
        passlib.handlers.bcrypt.BcryptBackend.detect_wrap_bug = lambda self, ident: (  # type: ignore
            False
        )
except (ImportError, AttributeError):
    pass

import os  # noqa: E402

from config import settings  # noqa: E402

from pagination import paginate  # noqa: E402

from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False
)

def verify_password(plain_password, hashed_password):
    """
    Standardized verification protocol (SEC-104).
    Ensures Bcrypt 72-byte limit compliance by truncating strictly by bytes.
    """
    if not plain_password:
        return False
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    return pwd_context.verify(
        pwd_bytes.decode("utf-8", errors="ignore"), hashed_password
    )

def get_password_hash(password):
    """
    Standardized hashing protocol (SEC-104).
    Ensures Bcrypt 72-byte limit compliance by truncating strictly by bytes.
    """
    if not password:
        return None
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    return pwd_context.hash(pwd_bytes.decode("utf-8", errors="ignore"))

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None

class ProfilePhotoUploadRequest(BaseModel):
    file_name: str
    file_type: str

import urllib.parse  # noqa: E402

from fastapi.responses import RedirectResponse  # noqa: E402

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "placeholder.auth0.com")

AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "placeholder_client_id")

AUTH0_CALLBACK_URL = os.getenv(
    "AUTH0_CALLBACK_URL", "http://localhost:8000/api/auth/sso/callback"
)
