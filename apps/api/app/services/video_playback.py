"""Resolve the attached adaptive generation without exposing an original."""
from fastapi import HTTPException
from sqlalchemy import select

from app.models.video_upload import VideoUpload


def hls_manifest_key(lesson) -> str | None:
    """Compare the same private object for local keys and S3-qualified keys."""
    key = lesson.video_asset_key or ''
    if not key.endswith('.m3u8'):
        return None
    return key.split('/', 3)[-1] if key.startswith('s3://') else key


def current_hls_generation(db, lesson) -> VideoUpload | None:
    manifest = hls_manifest_key(lesson)
    if manifest is None:
        # Genuine legacy progressive lessons remain playable until migrated.
        return None
    asset = db.scalar(select(VideoUpload).where(
        VideoUpload.lesson_id == lesson.id,
        VideoUpload.status == 'ready',
        VideoUpload.manifest_key == manifest,
    ).order_by(VideoUpload.created_at.desc(), VideoUpload.id.desc()).limit(1))
    if not asset or manifest not in (asset.outputs or []):
        # A missing/stale adaptive generation must never select the raw file.
        raise HTTPException(503, 'Adaptive video generation is not available')
    return asset
