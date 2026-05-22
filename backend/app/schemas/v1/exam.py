import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class QuestionBase(BaseModel):
    text: str
    expected_answer: str
    rubric: str

class QuestionCreate(QuestionBase):
    pass

class QuestionOut(QuestionBase):
    id: uuid.UUID
    exam_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExamBase(BaseModel):
    title: str

class ExamCreate(ExamBase):
    document_id: Optional[uuid.UUID] = None

class ExamOut(ExamBase):
    id: uuid.UUID
    creator_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    created_at: datetime
    questions: List[QuestionOut] = []

    model_config = ConfigDict(from_attributes=True)

class ExamGenerateRequest(BaseModel):
    document_id: uuid.UUID
    title: str
    num_questions: int = Field(default=5, ge=1, le=20)
    topic_focus: Optional[str] = None
