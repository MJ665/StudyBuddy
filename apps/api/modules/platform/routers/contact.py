import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from services.email_service import send_contact_email

router = APIRouter(prefix="/contact", tags=["contact"])
logger = logging.getLogger(__name__)


class ContactForm(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    subject: str | None = Field(default="", max_length=300)
    category: str | None = Field(default="General Inquiry", max_length=100)
    message: str = Field(min_length=1, max_length=5000)


@router.post("")
def contact_support(body: ContactForm):
    """Public contact form (marketing site + support). Emails the submission to
    the configured CONTACT_EMAIL with the sender as Reply-To. No auth — anyone
    can reach out."""
    try:
        sent = send_contact_email(
            name=body.name,
            email=str(body.email),
            subject=body.subject or "",
            category=body.category or "General Inquiry",
            message=body.message,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Contact form send failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not send your message right now. Please try again later.")

    if not sent:
        # Email backend unconfigured (no Resend key). Don't 500 the visitor —
        # log it so the message isn't silently lost, and report a clear error.
        logger.warning("Contact form: email not sent (email backend unconfigured). From %s <%s>: %s",
                       body.name, body.email, body.message[:200])
        raise HTTPException(status_code=503, detail="Messaging is temporarily unavailable. Please email us directly.")

    return {"status": "success", "message": "Message sent successfully"}
