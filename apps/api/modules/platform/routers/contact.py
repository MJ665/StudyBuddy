import logging
from typing import Any, Dict

from auth_utils import verify_token
from fastapi import APIRouter, Depends, HTTPException
from services.email_service import SECURITY_EMAIL, _send

router = APIRouter(prefix="/contact", tags=["contact"])
logger = logging.getLogger(__name__)


@router.post("")
def contact_support(
    payload: Dict[str, Any], current_user: dict = Depends(verify_token)
):
    """Handles inbound contact/support requests from the frontend ContactMe component."""
    subject = payload.get("subject", "Support Request")
    message = payload.get("message", "")
    priority = payload.get("priority", "Medium")

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user_email = current_user.get("email") or current_user.get("sub", "Unknown User")
    full_name = current_user.get("full_name", "Unknown User")

    html_content = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:12px;">
      <h2 style="color:#4f46e5;">New Support Request</h2>
      <p><strong>From:</strong> {full_name} ({user_email})</p>
      <p><strong>Priority:</strong> {priority}</p>
      <div style="background:#f8fafc;padding:16px;border-radius:8px;margin:20px 0;white-space:pre-wrap;">
        {message}
      </div>
    </div>
    """

    try:
        # Use email_service to send the support ticket
        success = _send(
            to_email=SECURITY_EMAIL,
            subject=f"[Support Ticket - {priority}] {subject}",
            html=html_content,
            user_id=current_user.get("sub"),
            email_type="SUPPORT_TICKET",
        )
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to dispatch support email. Please ensure the email system is properly configured.",
            )
        return {
            "status": "success",
            "message": "Support request submitted successfully",
        }
    except Exception as e:
        logger.error(f"Failed to submit support request: {e}")
        raise HTTPException(status_code=500, detail="Failed to process support request")
