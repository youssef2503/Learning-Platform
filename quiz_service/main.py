import os
import uuid
import json
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

app = FastAPI(title="Quiz Service", version="1.0.0")

# --- Configuration ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

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
                CREATE TABLE IF NOT EXISTS quizzes (
                    id VARCHAR(50) PRIMARY KEY,
                    document_id VARCHAR(50),
                    questions JSONB,
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
    # Logic to generate quiz from document (via Kafka or direct call)
    quiz_id = str(uuid.uuid4())
    # Placeholder questions
    questions = [
        {"id": 1, "text": "Sample Question?", "options": ["A", "B"], "answer": "A"}
    ]
    
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO quizzes (id, document_id, questions) VALUES (%s, %s, %s)",
                (quiz_id, request.document_id, json.dumps(questions))
            )
        conn.commit()
        conn.close()
        
    return {"quiz_id": quiz_id, "status": "generated"}

@app.get("/api/quiz/{id}")
async def get_quiz(id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("SELECT questions FROM quizzes WHERE id = %s", (id,))
        row = cur.fetchone()
        
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    return {"id": id, "questions": row[0]}

@app.post("/api/quiz/{id}/submit")
async def submit_quiz(id: str, request: QuizSubmitRequest):
    # Calculate score logic here
    score = 100 # Placeholder
    
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO quiz_results (quiz_id, user_id, score, answers) VALUES (%s, %s, %s, %s)",
                (id, request.user_id, score, json.dumps(request.answers))
            )
        conn.commit()
        conn.close()
        
    return {"score": score, "feedback": "Great job!"}

@app.get("/api/quiz/{id}/results")
async def get_quiz_results(id: str):
    # Implementation to get results
    return {"results": []}

@app.get("/api/quiz/history")
async def get_quiz_history():
    # Implementation to get user history
    return {"history": []}

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
