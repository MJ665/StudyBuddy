import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import models
from database import SessionLocal
from sqlalchemy import func
from sqlalchemy.orm import Session
from config import settings
from services.s3_service import get_s3_client

from ._shared import record_task_run

logger = logging.getLogger(__name__)


def auto_lock_assignments():
    """Runs periodically to lock assignments that are past due and have lock_after_due=True."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        past_due = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.is_active.is_(True),
                models.Assignment.lock_after_due,
                models.Assignment.due_date < now,
            )
            .all()
        )

        locked_count = 0
        for assignment in past_due:
            assignment.is_active = False
            locked_count += 1

        if locked_count > 0:
            db.commit()
            logger.info(f"Auto-locked {locked_count} past due assignments.")

        record_task_run(db, "auto_lock_assignments", "success")

    except Exception as e:
        logger.error(f"Error auto-locking assignments: {e}", exc_info=True)
        record_task_run(db, "auto_lock_assignments", "failure", str(e))
        db.rollback()
    finally:
        db.close()


def merge_duplicate_users():
    """Stub for merging duplicate users."""
    db = SessionLocal()
    try:
        record_task_run(db, "merge_duplicate_users", "success")
    except Exception as e:
        record_task_run(db, "merge_duplicate_users", "failure", str(e))
    finally:
        db.close()


def fix_orphaned_records():
    """Stub for fixing orphaned records."""
    db = SessionLocal()
    try:
        record_task_run(db, "fix_orphaned_records", "success")
    except Exception as e:
        record_task_run(db, "fix_orphaned_records", "failure", str(e))
    finally:
        db.close()


def cleanup_stale_data():
    """
    STRAT-CLN-01: Automated Data Integrity Cleanup.
    Runs periodically to remove artifacts that degrade platform quality.

    1. Correct zero-score artifacts in coding_attempts (abandoned/failed tests).
    2. Mark assignments older than 90 days as inactive.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. Cleanup zero-score coding attempts (older than 24h)
        # These are usually abandoned runs or catastrophic test failures
        threshold_24h = now - timedelta(hours=24)

        # Pydantic Validation Guardrail
        from schemas_tasks import StaleCodingAttempt

        stale_candidates = (
            db.query(models.CodingAttempt)
            .filter(
                models.CodingAttempt.attempted_at < threshold_24h,
                models.CodingAttempt.score == 0,
            )
            .all()
        )

        valid_stale_ids = []
        for candidate in stale_candidates:
            try:
                # Force strictly structural validation
                StaleCodingAttempt(
                    id=candidate.id,
                    score=candidate.score,  # type: ignore
                    attempted_at=candidate.attempted_at,  # type: ignore
                )
                valid_stale_ids.append(candidate.id)
            except Exception as val_e:
                logger.warning(
                    f"Validation failed for Stale Data candidate {candidate.id}: {val_e}"
                )

        deleted_coding = 0
        if valid_stale_ids:
            deleted_coding = (
                db.query(models.CodingAttempt)
                .filter(models.CodingAttempt.id.in_(valid_stale_ids))
                .delete(synchronize_session=False)
            )

        # 2. Expire old assignments (older than 90 days)
        threshold_90d = now - timedelta(days=90)
        expired_assignments = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.is_active.is_(True),
                models.Assignment.created_at < threshold_90d,
            )
            .update({"is_active": False}, synchronize_session=False)
        )

        db.commit()
        logger.info(
            f"🧹 Cleanup complete: {deleted_coding} zero-score attempts removed, {expired_assignments} old assignments expired."
        )
        record_task_run(db, "cleanup_stale_data", "success")

    except Exception as e:
        logger.error(f"Cleanup task failure: {e}", exc_info=True)
        record_task_run(db, "cleanup_stale_data", "failure", str(e))
        db.rollback()
    finally:
        db.close()


def prune_orphaned_s3_objects():
    """
    STRAT-S3-01: Orphaned Object Pruning.
    Runs weekly. Identifies and deletes S3 objects that are no longer referenced in the DB.

    Logic:
    1. Scan DB for all referenced S3 keys (Resource model and User asset URLs).
    2. List all objects in the S3 bucket.
    3. Delete objects that are NOT in the referenced list and are older than 24h.
    """
    db = SessionLocal()
    try:
        s3 = get_s3_client()
        if not settings.AWS_ACCESS_KEY_ID:
            logger.warning("S3 Cleanup skipped: AWS credentials not configured.")
            return

        # 1. Gather all referenced keys from DB
        referenced_keys = set()

        # Resource keys
        for row in db.query(models.Resource.s3_key).all():
            if row[0]:
                referenced_keys.add(row[0])

        # User assets (URLs)
        user_assets = db.query(
            models.User.profile_photo_url,
            models.User.cover_photo_url,
            models.User.intro_video_url,
        ).all()

        for profile, cover, video in user_assets:
            for url in [profile, cover, video]:
                if url and settings.S3_BUCKET_NAME in url:
                    # Extract key from URL
                    # URL format: https://bucket.s3.region.amazonaws.com/key
                    try:
                        key = url.split(".amazonaws.com/")[-1]
                        referenced_keys.add(key)
                    except Exception as e:
                        logger.error(f"Failed to parse S3 key from URL {url}: {e}")
                        continue

        # 2. List S3 objects and compare
        paginator = s3.get_paginator("list_objects_v2")
        deleted_count = 0
        total_objects = 0

        for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME):
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                total_objects += 1
                key = obj["Key"]

                # Check if it's an orphan
                if key not in referenced_keys:
                    # Pydantic Validation Guardrail
                    from schemas_tasks import StaleS3Object

                    try:
                        valid_orphan = StaleS3Object(
                            key=key, last_modified=obj["LastModified"]
                        )
                        s3.delete_object(
                            Bucket=settings.S3_BUCKET_NAME, Key=valid_orphan.key
                        )
                        deleted_count += 1
                    except Exception as val_e:
                        logger.warning(
                            f"S3 Object {key} failed Stale validation: {val_e}"
                        )

        logger.info(
            f"🗑️ S3 Cleanup complete: {deleted_count} orphaned objects pruned from {total_objects} total."
        )
        record_task_run(db, "prune_orphaned_s3_objects", "success")

    except Exception as e:
        logger.error(f"S3 cleanup task failure: {e}", exc_info=True)
        record_task_run(db, "prune_orphaned_s3_objects", "failure", str(e))
    finally:
        db.close()
