# -----------------------------------------------------------------
# STAGE 1: BUILD STAGE (لتركيب الاعتماديات وتصغير حجم الصورة)
# -----------------------------------------------------------------
# استخدام صورة slim كنقطة انطلاق
FROM python:3.11-slim as builder

# متغيرات البيئة (يفضل استخدامها لتجنب المشاكل)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# إضافة حزم النظام المطلوبة للتجميع في مرحلة البناء
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /install

# نسخ ملف الاعتماديات
COPY requirements.txt .

# تركيب الاعتماديات في مجلد منفصل (venv)
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------
# STAGE 2: FINAL STAGE (للتشغيل - بيئة تشغيل صغيرة وآمنة)
# -----------------------------------------------------------------
FROM python:3.11-slim

# إضافة المسار للـ venv
ENV PATH="/opt/venv/bin:$PATH"

# تثبيت حزم النظام المطلوبة للتشغيل (مثل libpq-dev لاتصال DB)
# وحزمة curl لـ HEALTHCHECK
RUN apt-get update && \
    apt-get install -y libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# إنشاء مستخدم غير Root للأمان (مطلوب في الـ Best Practices)
RUN addgroup --system appgroup && adduser --system --no-create-home --shell /bin/false --ingroup appgroup appuser

# نقل إلى مجلد التشغيل
WORKDIR /app

# نسخ الاعتماديات من مرحلة الـ builder
COPY --from=builder /opt/venv /opt/venv

# نسخ ملفات التطبيق
COPY . .

# تغيير ملكية الملفات للمستخدم الجديد
RUN chown -R appuser:appgroup /app

# تشغيل كـ Non-root user
USER appuser

EXPOSE 8000

# Health Check (ضروري للمنصات السحابية)
# يتطلب وجود endpoint /health في app.py
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# تشغيل الخدمة
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]