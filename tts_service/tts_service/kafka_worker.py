import os
import json
import logging
from confluent_kafka import Producer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts_kafka")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:29092")

producer = Producer({"bootstrap.servers": KAFKA_BROKERS})

def publish_audio_completed(event: dict):
    try:
        producer.produce(
            "audio.generation.completed",
            json.dumps(event).encode("utf-8")
        )
        producer.flush()
        logger.info(f"Published event: {event['request_id']}")
    except Exception as e:
        logger.exception("Kafka publish failed")
