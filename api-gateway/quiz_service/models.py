from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("Question", back_populates="quiz")


class Question(Base):
    __tablename__ = "questions"

    id = Column(String, primary_key=True)
    quiz_id = Column(String, ForeignKey("quizzes.id"))
    text = Column(String)
    choices = Column(JSON)
    correct_answer = Column(String) # New field to store the correct answer text
    type = Column(String)

    quiz = relationship("Quiz", back_populates="questions")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, index=True)
    user_id = Column(String, index=True) # New field for user isolation
    score = Column(Float)
    total = Column(Integer)
    details = Column(JSON)
