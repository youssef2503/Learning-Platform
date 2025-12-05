import os
import json
import threading
import boto3
import psycopg2
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import sys

sys.path.append("..")
from common.kafka_consumer import create_consumer
from common.kafka_producer import send_event

load_dotenv()

app = FastAPI(title="Chat Completion Service", version="1.0.0")

# --- Configuration ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("CHAT_BUCKET_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

s3_client = boto3.client('s3', region_name=AWS_REGION)

class ChatRequest(BaseModel):
    user_id: str
    message: str

def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
    except psycopg2.Error as e:
        print(f"Database connection failed: {e}")
        return None

@app.on_event("startup")
def initialize_database():
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50),
                    message TEXT,
                    role VARCHAR(20),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    finally:
        conn.close()
        # Start Kafka consumer in background thread
        threading.Thread(target=transcription_consumer, daemon=True).start()

@app.post("/api/chat/message")
async def send_message(request: ChatRequest):
    """
    Handles incoming chat messages, archives them to S3/RDS, 
    and publishes a chat event.
    """
    # 1. Archive to S3 (JSON log)
    timestamp = datetime.now().isoformat()
    s3_key = f"chats/{request.user_id}/{timestamp}.json"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(request.dict())
        )
    except Exception as e:
        print(f"S3 Archival Error: {e}")

    # 2. Persist to RDS
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_history (user_id, message, role) VALUES (%s, %s, %s)",
                (request.user_id, request.message, "user")
            )
        conn.commit()
        conn.close()

    # 3. Publish Event
    send_event("chat.message", request.dict())
    
    return {"status": "Message processed and archived"}

@app.get("/api/chat/conversations")
async def list_conversations(user_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT user_id, MAX(timestamp) as last_active FROM chat_history WHERE user_id = %s GROUP BY user_id",
            (user_id,)
        )
        rows = cur.fetchall()
        
    conn.close()
    return [{"user_id": row[0], "last_active": row[1]} for row in rows]

@app.get("/api/chat/conversations/{user_id}")
async def get_conversation_history(user_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute(
            "SELECT message, role, timestamp FROM chat_history WHERE user_id = %s ORDER BY timestamp ASC",
            (user_id,)
        )
        rows = cur.fetchall()
        
    conn.close()
    return [{"message": row[0], "role": row[1], "timestamp": row[2]} for row in rows]

@app.delete("/api/chat/conversations/{user_id}")
async def delete_conversation(user_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("DELETE FROM chat_history WHERE user_id = %s", (user_id,))
        
    conn.commit()
    conn.close()
    return {"status": "deleted"}

def transcription_consumer():
    """
    Background worker: Listens for completed transcriptions 
    and processes them (e.g., generating automated replies).
    """
    consumer = create_consumer("audio.transcription.completed", "chat_service_group")
    print("Kafka Consumer started: Listening for transcriptions...")
    
    for message in consumer:
        try:
            data = message.value
            text = data.get('text')
            print(f"Received transcription event: {text}")
            # Logic for automated reply generation would go here
        except Exception as e:
            print(f"Error processing Kafka message: {e}")