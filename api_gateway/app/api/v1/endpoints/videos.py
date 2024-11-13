from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ....database import get_db
from ....models.video import Video, VideoResponse, VideoStatus, VideoQuality
from ....services.rabbitmq import publish_message
from ....config import settings
import os
import shutil
from typing import List, Optional
import logging
import mimetypes

logger = logging.getLogger(__name__)
router = APIRouter()


def get_video_path(video_id: int, filename: str) -> str:
    """Generate the full path for a video file"""
    return os.path.join(settings.UPLOAD_DIR, str(video_id), filename)


def get_processed_path(video_id: int, filename: str) -> str:
    """Generate the full path for a processed video file"""
    return os.path.join(settings.ENCODED_DIR, str(video_id), filename)


def get_thumbnail_path(video_id: int, filename: str) -> str:
    """Generate the full path for a thumbnail file"""
    base_name = os.path.splitext(filename)[0]
    return os.path.join(settings.THUMBNAIL_DIR, str(video_id), f"{base_name}.jpg")


@router.post("/", response_model=VideoResponse)
async def upload_video(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    # Create database entry first to get video_id
    db_video = Video(filename=file.filename, status=VideoStatus.UPLOADED)
    db.add(db_video)
    await db.commit()
    await db.refresh(db_video)

    # Create video-specific directory
    video_dir = os.path.join(settings.UPLOAD_DIR, str(db_video.id))
    os.makedirs(video_dir, exist_ok=True)

    # Save file with video_id in path
    file_location = get_video_path(db_video.id, file.filename)

    try:
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())

        # Send message to upload service with video_id
        message = {
            "video_id": db_video.id,
            "filename": file.filename,
            "file_path": file_location,
        }
        await publish_message("upload_queue", message)

        return db_video
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        await db.delete(db_video)
        await db.commit()
        raise HTTPException(status_code=500, detail="Error uploading video")


@router.get("/", response_model=List[VideoResponse])
async def list_videos(db: AsyncSession = Depends(get_db)):
    stmt = select(Video).options(selectinload(Video.qualities))
    result = await db.execute(stmt)
    videos = result.scalars().all()
    return videos


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Video).where(Video.id == video_id).options(selectinload(Video.qualities))
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a video, its files, and database entries"""
    try:
        # Get video with qualities to know which files to delete
        stmt = (
            select(Video)
            .where(Video.id == video_id)
            .options(selectinload(Video.qualities))
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()

        if video is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )

        # Delete files
        paths_to_delete = [
            # Original upload directory
            os.path.join(settings.UPLOAD_DIR, str(video_id)),
            # Encoded versions directory
            os.path.join(settings.ENCODED_DIR, str(video_id)),
            # Thumbnail directory
            os.path.join(settings.THUMBNAIL_DIR, str(video_id)),
        ]

        for path in paths_to_delete:
            if os.path.exists(path):
                try:
                    shutil.rmtree(path)
                    logger.info(f"Deleted directory: {path}")
                except Exception as e:
                    logger.error(f"Error deleting directory {path}: {e}")

        # Delete database entries
        # First delete qualities (due to foreign key constraint)
        await db.execute(delete(VideoQuality).where(VideoQuality.video_id == video_id))

        # Then delete video
        await db.execute(delete(Video).where(Video.id == video_id))

        await db.commit()
        logger.info(f"Successfully deleted video {video_id}")

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting video: {str(e)}",
        )


@router.get("/{video_id}/download")
async def download_video(
    video_id: int, quality: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    """
    Download a video in specified quality.
    If no quality is specified, returns available qualities.
    """
    # Get video with qualities
    stmt = (
        select(Video).where(Video.id == video_id).options(selectinload(Video.qualities))
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # If no quality specified, return available qualities
    if quality is None:
        available_qualities = [
            {
                "quality": q.quality,
                "download_url": f"/api/v1/videos/{video_id}/download?quality={q.quality}",
            }
            for q in video.qualities
        ]
        return JSONResponse(
            content={
                "video_id": video_id,
                "filename": video.filename,
                "available_qualities": available_qualities,
            }
        )

    # Find requested quality
    video_quality = next((q for q in video.qualities if q.quality == quality), None)

    if video_quality is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality {quality} not found for this video",
        )

    file_path = video_quality.file_path
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found"
        )

    # Get the file extension and mime type
    _, ext = os.path.splitext(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    # Generate download filename
    filename_base = os.path.splitext(video.filename)[0]
    download_filename = f"{filename_base}_{quality}{ext}"

    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={download_filename}"},
    )


@router.get("/{video_id}/thumbnail")
async def get_thumbnail(video_id: int, db: AsyncSession = Depends(get_db)):
    """Get the video thumbnail"""
    # Get video
    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Construct thumbnail path
    filename_base = os.path.splitext(video.filename)[0]
    thumbnail_path = os.path.join(
        settings.THUMBNAIL_DIR, str(video_id), f"{filename_base}.jpg"
    )

    if not os.path.exists(thumbnail_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found"
        )

    return FileResponse(
        path=thumbnail_path,
        media_type="image/jpeg",
        filename=f"{filename_base}_thumbnail.jpg",
    )


@router.get("/{video_id}/stream/{quality}")
async def stream_video(video_id: int, quality: str, db: AsyncSession = Depends(get_db)):
    """Stream video in specified quality"""
    # Get video with qualities
    stmt = (
        select(Video).where(Video.id == video_id).options(selectinload(Video.qualities))
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Find requested quality
    video_quality = next((q for q in video.qualities if q.quality == quality), None)

    if video_quality is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality {quality} not found for this video",
        )

    file_path = video_quality.file_path
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found"
        )

    return FileResponse(
        path=file_path, media_type="video/mp4", filename=f"{video.filename}"
    )
