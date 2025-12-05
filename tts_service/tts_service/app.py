import os
import uuid
import logging
from io import BytesIO
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from gtts import gTTS
import boto3
from botocore.config import Config

from .kafka_worker import publish_audio_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts_service")

app = FastAPI(title="TTS Service", version="1.0")

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "tts-audio-storage")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

def get_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-ID")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID")
    return x_user_id

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en"
    format: Optional[str] = "mp3"

@app.get("/health")
def health():
    return {"message": "tts-service is running"}

@app.post("/api/v1/tts/synthesize")
def synthesize(req: TTSRequest, user_id: str = Depends(get_user_id)):
    try:
        request_id = str(uuid.uuid4())
        audio = gTTS(text=req.text, lang=req.voice or "en")
        buffer = BytesIO()
        audio.write_to_fp(buffer)
        buffer.seek(0)

        key = f"tts/{user_id}/{request_id}.{req.format or 'mp3'}"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buffer.read(), ContentType="audio/mpeg")

        publish_audio_completed({
            "user_id": user_id,
            "request_id": request_id,
            "s3_key": key,
            "status": "completed"
        })

        return {"request_id": request_id, "s3_key": key}

    except Exception as e:
        logger.exception("TTS failed")
        raise HTTPException(status_code=500, detail=str(e))

