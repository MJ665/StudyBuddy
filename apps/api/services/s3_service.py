import logging

import boto3
from botocore.exceptions import ClientError
from config import settings
from fastapi import HTTPException

logger = logging.getLogger("s3_service")


def get_s3_client():
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise RuntimeError("AWS credentials missing in configuration.")

    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def generate_profile_upload_url(
    user_id: int, filename: str, file_type: str, max_size_bytes: int = 5242880
):
    s3_client = get_s3_client()
    import uuid

    safe_name = filename.replace(" ", "_")
    s3_key = f"profiles/{user_id}/{uuid.uuid4().hex[:8]}_{safe_name}"

    try:
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type},
                ["content-length-range", 1, max_size_bytes],
            ],
            ExpiresIn=300,
        )
        public_url = f"{settings.S3_PUBLIC_URL_BASE}/{s3_key}"
        return {
            "upload_url": presigned_post,
            "public_url": public_url,
            "s3_key": s3_key,
        }
    except ClientError as e:
        logger.error(f"S3 presigned POST generation failed: {e}")
        raise HTTPException(status_code=503, detail="Could not generate upload URL.")


def generate_image_resource_url(
    user_id: int, filename: str, file_type: str, max_size_bytes: int = 2097152
):
    """STRAT-IMAGE-V4: Generates presigned URL for embedding images in RichText/Quizzes."""
    s3_client = get_s3_client()
    import uuid

    safe_name = (
        "".join(c for c in filename if c.isalnum() or c in (".", "_", "-"))
        .strip()
        .replace(" ", "_")
    )
    s3_key = f"content_images/{user_id}/{uuid.uuid4().hex[:8]}_{safe_name}"

    try:
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type},
                ["content-length-range", 1, max_size_bytes],
            ],
            ExpiresIn=600,
        )
        # Using public URL base for direct embedding
        public_url = f"{settings.S3_PUBLIC_URL_BASE}/{s3_key}"
        return {
            "upload_url": presigned_post,
            "public_url": public_url,
            "s3_key": s3_key,
        }
    except ClientError as e:
        logger.error(f"S3 presigned POST generation for image failed: {e}")
        raise HTTPException(
            status_code=503, detail="Could not generate image upload URL."
        )


def generate_resource_upload_url(
    group_name: str, user_email: str, filename: str, file_type: str = "application/pdf", max_size_bytes: int = 10485760
):
    s3_client = get_s3_client()
    safe_group = group_name.replace(" ", "_")
    safe_name = filename.replace(" ", "_")
    s3_key = f"resources/{safe_group}/{user_email}/{safe_name}"

    try:
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type},
                ["content-length-range", 1, max_size_bytes],
            ],
            ExpiresIn=300,
        )
        return {"upload_url": presigned_post, "s3_key": s3_key}
    except ClientError as e:
        logger.error(f"S3 resource upload URL generation failed: {e}")
        raise HTTPException(status_code=503, detail="Could not generate upload URL.")


def generate_proctor_media_upload_url(
    attempt_id: int,
    filename: str,
    file_type: str = "video/webm",
    max_size_bytes: int = 26214400,  # 25 MB per chunk/snapshot
):
    """Presigned POST for a proctoring artifact (webcam video chunk or snapshot),
    namespaced under the exam attempt. Returns {upload_url, s3_key}."""
    s3_client = get_s3_client()
    import uuid

    safe_name = filename.replace(" ", "_")
    s3_key = f"proctoring/{attempt_id}/{uuid.uuid4().hex[:12]}_{safe_name}"
    try:
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type},
                ["content-length-range", 1, max_size_bytes],
            ],
            ExpiresIn=600,
        )
        return {"upload_url": presigned_post, "s3_key": s3_key}
    except ClientError as e:
        logger.error(f"S3 proctor media upload URL generation failed: {e}")
        raise HTTPException(status_code=503, detail="Could not generate upload URL.")


def sign_media_url(value: str | None, expiry_seconds: int = 3600) -> str | None:
    """Turn a stored media reference into a browser-loadable URL.

    The bucket is PRIVATE, so raw object URLs (…amazonaws.com/key) return
    AccessDenied. This converts a stored full-S3-URL or bare key into a
    short-lived presigned GET. Non-S3 values (data:, external http) pass through.
    """
    if not value:
        return None
    v = str(value)
    if v.startswith("data:"):
        return v
    key = None
    if ".amazonaws.com/" in v:
        key = v.split(".amazonaws.com/", 1)[1].split("?", 1)[0]
    elif not v.startswith("http"):
        key = v  # already a bare key
    if key is None:
        return v  # some other external URL — leave as-is
    try:
        return generate_presigned_get_url(key, expiry_seconds=expiry_seconds)
    except Exception as e:
        logger.warning(f"sign_media_url failed for {key}: {e}")
        return None


def delete_s3_object(s3_key: str):
    try:
        s3_client = get_s3_client()
        s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except Exception as e:
        logger.warning(f"Failed to delete S3 object {s3_key}: {e}")


def generate_presigned_get_url(
    s3_key: str, expiry_seconds: int = 3600, filename: str | None = None
):
    s3_client = get_s3_client()
    try:
        params = {"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        url = s3_client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expiry_seconds
        )
        return url
    except ClientError as e:
        logger.error(f"S3 get URL generation failed: {e}")
        raise HTTPException(status_code=503, detail="Could not generate access URL.")


def put_s3_object_content(s3_key: str, content: str, content_type: str = "text/plain"):
    s3_client = get_s3_client()
    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=content,
            ContentType=content_type,
        )
    except ClientError as e:
        logger.error(f"Failed to put S3 object {s3_key}: {e}")
        raise HTTPException(status_code=503, detail="S3 upload failed.")


def get_s3_object_content(s3_key: str) -> str:
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error(f"Failed to get S3 object {s3_key}: {e}")
        raise HTTPException(status_code=503, detail="S3 download failed.")


def generate_kt_attachment_upload_url(
    doc_id: str, filename: str, content_type: str, max_size_bytes: int = 52428800
) -> dict:
    """
    Generate a presigned POST URL for KT document attachments.
    Supports PDFs, images, and other binary files up to 50MB.
    Returns {url, fields, s3_key, public_url} for the frontend to POST directly to S3.
    """
    import uuid as _uuid

    s3_client = get_s3_client()
    safe_name = "".join(
        c for c in filename if c.isalnum() or c in (".", "_", "-")
    ).strip()
    s3_key = f"kt/attachments/{doc_id}/{_uuid.uuid4().hex[:8]}_{safe_name}"

    try:
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=600,
        )
        public_url = f"{settings.S3_PUBLIC_URL_BASE}/{s3_key}"
        return {
            "url": presigned_url,
            "upload_url": presigned_url,
            "fields": {},  # Return empty dict so frontend doesn't break if checking
            "s3_key": s3_key,
            "public_url": public_url,
        }
    except ClientError as e:
        logger.error(f"S3 KT attachment presign failed: {e}")
        raise HTTPException(
            status_code=503, detail="Could not generate attachment upload URL."
        )


def object_exists(s3_key: str) -> bool:
    s3_client = get_s3_client()
    try:
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        return True
    except Exception:
        return False
