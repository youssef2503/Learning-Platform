FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY tts_service/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY common /common
COPY tts_service /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
