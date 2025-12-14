import os
import uuid
import boto3
import psycopg2
from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv
import sys

# Add parent directory to path to import common modules
sys.path.append("..")
from common.kafka_producer import send_event

load_dotenv()

app = FastAPI(title="STT Service", version="1.0.0")

# --- Configuration ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("STT_BUCKET_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

s3_client = boto3.client('s3', region_name=AWS_REGION)

def get_db_connection():
    """Establishes connection to the RDS PostgreSQL instance."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except psycopg2.Error as e:
        print(f"Database connection failed: {e}")
        return None

@app.on_event("startup")
def initialize_database():
    """Ensures the transcriptions table exists on startup."""
    conn = get_db_connection()
    if not conn:
        print("Skipping DB initialization due to connection failure.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id VARCHAR(50) PRIMARY KEY,
                    filename VARCHAR(255),
                    text TEXT,
                    s3_url VARCHAR(500),
                    status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    finally:
        conn.close()

@app.post("/api/stt/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Endpoint: Uploads audio, stores it in S3, creates a DB record, 
    and triggers a Kafka event for processing.
    """
    transcription_id = str(uuid.uuid4())
    file_key = f"uploads/{transcription_id}_{file.filename}"
    
    try:
        # 1. Upload to S3
        s3_client.upload_fileobj(file.file, S3_BUCKET, file_key)
        s3_url = f"s3://{S3_BUCKET}/{file_key}"
        
        # 2. Process Audio - Actual Transcription
        try:
            import speech_recognition as sr
            
            # Reset file pointer
            file.file.seek(0)
            
            # Save temporarily
            temp_path = f"/tmp/{transcription_id}_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(file.file.read())
            
            # Recognize speech
            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_path) as source:
                audio_data = recognizer.record(source)
                transcribed_text = recognizer.recognize_google(audio_data)
            
            # Clean up
            import os
            os.remove(temp_path)
            
        except Exception as e:
            print(f"Transcription error: {e}")
            transcribed_text = f"[Transcription failed: {str(e)}] - File: {file.filename}"
        
        # 3. Persist metadata to RDS
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO transcriptions (id, filename, text, s3_url, status) 
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (transcription_id, file.filename, transcribed_text, s3_url, "completed")
                )
            conn.commit()
            conn.close()
        
        # 4. Publish Event
        payload = {
            "event": "audio.transcription.completed",
            "transcription_id": transcription_id,
            "text": transcribed_text,
            "s3_location": s3_url
        }
        send_event("audio.transcription.completed", payload)
        
        return {
            "id": transcription_id,
            "status": "success",
            "message": "File processed and event published."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stt/transcription/{id}")
async def get_transcription(id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, text, status, created_at FROM transcriptions WHERE id = %s", (id,))
        row = cur.fetchone()
        
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Transcription not found")
        
    return {
        "id": row[0],
        "filename": row[1],
        "text": row[2],
        "status": row[3],
        "created_at": row[4]
    }

@app.get("/api/stt/transcriptions")
async def list_transcriptions():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, status, created_at FROM transcriptions ORDER BY created_at DESC")
        rows = cur.fetchall()
        
    conn.close()
    return [
        {"id": row[0], "filename": row[1], "status": row[2], "created_at": row[3]} 
        for row in rows
    ]