import asyncio
import os
import logging
from ..config import settings, VideoPreset

logger = logging.getLogger(__name__)


async def process_video_preset(
    input_path: str, output_path: str, preset: VideoPreset
) -> str:
    """Process video to specific resolution using FFmpeg"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = [
            "ffmpeg",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-b:v",
            preset.bitrate,
            "-vf",
            f"scale={preset.width}:{preset.height}",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",  # Enable streaming
            "-y",  # Overwrite output file
            output_path,
        ]

        logger.info(
            f"Processing video to {preset.width}x{preset.height}: {output_path}"
        )

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception(f"FFmpeg failed with return code {process.returncode}")

        return output_path

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise


async def process_video(input_path: str, base_output_path: str) -> dict:
    """Process video into multiple resolutions"""
    try:
        results = {}
        base_dir = os.path.dirname(base_output_path)
        filename = os.path.basename(base_output_path)
        name, ext = os.path.splitext(filename)

        # Process each preset
        for quality, preset in settings.VIDEO_PRESETS.items():
            output_path = os.path.join(base_dir, f"{name}_{quality}{ext}")
            try:
                processed_path = await process_video_preset(
                    input_path, output_path, preset
                )
                results[quality] = processed_path
            except Exception as e:
                logger.error(f"Failed to process {quality}: {e}")
                continue

        if not results:
            raise Exception("No video presets were successfully processed")

        return results

    except Exception as e:
        logger.error(f"Error in video processing: {e}")
        raise
