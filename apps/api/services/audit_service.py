from typing import Any, Dict, Optional

import models
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


def _build_admin_log(
    actor_id: Optional[int],
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    details: Optional[Dict[str, Any]],
    ip_address: Optional[str],
):
    return models.AdminAuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )


def log_admin_action(
    db: Session,
    actor_id: Optional[int],
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    commit: bool = True,
):
    """
    Strategic Audit Log Protocol (AUD-203).
    Writes an entry to admin_audit_log for administrative accountability.
    """
    log_entry = _build_admin_log(
        actor_id, actor_role, action, resource_type, resource_id, details, ip_address
    )
    db.add(log_entry)
    if commit:
        db.commit()


async def log_admin_action_async(
    db: AsyncSession,
    actor_id: Optional[int],
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    commit: bool = True,
):
    """Async twin of log_admin_action (AUD-203) for AsyncSession routers.

    Added alongside the sync version so routers can migrate to async one at a
    time without breaking the callers that still use a sync Session.
    """
    log_entry = _build_admin_log(
        actor_id, actor_role, action, resource_type, resource_id, details, ip_address
    )
    db.add(log_entry)
    if commit:
        await db.commit()


def log_email_dispatch(
    db: Session,
    recipient_email: str,
    email_type: str,
    subject: str,
    user_id: Optional[int] = None,
    status: str = "sent",
    error_message: Optional[str] = None,
    commit: bool = True,
):
    """
    Email Logging Protocol (AUD-301).
    Ensures administrative visibility of all outgoing system communications.
    """
    log_entry = models.EmailLog(
        user_id=user_id,
        recipient_email=recipient_email,
        email_type=email_type,
        subject=subject,
        status=status,
        error_message=error_message,
    )
    db.add(log_entry)
    if commit:
        db.commit()
