from kafka import KafkaProducer
import json
import logging
from .config import KAFKA_BOOTSTRAP_SERVERS

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    acks=1,                     # نكتفي بموافقة سيرفر واحد فقط (أسرع)
    request_timeout_ms=5000,    # أقصى وقت للانتظار 5 ثواني
    max_block_ms=5000           # لا تعطل الكود أكثر من 5 ثواني
)

def send_event(topic, data):
    try:
        # نرسل الرسالة
        producer.send(topic, data)
        # producer.flush() 
        print(f"✅ Message sent to Kafka topic: {topic}")
    except Exception as e:
        print(f"❌ Error sending to Kafka: {e}")