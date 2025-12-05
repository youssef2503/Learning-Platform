import os
import uuid
import json
import psycopg2
import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Optional
import sys

# Add parent directory for common modules
sys.path.append("..")
from common.kafka_producer import send_event

load_dotenv()

app = FastAPI(title="Quiz Service", version="1.0.0")

# --- Configuration ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("QUIZ_BUCKET_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Initialize S3 Client
s3_client = boto3.client('s3', region_name=AWS_REGION)

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
            # We added 's3_url' to the schema
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quizzes (
                    id VARCHAR(50) PRIMARY KEY,
                    document_id VARCHAR(50),
                    questions JSONB,
                    s3_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id SERIAL PRIMARY KEY,
                    quiz_id VARCHAR(50) REFERENCES quizzes(id),
                    user_id VARCHAR(50),
                    score INTEGER,
                    answers JSONB,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    finally:
        conn.close()

class QuizGenerateRequest(BaseModel):
    document_id: str

class QuizSubmitRequest(BaseModel):
    user_id: str
    answers: dict

@app.post("/api/quiz/generate")
async def generate_quiz(request: QuizGenerateRequest):
    # 1. Generate ID and Mock Questions (AI Logic would go here)
    quiz_id = str(uuid.uuid4())
    questions = [
        {"id": 1, "text": "What is the main topic of the document?", "options": ["Cloud Computing", "Cooking"], "answer": "Cloud Computing"},
        {"id": 2, "text": "Is S3 used for storage?", "options": ["Yes", "No"], "answer": "Yes"}
    ]
    
    # 2. Upload Quiz JSON to S3
    s3_key = f"quizzes/{quiz_id}.json"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(questions),
            ContentType='application/json'
        )
        s3_url = f"s3://{S3_BUCKET}/{s3_key}"
    except Exception as e:
        print(f"S3 Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload quiz to S3: {str(e)}")
    
    # 3. Save to RDS (with S3 URL)
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO quizzes (id, document_id, questions, s3_url) VALUES (%s, %s, %s, %s)",
                (quiz_id, request.document_id, json.dumps(questions), s3_url)
            )
        conn.commit()
        conn.close()
    
    # 4. Send Kafka Event
    send_event("quiz.generated", {
        "quiz_id": quiz_id, 
        "document_id": request.document_id,
        "s3_url": s3_url
    })
        
    return {"quiz_id": quiz_id, "status": "generated", "s3_url": s3_url}

@app.get("/api/quiz/{id}")
async def get_quiz(id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("SELECT questions, s3_url FROM quizzes WHERE id = %s", (id,))
        row = cur.fetchone()
        
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    return {"id": id, "questions": row[0], "s3_url": row[1]}

@app.post("/api/quiz/{id}/submit")
async def submit_quiz(id: str, request: QuizSubmitRequest):
    # Mock Scoring Logic
    score = 85 
    
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO quiz_results (quiz_id, user_id, score, answers) VALUES (%s, %s, %s, %s)",
                (id, request.user_id, score, json.dumps(request.answers))
            )
        conn.commit()
        conn.close()
        
    return {"score": score, "feedback": "Good effort!"}

@app.get("/api/quiz/{id}/results")
async def get_quiz_results(id: str):
    conn = get_db_connection()
    if not conn:
        return []
    with conn.cursor() as cur:
        cur.execute("SELECT user_id, score FROM quiz_results WHERE quiz_id = %s", (id,))
        rows = cur.fetchall()
    conn.close()
    return [{"user_id": r[0], "score": r[1]} for r in rows]

@app.delete("/api/quiz/{id}")
async def delete_quiz(id: str):
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM quiz_results WHERE quiz_id = %s", (id,))
            cur.execute("DELETE FROM quizzes WHERE id = %s", (id,))
        conn.commit()
        conn.close()
    return {"status": "deleted"}