import aio_pika
import json
from ..config import settings
import logging

logger = logging.getLogger(__name__)


async def get_rabbitmq_connection():
    return await aio_pika.connect_robust(
        f"amqp://guest:guest@{settings.RABBITMQ_HOST}/"
    )


async def publish_message(routing_key: str, message: dict):
    connection = await get_rabbitmq_connection()
    try:
        channel = await connection.channel()
        # Declare the queue to ensure it exists
        await channel.declare_queue(routing_key, durable=True)

        # Convert dict to JSON string and encode
        message_body = json.dumps(message).encode()

        # Publish message
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=message_body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key,
        )
        logger.info(f"Published message to {routing_key}: {message}")
    finally:
        await connection.close()
