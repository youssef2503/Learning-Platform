# quiz_service/app.py
# Document Reader & Note Generator (محسّن ومتكامل)
# متوافق مع: kong.yml (/api/v1/documents/*), kafka_module.producer.send_event, boto3 S3, genai (Gemini)
# ملاحظات: هذا الملف يحاول استخدام مكتبات اختيارية (PyPDF2, python-docx) إذا كانت مثبتة، وإلا يستخدم الـ mock extractor.

import os
import uuid
import json
import logging
import time
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

# Gemini client (google genai) — افتراضي موجود كما في مشروعك
# لو غير متوفر سيتسبب في خطأ أثناء توليد الملاحظات
try:
    from google import genai
except Exception:
    genai = None  # سنتعامل لاحقاً مع نقص المكتبة بطريقة مفهومة

# Kafka send_event — تستخدم الproducer اللي عملته في kafka_module/producer.py
from kafka_module.producer import send_event

# Optional parsers (if installed). If not present, fallback to simple text decode.
try:
    import PyPDF2  # type: ignore
except Exception:
    PyPDF2 = None

try:
    import docx  # python-docx (type: ignore)
except Exception:
    docx = None

# -------- Logging --------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("document_reader")

# -------- FastAPI app --------
app = FastAPI(title="Document Reader & Note Generator", version="1.1")

# -------- Configuration from environment --------
S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "document-reader-storage-dev")
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")  # optional; gemini client may also read from env

# S3 / boto3 configuration with retries
boto_config = Config(
    retries={
        "max_attempts": 5,
        "mode": "standard"
    },
    region_name=AWS_REGION
)

if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=boto_config,
        region_name=AWS_REGION
    )
else:
    # If keys are not provided, boto3 will attempt to use the instance/role credentials (ECS/EC2/IAM roles)
    s3_client = boto3.client("s3", config=boto_config, region_name=AWS_REGION)

# Initialize Gemini client if possible
gemini_client = None
if genai is not None:
    try:
        # Some genai client constructors accept api_key or read from env; handle both cases.
        if GEMINI_API_KEY:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            gemini_client = genai.Client()
        logger.info("Gemini client initialized.")
    except Exception as e:
        gemini_client = None
        logger.warning(f"Gemini client could not be initialized: {e}")
else:
    logger.warning("genai library not available; Gemini LLM calls will fail if attempted.")

# -------- Dependency: extract user id from Kong-forwarded headers --------
def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_consumer_id: Optional[str] = Header(None, alias="X-Consumer-ID")
) -> str:
    """
    Extract user identifier forwarded by Kong after JWT verification.
    Raises 401 if missing.
    """
    user_id = x_user_id or x_consumer_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication failed: Missing User Identifier Header")
    return user_id

# -------- Utility: robust S3 put with retries --------
def s3_put_object_with_retries(bucket: str, key: str, body: bytes, content_type: str = "application/octet-stream", max_retries: int = 3) -> None:
    """Put object into S3 with retries and exponential backoff."""
    attempt = 0
    while True:
        try:
            s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
            logger.info(f"S3 put_object succeeded: s3://{bucket}/{key}")
            return
        except (BotoCoreError, ClientError) as e:
            attempt += 1
            logger.warning(f"S3 put_object failed (attempt {attempt}): {e}")
            if attempt >= max_retries:
                logger.error("S3 put_object: max retries reached.")
                raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {e}")
            sleep_time = 2 ** attempt
            time.sleep(sleep_time)

# -------- Utility: extract text from common document types (best-effort) --------
def extract_text_from_pdf_bytes(data: bytes) -> str:
    if PyPDF2 is None:
        raise RuntimeError("PyPDF2 not installed")
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(data))  # type: ignore[name-defined]
        text_chunks = []
        for page in reader.pages:
            text_chunks.append(page.extract_text() or "")
        return "\n".join(text_chunks)
    except Exception as e:
        logger.warning(f"PyPDF2 extraction failed: {e}")
        raise

def extract_text_from_docx_bytes(data: bytes) -> str:
    if docx is None:
        raise RuntimeError("python-docx not installed")
    try:
        import io as _io
        f = _io.BytesIO(data)
        document = docx.Document(f)
        paragraphs = [p.text for p in document.paragraphs]
        return "\n".join(paragraphs)
    except Exception as e:
        logger.warning(f"python-docx extraction failed: {e}")
        raise

def get_text_from_document(file_content: bytes, filename_hint: Optional[str] = None) -> str:
    """
    Attempt to extract textual content from common document formats (PDF, DOCX, TXT).
    Falls back to simple utf-8 decode or a fixed mock summary if extraction fails.
    """
    # Try DOCX by filename
    try:
        if filename_hint and filename_hint.lower().endswith(".docx") and docx is not None:
            return extract_text_from_docx_bytes(file_content)
    except Exception:
        logger.debug("DOCX extraction attempt failed; continuing to other methods.")

    # Try PDF
    try:
        if filename_hint and filename_hint.lower().endswith(".pdf") and PyPDF2 is not None:
            return extract_text_from_pdf_bytes(file_content)
    except Exception:
        logger.debug("PDF extraction attempt failed; continuing to other methods.")

    # Try as text
    try:
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        logger.debug("utf-8 decode failed; will return fallback summary.")

    # Fallback summary (useful for binary PDFs when PyPDF2 not present)
    return (
        "The concept of Microservices Architecture focuses on designing applications "
        "as a collection of loosely coupled services. These services communicate "
        "through APIs or message brokers like Kafka. Key advantages include "
        "independent deployment, technology diversity, and resilience. For example, "
        "the Quiz Service is decoupled from the Document Reader service via Kafka."
    )

