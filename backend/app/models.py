"""PostgreSQL persistence models for EduLink."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="student", default="student")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    questions: Mapped[list[Question]] = relationship(back_populates="author", cascade="all, delete-orphan")
    answers: Mapped[list[Answer]] = relationship(back_populates="author", cascade="all, delete-orphan")
    votes: Mapped[list[Vote]] = relationship(back_populates="user", cascade="all, delete-orphan")
    resources: Mapped[list[Resource]] = relationship(back_populates="author", cascade="all, delete-orphan")
    procedures: Mapped[list[Procedure]] = relationship(back_populates="creator")
    notices: Mapped[list[Notice]] = relationship(back_populates="creator")
    help_requests: Mapped[list[HelpRequest]] = relationship(back_populates="author", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("role IN ('student', 'faculty', 'admin')", name="ck_users_role"),
    )


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, server_default="General", default="General")
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    author: Mapped[User] = relationship(back_populates="questions")
    answers: Mapped[list[Answer]] = relationship(back_populates="question", cascade="all, delete-orphan")
    votes: Mapped[list[Vote]] = relationship(back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_questions_author_id", "author_id"),
        Index("ix_questions_category", "category"),
        Index("ix_questions_created_at", "created_at"),
    )


class Answer(Base, TimestampMixin):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    faculty_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)

    question: Mapped[Question] = relationship(back_populates="answers")
    author: Mapped[User] = relationship(back_populates="answers")
    votes: Mapped[list[Vote]] = relationship(back_populates="answer", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_answers_question_id", "question_id"),)


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=True)
    answer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), nullable=True)
    vote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="votes")
    question: Mapped[Optional[Question]] = relationship(back_populates="votes")
    answer: Mapped[Optional[Answer]] = relationship(back_populates="votes")

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_votes_user_question"),
        UniqueConstraint("user_id", "answer_id", name="uq_votes_user_answer"),
        CheckConstraint(
            "(question_id IS NOT NULL AND answer_id IS NULL AND vote_type = 'upvote') "
            "OR (question_id IS NULL AND answer_id IS NOT NULL AND vote_type = 'helpful')",
            name="ck_votes_target_and_type",
        ),
    )


class Resource(Base, TimestampMixin):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, server_default="General", default="General")
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    author: Mapped[User] = relationship(back_populates="resources")


class Procedure(Base, TimestampMixin):
    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)

    creator: Mapped[User] = relationship(back_populates="procedures")


class Notice(Base, TimestampMixin):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    creator: Mapped[User] = relationship(back_populates="notices")


class HelpOffer(Base):
    __tablename__ = "help_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    help_request_id: Mapped[int] = mapped_column(
        ForeignKey("help_requests.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    help_request: Mapped["HelpRequest"] = relationship(back_populates="offers")
    user: Mapped[User] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "help_request_id", "user_id", name="uq_help_offers_request_user"
        ),
        Index("ix_help_offers_request_id", "help_request_id"),
    )


class HelpRequest(Base, TimestampMixin):
    __tablename__ = "help_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, server_default="General", default="General")
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open", default="open")

    author: Mapped[User] = relationship(back_populates="help_requests")
    offers: Mapped[list[HelpOffer]] = relationship(
        back_populates="help_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved')", name="ck_help_requests_status"),
        Index("ix_help_requests_author_id", "author_id"),
    )
