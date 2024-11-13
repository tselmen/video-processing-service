import aio_pika
from ..config import settings
import logging

logger = logging.getLogger(__name__)


async def get_rabbitmq_connection():
    return await aio_pika.connect_robust(
        f"amqp://guest:guest@{settings.RABBITMQ_HOST}/"
    )


async def publish_message(channel: aio_pika.Channel, routing_key: str, message: str):
    await channel.declare_queue(routing_key, durable=True)
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=message.encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        ),
        routing_key=routing_key,
    )
    logger.info(f"Published message to {routing_key}: {message}")