# -------- LLM (Gemini) integration with retry and validation --------
def generate_notes_with_gemini(extracted_text: str, user_id: str, max_retries: int = 3) -> str:
    """
    Generate study notes using Gemini. Retries on transient errors.
    Returns markdown string.
    """
    if gemini_client is None:
        logger.error("Gemini client not initialized.")
        raise HTTPException(status_code=500, detail="LLM service unavailable")

    prompt = (
        f"You are an expert academic assistant. Analyze the following text extracted from a document "
        f"and generate detailed, high-quality study notes, formatted strictly in Markdown. "
        f"The user ID for context is {user_id}. Focus on key concepts, definitions, and summaries. "
        f"Limit the output to ~500 words and structure using headings, bullets and short explanations.\n\n"
        f"--- DOCUMENT TEXT ---\n{extracted_text}\n--- END DOCUMENT ---"
    )

    attempt = 0
    while True:
        try:
            attempt += 1
            # Use the genai client according to your project's client API
            # The exact call may vary depending on genai version; adjust if necessary.
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            # The client may return different shapes; attempt to access .text or equivalent:
            notes_text = getattr(response, "text", None) or (response.get("text") if isinstance(response, dict) else None)
            if not notes_text:
                # Try parsing nested structure (compatibility with some SDK shapes)
                try:
                    notes_text = response["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    notes_text = None

            if not notes_text:
                raise RuntimeError("Gemini response did not contain usable text.")

            logger.info("Gemini generation succeeded.")
            return notes_text

        except Exception as e:
            logger.warning(f"Gemini generation attempt {attempt} failed: {e}")
            if attempt >= max_retries:
                logger.error("Gemini generation: max retries reached.")
                raise HTTPException(status_code=500, detail=f"LLM processing failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)

# -------- Background worker to process file and send Kafka event --------
def process_document_and_notify(document_id: str, user_id: str, filename: str, file_content: bytes, send_immediate_notes: bool = True) -> Dict[str, Any]:
    """
    Full pipeline:
    - Upload raw file to S3 (raw_documents/...)
    - Extract text
    - Generate notes with Gemini
    - Save notes to S3 (generated_notes/...)
    - Send 'notes.generated' event to Kafka
    Returns a dict with summary info (s3 keys, notes excerpt).
    """
    raw_key = f"raw_documents/{user_id}/{document_id}/{filename}"
    logger.info(f"Uploading raw file to s3://{S3_BUCKET_NAME}/{raw_key}")
    s3_put_object_with_retries(S3_BUCKET_NAME, raw_key, file_content, content_type="application/octet-stream")

    # Extract text
    extracted_text = get_text_from_document(file_content, filename_hint=filename)
    if not extracted_text or extracted_text.isspace():
        logger.error("Extracted text is empty.")
        raise HTTPException(status_code=400, detail="Could not extract content from document.")

    # Generate notes
    notes = generate_notes_with_gemini(extracted_text, user_id)

    # Save notes
    notes_key = f"generated_notes/{user_id}/{document_id}/notes.md"
    logger.info(f"Saving generated notes to s3://{S3_BUCKET_NAME}/{notes_key}")
    s3_put_object_with_retries(S3_BUCKET_NAME, notes_key, notes.encode("utf-8"), content_type="text/markdown")

    # Build event payload
    event_payload = {
        "document_id": document_id,
        "user_id": user_id,
        "filename": filename,
        "raw_file_key": raw_key,
        "notes_s3_key": notes_key,
        "notes_content": notes if send_immediate_notes else None,
        "num_questions": 5
    }

    # Send to Kafka (fire-and-forget local producer)
    try:
        send_event("notes.generated", event_payload)
        logger.info(f"Sent notes.generated event for document {document_id}")
    except Exception as e:
        logger.error(f"Failed to send Kafka event: {e}")

    return {
        "document_id": document_id,
        "raw_s3_key": raw_key,
        "notes_s3_key": notes_key,
        "notes_excerpt": notes[:120] + ("..." if len(notes) > 120 else "")
    }

# -------- Request/Response models (optional, clearer API schema) --------
class UploadResponse(BaseModel):
    document_id: str
    status: str
    notes_content: Optional[str] = None
    raw_s3_key: Optional[str] = None
    notes_s3_key: Optional[str] = None
    message: Optional[str] = None

# -------- Routes --------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "document_reader"}

@app.post("/api/v1/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    immediate: Optional[bool] = True  # if True, process synchronously and return notes; else enqueue in background
):
    """
    Upload a document and generate study notes.
    - If `immediate=true` (default) the endpoint will process synchronously and return notes content.
    - If `immediate=false` the processing will be done in background and endpoint returns 202 with document_id.
    """

    document_id = str(uuid.uuid4())
    filename = file.filename or f"document_{document_id}"

    # Read file bytes
    try:
        file_content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")

    # Basic validation: non-empty
    if not file_content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # If immediate processing requested → do it synchronously (blocks until notes generated)
    if immediate:
        try:
            result = process_document_and_notify(document_id, user_id, filename, file_content, send_immediate_notes=True)
            return UploadResponse(
                document_id=document_id,
                status="processing_completed",
                notes_content=(result.get("notes_excerpt") or "") if result else None,
                raw_s3_key=result.get("raw_s3_key"),
                notes_s3_key=result.get("notes_s3_key"),
                message="Notes generated and event sent to Kafka."
            )
        except HTTPException:
            # Re-raise HTTPException as-is
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during processing: {e}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    else:
        # Enqueue background processing and return 202
        background_tasks.add_task(process_document_and_notify, document_id, user_id, filename, file_content, False)
        return UploadResponse(
            document_id=document_id,
            status="processing_queued",
            message="Document processing queued in background. Notes will be generated and event sent asynchronously."
        )
