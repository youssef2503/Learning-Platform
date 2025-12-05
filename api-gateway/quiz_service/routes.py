# quiz_service/routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from database import get_db
from models import Quiz, Question, QuizResult
from app import get_current_user_id

router = APIRouter(prefix="/api/v1/quiz", tags=["Quiz Service"])


# ========================================================================
# 1) GET QUIZ BY ID
# ========================================================================
@router.get("/{quiz_id}")
def get_quiz(
    quiz_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)   # required from Kong-JWT
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = db.query(Question).filter(Question.quiz_id == quiz_id).all()

    return {
        "quiz_id": quiz.id,
        "document_id": quiz.id,   # PDF requires document_id (quiz is tied to doc)
        "title": quiz.title,
        "total_questions": len(questions),
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "choices": q.choices,
                "type": q.type,
            }
            for q in questions
        ]
    }


# ========================================================================
# 2) SUBMIT QUIZ (grade user answers)
# ========================================================================
@router.post("/{quiz_id}/submit")
def submit_quiz(
    quiz_id: str,
    answers: Dict[str, Any],    # {"question_id": "user_answer", ...}
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):

    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = db.query(Question).filter(Question.quiz_id == quiz_id).all()
    if not questions:
        raise HTTPException(status_code=404, detail="This quiz has no questions")

    score = 0
    details = []

    # ------- Grade --------
    for q in questions:
        user_answer = answers.get(q.id)
        correct = (user_answer == q.correct_answer)

        if correct:
            score += 1

        details.append({
            "question_id": q.id,
            "question_text": q.text,
            "correct_answer": q.correct_answer,
            "user_answer": user_answer,
            "is_correct": correct
        })

    # ------- Save result in DB --------
    result = QuizResult(
        quiz_id=quiz_id,
        user_id=user_id,
        score=score,
        total=len(questions),
        details=details
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "quiz_id": quiz_id,
        "user_id": user_id,
        "score": score,
        "total": len(questions),
        "details": details
    }


# ========================================================================
# 3) USER QUIZ HISTORY
# ========================================================================
@router.get("/user/history")
def get_user_history(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    results = db.query(QuizResult).filter(QuizResult.user_id == user_id).all()

    formatted = []
    for r in results:
        formatted.append({
            "quiz_id": r.quiz_id,
            "score": r.score,
            "total": r.total,
            "details": r.details,
        })

    return {
        "user_id": user_id,
        "history_count": len(formatted),
        "results": formatted
    }
