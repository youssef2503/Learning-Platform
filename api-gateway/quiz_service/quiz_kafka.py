import os
import json
import logging
from confluent_kafka import Producer, Consumer

logging.basicConfig(level=logging.INFO)

# ----------------- Configuration -----------------
# يجب استخدام متغير البيئة KAFKA_BROKERS (اسم الخدمة في Kubernetes/ECS أو IP)
KAFKA_BROKER = os.getenv("KAFKA_BROKERS", "localhost:9092")

# -------- Producer (مستخدم لإرسال quiz.generated) --------

# تهيئة الـ Producer مرة واحدة عند بدء التشغيل
producer = Producer({'bootstrap.servers': KAFKA_BROKER})

def send_event(topic, event_data):
    """
    إرسال حدث إلى Topic معين.
    يتم تشفير البيانات إلى UTF-8 JSON.
    """
    try:
        data = json.dumps(event_data).encode('utf-8')
        # استخدام Producer.produce مع callback لمعالجة الأخطاء
        producer.produce(topic, data, callback=delivery_report)
        # Flush لإرسال الرسالة فوراً (مناسب لعدد قليل من الرسائل)
        producer.flush() 
        logging.info(f"Kafka event sent: Topic={topic}, Data={event_data}")
    except Exception as e:
        logging.error(f"Failed to send Kafka event to {topic}: {e}")

def delivery_report(err, msg):
    """Callback for delivery reports."""
    if err is not None:
        logging.error(f'Message delivery failed: {err}')
    else:
        logging.debug(f'Message delivered to {msg.topic()} [{msg.partition()}]')

# الدالة القديمة غير مطلوبة بعد الآن، لكن نتركها للتوافق إذا كانت مستخدمة في مكان آخر
# ملاحظة: تم تعديل app.py لاستخدام send_event مباشرة
def produce_quiz_generated(event_data): 
    send_event("quiz.generated", event_data) 

# -------- Consumer (مستخدم لاستقبال notes.generated) --------

def create_consumer(topics: list, group_id: str):
    """
    إنشاء Consumer والاستماع إلى قائمة من الـ Topics.
    """
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': group_id,
        'auto.offset.reset': 'earliest' # يبدأ من أقدم Offsets إذا لم يكن هناك Offset محفوظ
    })
    
    # الاشتراك في الـ Topics
    consumer.subscribe(topics)
    logging.info(f"Consumer subscribed to topics: {topics}")
    return consumer