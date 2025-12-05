FROM python:3.11-slim
WORKDIR /app
COPY stt_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common /common
COPY stt_service /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]