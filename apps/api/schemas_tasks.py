from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, field_validator


class StaleCodingAttempt(BaseModel):
    id: int
    score: int
    attempted_at: datetime

    @field_validator("score")
    def validate_score(cls, v):
        if v != 0:
            raise ValueError("Only zero-score attempts can be considered stale")
        return v

    @field_validator("attempted_at")
    def validate_date(cls, v):
        if v >= datetime.now(timezone.utc) - timedelta(days=30):
            raise ValueError("Attempt is too recent to be stale")
        return v


class StaleS3Object(BaseModel):
    key: str
    last_modified: datetime

    @field_validator("last_modified")
    def validate_age(cls, v):
        if v >= datetime.now(timezone.utc) - timedelta(days=30):
            raise ValueError("S3 Object is too recent to be considered orphaned")
        return v
