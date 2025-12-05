# مشروع المرحلة الثانية: API Gateway و Quiz Service

هذا المجلد يحتوي على التنفيذ المكتمل لخدمة الاختبارات (Quiz Service) وتكوين بوابة API Gateway (باستخدام Kong) للتطوير المحلي.

## 1. هيكل المشروع

```
api-gateway/
├── api-gateway/
│   └── kong.yml          # تكوين Kong (المسارات، JWT، Rate Limiting)
├── quiz-service/
│   ├── Dockerfile        # ملف بناء صورة خدمة الاختبارات
│   ├── main.py           # منطق API و S3 و DB (منطق توليد الكويز)
│   ├── models.py         # نماذج قاعدة البيانات (Quiz, Question, Result)
│   ├── database.py       # تكوين الاتصال بقاعدة البيانات
│   ├── kafka_consumer.py # منطق استهلاك أحداث notes.generated
│   ├── kafka_producer.py # دالة إرسال أحداث Kafka
│   └── requirements.txt  # تبعيات Python
└── docker-compose.yml    # تشغيل Kong, Quiz Service, DB, Kafka, Zookeeper
```

## 2. متطلبات التشغيل

*   Docker و Docker Compose (أو Docker Desktop).

## 3. خطوات التشغيل

1.  **بناء وتشغيل الخدمات:**
    ```bash
    docker-compose up --build -d
    ```
    سيقوم هذا الأمر ببناء صورة Quiz Service وتشغيل جميع الحاويات المطلوبة (Kong, Quiz Service, DB, Kafka, Zookeeper).

2.  **التحقق من حالة الخدمات:**
    ```bash
    docker-compose ps
    ```
    يجب أن تكون جميع الخدمات في حالة `Up`.

3.  **الوصول إلى API Gateway:**
    يمكنك الآن الوصول إلى Quiz Service عبر بوابة Kong على المنفذ `8000`.

    *   **توثيق Swagger:** `http://localhost:8000/api/quiz/docs`
    *   **مثال على استدعاء API (عبر Kong):**
        ```bash
        curl -X POST "http://localhost:8000/api/quiz/generate?document_id=doc123&user_id=user456" -H "accept: application/json"
        ```

## 4. ملاحظات هامة

*   **تكامل AWS:** تم وضع متغيرات بيئة (مثل `AWS_ACCESS_KEY_ID` و `S3_BUCKET_NAME`) في `docker-compose.yml`. يجب استبدالها ببيانات AWS الحقيقية عند النشر على AWS.
*   **Kafka Consumer:** تم تكوين `kafka_consumer.py` للعمل في نفس حاوية `quiz-service` كعملية خلفية.
*   **API Gateway Security:** تم تكوين Kong لتطبيق سياسات **JWT** و **Rate Limiting** و **CORS** كما هو مطلوب في PDF. يجب عليك إضافة تكوين JWT الفعلي ليتوافق مع خدمة المصادقة لديك.
