import os
import uuid
import json
import boto3
import psycopg2
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Optional
import sys

# Add parent directory to path to import common modules
sys.path.append("..")
# Note: In Docker, we will handle this by setting PYTHONPATH or copying common

load_dotenv()

app = FastAPI(title="Document Reader Service", version="1.0.0")

# --- Configuration ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("DOCUMENT_BUCKET_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id VARCHAR(50) PRIMARY KEY,
                    filename VARCHAR(255),
                    s3_url VARCHAR(500),
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS document_notes (
                    id SERIAL PRIMARY KEY,
                    document_id VARCHAR(50) REFERENCES documents(id),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    finally:
        conn.close()

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    doc_id = str(uuid.uuid4())
    file_key = f"documents/{doc_id}/{file.filename}"
    
    try:
        s3_client.upload_fileobj(file.file, S3_BUCKET, file_key)
        s3_url = f"s3://{S3_BUCKET}/{file_key}"
        
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (id, filename, s3_url) VALUES (%s, %s, %s)",
                    (doc_id, file.filename, s3_url)
                )
            conn.commit()
            conn.close()
            
        # Trigger processing (Kafka event would go here)
        # send_event("document.uploaded", {"id": doc_id, "url": s3_url})
        
        return {"id": doc_id, "status": "uploaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/{id}")
async def get_document(id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, s3_url, uploaded_at FROM documents WHERE id = %s", (id,))
        doc = cur.fetchone()
    
    conn.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return {"id": doc[0], "filename": doc[1], "s3_url": doc[2], "uploaded_at": doc[3]}

@app.get("/api/documents/{id}/notes")
async def get_document_notes(id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("SELECT notes FROM document_notes WHERE document_id = %s ORDER BY created_at DESC LIMIT 1", (id,))
        notes = cur.fetchone()
        
    conn.close()
    if not notes:
        return {"notes": None}
    return {"notes": notes[0]}

@app.post("/api/documents/{id}/regenerate-notes")
async def regenerate_notes(id: str):
    # Logic to trigger AI note generation
    return {"status": "regeneration_started"}

@app.get("/api/documents")
async def list_documents():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, uploaded_at FROM documents ORDER BY uploaded_at DESC")
        docs = [{"id": row[0], "filename": row[1], "uploaded_at": row[2]} for row in cur.fetchall()]
        
    conn.close()
    return docs

@app.delete("/api/documents/{id}")
async def delete_document(id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database unavailable")
        
    # Get S3 key first
    with conn.cursor() as cur:
        cur.execute("SELECT s3_url FROM documents WHERE id = %s", (id,))
        row = cur.fetchone()
        if row:
            # Parse s3_url to get key. Assuming s3://bucket/key format
            # This is a simplified parsing
            pass 
            
        cur.execute("DELETE FROM document_notes WHERE document_id = %s", (id,))
        cur.execute("DELETE FROM documents WHERE id = %s", (id,))
    
    conn.commit()
    conn.close()
    return {"status": "deleted"}
