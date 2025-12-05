import os
import uuid
import logging
from io import BytesIO
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from gtts import gTTS
import boto3
import sys

# Add parent directory to path to import common modules
sys.path.append("..")
from common.kafka_producer import send_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts_service")

app = FastAPI(title="TTS Service", version="1.0.0")

# --- Configuration ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("TTS_BUCKET_NAME", "tts-service-storage-dev")

# Use default credential provider chain (IAM role or env vars)
s3_client = boto3.client('s3', region_name=AWS_REGION)

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en"
    format: Optional[str] = "mp3"

@app.post("/api/tts/synthesize")
async def synthesize(req: TTSRequest):
    try:
        request_id = str(uuid.uuid4())
        # Using gTTS as a placeholder/simple implementation
        # In production, might use AWS Polly or Coqui TTS
        audio = gTTS(text=req.text, lang=req.voice or "en")
        buffer = BytesIO()
        audio.write_to_fp(buffer)
        buffer.seek(0)

        key = f"tts/{request_id}.{req.format or 'mp3'}"
        
        s3_client.put_object(
            Bucket=S3_BUCKET, 
            Key=key, 
            Body=buffer.read(), 
            ContentType=f"audio/{req.format or 'mpeg'}"
        )
        
        s3_url = f"s3://{S3_BUCKET}/{key}"

        # Publish event
        send_event("audio.generation.completed", {
            "request_id": request_id,
            "s3_url": s3_url,
            "status": "completed"
        })

        return {"request_id": request_id, "s3_url": s3_url}

    except Exception as e:
        logger.exception("TTS failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tts/audio/{id}")
async def get_audio(id: str):
    # In a real app, we might generate a presigned URL
    # For now, we'll just return the S3 path if it exists
    # We need to know the extension, which is a flaw in the API design if not stored in DB
    # Assuming mp3 for simplicity or checking multiple
    key = f"tts/{id}.mp3"
    try:
        # Check if exists (head_object)
        s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': key},
            ExpiresIn=3600
        )
        return {"url": url}
    except Exception:
        raise HTTPException(status_code=404, detail="Audio not found")

@app.delete("/api/tts/audio/{id}")
async def delete_audio(id: str):
    key = f"tts/{id}.mp3"
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
