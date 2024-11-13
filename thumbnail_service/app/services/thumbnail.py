import asyncio
import os
import logging
from ..config import settings

logger = logging.getLogger(__name__)


async def generate_thumbnail(video_path: str, thumbnail_path: str) -> str:
    """Generate thumbnail from video using FFmpeg"""
    try:
        # Ensure thumbnail directory exists
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

        cmd = [
            "ffmpeg",
            "-ss",
            "00:00:02",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-vf",
            f"scale={settings.THUMBNAIL_SIZE[0]}:{settings.THUMBNAIL_SIZE[1]}",
            "-y",
            thumbnail_path,
        ]

        logger.info(f"Generating thumbnail: {video_path} -> {thumbnail_path}")

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception(f"FFmpeg failed with return code {process.returncode}")

        return thumbnail_path

    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        raise
