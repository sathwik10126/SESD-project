
"""SQLAlchemy database configuration for EduLink."""

import logging
import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

# Load local environment variables.
# Render environment variables take precedence over .env values.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def normalize_database_url(url: str | None) -> str | None:
    """
    Normalize PostgreSQL URLs to use the psycopg 3 driver.
    Supports Render PostgreSQL connection URLs.
    """

    if not url:
        return None

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


def get_engine(database_url: str | None = None):
    """Create the SQLAlchemy database engine."""

    url = normalize_database_url(
        database_url or os.getenv("DATABASE_URL")
    )

    if not url:
        return None

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
    )


# Initialize engine.
engine = get_engine(DATABASE_URL)

SessionLocal = (
    sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    if engine
    else None
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for each request."""

    global engine, SessionLocal

    if SessionLocal is None:
        current_url = os.getenv("DATABASE_URL")

        if current_url:
            engine = get_engine(current_url)

            if engine:
                SessionLocal = sessionmaker(
                    bind=engine,
                    autoflush=False,
                    autocommit=False,
                    expire_on_commit=False,
                )

    if SessionLocal is None:
        logger.error("DATABASE_URL is not configured.")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )

    db = SessionLocal()

    try:
        yield db

    except SQLAlchemyError as exc:
        db.rollback()

        logger.exception(
            "Database error during request execution."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred. Please try again later.",
        ) from exc

    finally:
        db.close()


def initialize_database() -> bool:
    """
    Test the database connection and create missing tables.
    Detailed errors are written to the application logs.
    """

    global engine, SessionLocal

    if engine is None:
        current_url = os.getenv("DATABASE_URL")

        if current_url:
            engine = get_engine(current_url)

            if engine:
                SessionLocal = sessionmaker(
                    bind=engine,
                    autoflush=False,
                    autocommit=False,
                    expire_on_commit=False,
                )

    if engine is None:
        logger.error(
            "DATABASE_URL is missing. Database initialization skipped."
        )
        return False

    try:
        # Import models so SQLAlchemy registers all database tables.
        from app import models  # noqa: F401

        # Test PostgreSQL connectivity.
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

        logger.info(
            "PostgreSQL connection established successfully."
        )

        # Create missing tables.
        Base.metadata.create_all(bind=engine)

        logger.info(
            "EduLink database initialized successfully."
        )

        return True

    except Exception:
        logger.exception(
            "DATABASE INITIALIZATION FAILED."
        )

        return False
