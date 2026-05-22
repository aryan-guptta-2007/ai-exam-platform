import uuid
from sqlalchemy import String, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(
        String, nullable=False
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    estimated_cost: Mapped[float] = mapped_column(
        Numeric(10, 6), default=0.0, nullable=False  # high-precision for fractional cents
    )
    task_name: Mapped[str] = mapped_column(
        String, nullable=True  # e.g., 'exam_generation', 'retrieval'
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
