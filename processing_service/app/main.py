from fastapi import FastAPI
import aio_pika
import logging
import json
from .config import settings
from .services.rabbitmq import publish_message
from .services.video import process_video
import os
import aiomysql

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Processing Service")


async def get_db_connection():
    return await aiomysql.connect(
        host=settings.MYSQL_HOST,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        db=settings.MYSQL_DATABASE,
    )


async def update_video_status(video_id: int, status: str):
    """Update video status in database"""
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE videos SET status = %s WHERE id = %s", (status, video_id)
            )
            await conn.commit()
        conn.close()
        logger.info(f"Updated status for video {video_id} to {status}")
    except Exception as e:
        logger.error(f"Error updating video status: {e}")


async def store_video_quality(video_id: int, quality: str, file_path: str):
    """Store video quality information in database"""
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO video_qualities (video_id, quality, file_path)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE file_path = VALUES(file_path)
            """,
                (video_id, quality, file_path),
            )
            await conn.commit()
        conn.close()
        logger.info(f"Stored quality {quality} for video {video_id}")
    except Exception as e:
        logger.error(f"Error storing video quality: {e}")


@app.on_event("startup")
async def startup():
    # Create required directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.ENCODED_DIR, exist_ok=True)

    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(
        f"amqp://guest:guest@{settings.RABBITMQ_HOST}/"
    )

    # Store connection in app state
    app.state.rabbitmq_connection = connection
    channel = await connection.channel()
    app.state.rabbitmq_channel = channel

    # Declare queue
    queue = await channel.declare_queue("processing_queue", durable=True)

    async def process_message(message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                # Parse JSON message
                data = json.loads(message.body.decode())
                video_id = data["video_id"]
                input_path = data["file_path"]
                output_path = data["processed_path"]

                logger.info(f"Received file for processing: video_id={video_id}")

                # Update status to PROCESSING
                await update_video_status(video_id, "PROCESSING")

                # Process the video into multiple resolutions
                processed_files = await process_video(input_path, output_path)

                # Store each quality in the database
                for quality, file_path in processed_files.items():
                    await store_video_quality(video_id, quality, file_path)

                # Send to thumbnail service (use highest quality for thumbnail)
                highest_quality = max(processed_files.keys())  # e.g., "1080p"
                thumbnail_message = {
                    "video_id": video_id,
                    "filename": data["filename"],
                    "processed_path": processed_files[highest_quality],
                    "thumbnail_path": f"/thumbnails/{video_id}/{os.path.splitext(data['filename'])[0]}.jpg",
                }

                await publish_message(channel, "thumbnail_queue", thumbnail_message)

                # Update status to COMPLETED
                await update_video_status(video_id, "COMPLETED")

                logger.info(f"Processing completed for video {video_id}")

            except Exception as e:
                logger.error(f"Error processing video {video_id}: {e}")
                if "video_id" in locals():
                    await update_video_status(video_id, "COMPLETED")

    await queue.consume(process_message)
    logger.info("Processing service started, waiting for messages")


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "rabbitmq_connection"):
        await app.state.rabbitmq_connection.close()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
