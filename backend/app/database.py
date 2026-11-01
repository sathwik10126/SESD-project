"""SQLAlchemy database configuration for EduLink Phase 3."""

import logging
import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Ensure environment variables are loaded
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str | None) -> str | None:
    """Use psycopg 3 explicitly for Render and other PostgreSQL URLs."""
    if not url:
        return None
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def get_engine(database_url: str | None = None):
    url = normalize_database_url(database_url or os.getenv("DATABASE_URL"))
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


engine = get_engine(DATABASE_URL)

SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    if engine
    else None
)


def get_db() -> Generator[Session, None, None]:
    """Provide a request-scoped database session without exposing internal DB errors."""
    global engine, SessionLocal
    if SessionLocal is None:
        current_url = os.getenv("DATABASE_URL")
        if current_url:
            engine = get_engine(current_url)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    if SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured. Set DATABASE_URL on the server.",
        )

    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error during request execution.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred. Please try again later.",
        ) from exc
    finally:
        db.close()


def initialize_database() -> bool:
    """Create missing tables. No records are created by this function."""
    global engine, SessionLocal
    if engine is None:
        current_url = os.getenv("DATABASE_URL")
        if current_url:
            engine = get_engine(current_url)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    if engine is None:
        logger.error("DATABASE_URL is not configured; database tables were not initialized.")
        return False

    try:
        # Importing here registers all mapped models on Base before create_all().
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        return True
    except SQLAlchemyError:
        logger.exception("Could not initialize the EduLink database.")
        return False
