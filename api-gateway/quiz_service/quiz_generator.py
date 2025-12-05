import os
import json
import logging
import time
import requests
import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# يجب ترك الـ API Key فارغاً، وسيتم توفيره في بيئة التشغيل
API_KEY = "" # Leave empty for Canvas environment or provide real key for local testing
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
MAX_RETRIES = 5

logging.basicConfig(level=logging.INFO)

# --- Pydantic Schemas for Structured Output ---

class QuestionSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="A unique UUID for the question.")
    text: str = Field(description="The text of the question.")
    
    # Choices: تكون قائمة للأجوبة في MCQ/TF، وتكون قائمة فارغة لـ Short Answer
    choices: List[str] = Field(description="A list of possible answers (e.g., [True, False] for TF, or multiple options for MCQ).")
    
    correct_answer: str = Field(description="The correct answer text.")
    
    # النوع يجب أن يكون حصراً: 'mcq', 'true_false', أو 'short_answer'
    type: str = Field(description="The type of question, must be one of: 'mcq', 'true_false', or 'short_answer'.")

class QuizSchema(BaseModel):
    questions: List[QuestionSchema]

# --- LLM Generation Logic ---

def generate_quiz(notes_content: str, num_questions: int = 5) -> List[Dict[str, Any]]:
    """
    Generates a quiz from the provided notes content using the Gemini API 
    with Exponential Backoff and Structured JSON output.
    """
    if not notes_content:
        logging.error("Error: Notes content is empty.")
        return []
    
    # 1. إعداد الـ Prompt لتضمين أنواع الأسئلة الثلاثة
    prompt = f"""
    You are an expert quiz generator. Your task is to create a quiz based on the following study notes.
    
    1. Generate exactly {num_questions} questions in total.
    2. Ensure the generated questions are a mix of the following three types, distributing them logically:
       - Multiple-Choice Questions (type: 'mcq', provide 4 choices).
       - True/False Questions (type: 'true_false', choices: ["True", "False"]).
       - Short Answer Questions (type: 'short_answer', choices: []).
    3. The correct answer MUST be provided in the 'correct_answer' field.
    4. The output MUST be a single JSON array that strictly follows the provided schema.

    STUDY NOTES:
    ---
    {notes_content}
    ---
    """
    
    # 2. إعداد الـ Payload لطلب Gemini
    payload = {
        "contents": [{ "parts": [{ "text": prompt }] }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": QuizSchema.model_json_schema(),
            "temperature": 0.5
        },
    }

    # 3. تطبيق Exponential Backoff
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Attempt {attempt + 1}/{MAX_RETRIES}: Calling Gemini API for quiz generation...")
            
            headers = { 'Content-Type': 'application/json' }
            response = requests.post(
                f"{API_URL}?key={API_KEY}",
                headers=headers,
                data=json.dumps(payload)
            )
            response.raise_for_status() # ترفع استثناء لأخطاء 4xx و 5xx

            result = response.json()
            
            # استخلاص الـ JSON String من الرد
            json_string = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
            
            if not json_string:
                raise ValueError("Gemini response structure is missing the JSON content.")

            # تحويل الـ JSON String إلى Pydantic Object للتحقق النهائي
            parsed_quiz_data = QuizSchema.model_validate_json(json_string)
            
            # تحويل Pydantic Object إلى List[dict] للإرجاع
            return [q.model_dump() for q in parsed_quiz_data.questions]
        
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logging.warning(f"Error on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                # حساب الـ Backoff Time: 2^attempt ثواني
                sleep_time = 2 ** attempt
                logging.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error("Maximum retries reached. Failing gracefully.")
                # 4. Fallback (الخيار البديل في حالة الفشل)
                return [{
                    "id": str(uuid.uuid4()),
                    "text": "Fallback: What is the main component of a microservices architecture?",
                    "choices": ["API Gateway", "Monolithic App", "Excel Spreadsheet"],
                    "correct_answer": "API Gateway",
                    "type": "mcq"
                }]
                
    # يجب أن لا تصل الدالة إلى هنا، لكن للإجراء الاحترازي:
    return []

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Mock notes content
    test_notes = """
    Apache Kafka is a distributed event streaming platform used for building real-time data pipelines.
    It is horizontally scalable and fault-tolerant. The main components are Producers, Consumers, Brokers, and Topics. 
    A Topic is divided into partitions for parallel processing. In our project, the Quiz Service consumes 
    from 'notes.generated' and produces to 'quiz.generated'.
    """
    
    # NOTE: Set a real API key in the environment or replace API_KEY above for local testing
    
    # quiz = generate_quiz(test_notes, 3) # قم بإلغاء التعليق للاختبار المحلي
    # if quiz:
    #     print(json.dumps(quiz, indent=2, ensure_ascii=False))
    # else:
    #     print("Quiz generation failed.")
    pass