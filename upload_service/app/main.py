from fastapi import FastAPI
import aio_pika
import logging
from .config import settings
from .services.rabbitmq import publish_message
import os
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Upload Service")


def get_processed_path(video_id: int, filename: str) -> str:
    """Generate the full path for a processed video file"""
    return os.path.join(settings.ENCODED_DIR, str(video_id), filename)


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
    queue = await channel.declare_queue("upload_queue", durable=True)

    async def process_message(message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                # Parse JSON message
                data = json.loads(message.body.decode())
                video_id = data["video_id"]
                filename = data["filename"]
                file_path = data["file_path"]

                logger.info(f"Processing video ID {video_id}: {file_path}")

                # Verify file exists
                if not os.path.exists(file_path):
                    logger.error(f"File not found: {file_path}")
                    return

                # Create processed directory
                processed_dir = os.path.join(settings.ENCODED_DIR, str(video_id))
                os.makedirs(processed_dir, exist_ok=True)

                # Send to processing service
                message = {
                    "video_id": video_id,
                    "filename": filename,
                    "file_path": file_path,
                    "processed_path": get_processed_path(video_id, filename),
                }
                await publish_message(channel, "processing_queue", message)
                logger.info(f"File sent to processing: {message}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")

    await queue.consume(process_message)
    logger.info("Upload service started, waiting for messages")


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "rabbitmq_connection"):
        await app.state.rabbitmq_connection.close()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
