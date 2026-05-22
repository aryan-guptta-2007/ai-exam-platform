import uuid
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(
        String, nullable=False
    )
    storage_path: Mapped[str] = mapped_column(
        String, nullable=False
    )
    sha256: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, nullable=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    # Using 1536 dimension vector (compatible with OpenAI text-embedding-3-small and text-embedding-ada-002)
    embedding = mapped_column(
        Vector(1536), nullable=True
    )
    char_start: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    char_end: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document = relationship("Document", back_populates="chunks")
    
    outgoing_relationships = relationship(
        "DocumentChunkRelationship",
        foreign_keys="[DocumentChunkRelationship.source_chunk_id]",
        back_populates="source_chunk",
        cascade="all, delete-orphan"
    )
    incoming_relationships = relationship(
        "DocumentChunkRelationship",
        foreign_keys="[DocumentChunkRelationship.target_chunk_id]",
        back_populates="target_chunk",
        cascade="all, delete-orphan"
    )

class DocumentChunkRelationship(Base):
    __tablename__ = "document_chunk_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    target_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String, nullable=False
    )
    weight: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source_chunk = relationship("DocumentChunk", foreign_keys=[source_chunk_id], back_populates="outgoing_relationships")
    target_chunk = relationship("DocumentChunk", foreign_keys=[target_chunk_id], back_populates="incoming_relationships")

