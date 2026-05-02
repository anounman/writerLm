from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from web.backend.database import Base


JsonDict = MutableDict.as_mutable(JSON().with_variant(JSONB, "postgresql"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    config: Mapped["UserConfig"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    jobs: Mapped[list["BookJob"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    books: Mapped[list["GeneratedBook"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_api_key_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    encrypted_value: Mapped[str] = mapped_column(Text)
    key_hint: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="api_keys")


class UserConfig(Base):
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    settings: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="config")


class BookJob(Base):
    __tablename__ = "book_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), default="queued")
    request_payload: Mapped[dict] = mapped_column(JsonDict, default=dict)
    config_snapshot: Mapped[dict] = mapped_column(JsonDict, default=dict)
    stages: Mapped[dict] = mapped_column(JsonDict, default=dict)
    summary: Mapped[dict] = mapped_column(JsonDict, default=dict)
    warnings: Mapped[dict] = mapped_column(JsonDict, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="jobs")
    book: Mapped["GeneratedBook"] = relationship(back_populates="job", cascade="all, delete-orphan", uselist=False)


class GeneratedBook(Base):
    __tablename__ = "generated_books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("book_jobs.id", ondelete="CASCADE"), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    topic: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    run_dir: Mapped[str] = mapped_column(Text)
    latex_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_metrics: Mapped[dict] = mapped_column(JsonDict, default=dict)
    artifact_paths: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="books")
    job: Mapped[BookJob] = relationship(back_populates="book")
