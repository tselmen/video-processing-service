from fastapi import FastAPI
import aio_pika
import logging
import json
from .config import settings
from .services.thumbnail import generate_thumbnail
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Thumbnail Service")


@app.on_event("startup")
async def startup():
    # Create required directories
    os.makedirs(settings.ENCODED_DIR, exist_ok=True)
    os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)

    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(
        f"amqp://guest:guest@{settings.RABBITMQ_HOST}/"
    )

    # Store connection in app state
    app.state.rabbitmq_connection = connection
    channel = await connection.channel()
    app.state.rabbitmq_channel = channel

    # Declare queue
    queue = await channel.declare_queue("thumbnail_queue", durable=True)

    async def process_message(message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                # Parse JSON message
                data = json.loads(message.body.decode())
                video_id = data["video_id"]
                processed_path = data["processed_path"]
                thumbnail_path = data["thumbnail_path"]

                logger.info(
                    f"Received video for thumbnail generation: video_id={video_id}"
                )

                # Generate thumbnail
                await generate_thumbnail(processed_path, thumbnail_path)
                logger.info(
                    f"Thumbnail generated for video {video_id}: {thumbnail_path}"
                )

            except Exception as e:
                logger.error(f"Error processing video {video_id}: {e}")

    await queue.consume(process_message)
    logger.info("Thumbnail service started, waiting for messages")


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "rabbitmq_connection"):
        await app.state.rabbitmq_connection.close()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
