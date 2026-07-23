"""doc_registry endpoints (moved verbatim from modules/kt/routers/documents.py)."""
from fastapi import APIRouter

from modules.kt.routers.documents_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/registry/doc-types")
def get_doc_types():
    return [
        {"id": "architecture_decision", "name": "Architecture Decision (ADR)"},
        {"id": "runbook", "name": "Operations Runbook"},
        {"id": "design_doc", "name": "System Design Doc"},
        {"id": "onboarding_guide", "name": "Onboarding Guide"},
        {"id": "post_mortem", "name": "Post-Mortem Analysis"},
    ]

@router.get("/registry/complexities")
def get_complexities():
    return [
        {"id": "beginner", "name": "Beginner"},
        {"id": "intermediate", "name": "Intermediate"},
        {"id": "advanced", "name": "Advanced"},
        {"id": "expert", "name": "Expert"},
    ]

@router.get("/registry/access-levels")
def get_access_levels():
    return [
        {"id": "public", "name": "Public (All Organization)"},
        {"id": "company_wide", "name": "Company Wide (Internal)"},
        {"id": "project_only", "name": "Confidential (Project Only)"},
    ]

@router.get("/registry/sensitivities")
def get_sensitivities():
    return [
        {"id": "low", "name": "Low (No sensitive data)"},
        {"id": "medium", "name": "Medium (Internal logic/architecture)"},
        {"id": "high", "name": "High (Credentials/PII present)"},
    ]
