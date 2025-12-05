# quiz_service/consumer_worker.py

import json
import logging
import uuid
import time

from sqlalchemy.orm import Session

from .quiz_generator import generate_quiz
from .quiz_kafka import create_consumer, send_event
from .database import SessionLocal
from .models import Quiz, Question

logging.basicConfig(level=logging.INFO)

TOPIC = "notes.generated"
GROUP_ID = "quiz-service-group"


# -------------------------------------------------------
# Helper: Save quiz + questions to PostgreSQL
# -------------------------------------------------------
def save_quiz_to_db(db: Session, user_id: str, questions_data: list):
    """Create a Quiz + Questions records in DB."""
    quiz_id = str(uuid.uuid4())

    # 1) Create quiz row
    quiz = Quiz(
        id=quiz_id,
        title=f"Generated Quiz for User {user_id}"
    )
    db.add(quiz)

    # 2) Create question rows
    for q in questions_data:
        question = Question(
            id=q["id"],
            quiz_id=quiz_id,
            text=q["text"],
            choices=q["choices"],
            correct_answer=q["correct_answer"],
            type=q["type"],
        )
        db.add(question)

    db.commit()
    db.refresh(quiz)
    return quiz_id


# -------------------------------------------------------
# Core Worker Loop
# -------------------------------------------------------
def start_consumer_worker():
    """Main loop that consumes notes.generated events and creates quizzes."""
    logging.info("🚀 Starting Quiz Service Kafka Worker...")
    consumer = create_consumer([TOPIC], GROUP_ID)

    while True:
        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():
            logging.error(f"Kafka Consumer Error: {msg.error()}")
            continue

        # -------------------------------------------------------
        # Parse event payload
        # -------------------------------------------------------
        try:
            event = json.loads(msg.value().decode("utf-8"))
            logging.info(f"📥 Received notes.generated event: {event}")
        except Exception as e:
            logging.error(f"Failed to decode Kafka message: {e}")
            continue

        user_id = event.get("user_id")
        notes_content = event.get("notes_content")
        num_questions = event.get("num_questions", 5)

        if not user_id:
            logging.error("Event missing user_id → skipping")
            continue

        if not notes_content:
            logging.error("Event has no notes_content → skipping")
            continue

        # -------------------------------------------------------
        # Call LLM Generator
        # -------------------------------------------------------
        logging.info("🤖 Generating quiz using Gemini LLM...")
        quiz_questions = generate_quiz(notes_content, num_questions)

        if not quiz_questions:
            logging.error("❌ LLM returned empty quiz → skipping")
            continue

        # -------------------------------------------------------
        # Save Quiz to DB
        # -------------------------------------------------------
        db = SessionLocal()
        try:
            quiz_id = save_quiz_to_db(db, user_id, quiz_questions)
            logging.info(f"📝 Quiz saved successfully with ID = {quiz_id}")
        except Exception as e:
            logging.error(f"❌ Failed to save quiz to DB: {e}")
            db.rollback()
            db.close()
            continue
        finally:
            db.close()

        # -------------------------------------------------------
        # Send Event: quiz.generated
        # -------------------------------------------------------
        out_event = {
            "quiz_id": quiz_id,
            "user_id": user_id,
            "num_questions": len(quiz_questions)
        }

        send_event("quiz.generated", out_event)
        logging.info(f"📤 Sent quiz.generated event for quiz {quiz_id}")

        time.sleep(0.25)


# -------------------------------------------------------
# Run Worker if file executed directly
# -------------------------------------------------------
if __name__ == "__main__":
    start_consumer_worker()
