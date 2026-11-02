
"""SQLAlchemy database configuration for EduLink."""

import logging
import os
import traceback
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

# Load environment variables from backend/.env when running locally.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Configure logging.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------------------------------------------------
# DATABASE URL
# --------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")


def normalize_database_url(url: str | None) -> str | None:
    """Convert PostgreSQL URLs to the psycopg driver format."""

    if not url:
        return None

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    return url


# --------------------------------------------------
# SQLALCHEMY BASE
# --------------------------------------------------

class Base(DeclarativeBase):
    pass


# --------------------------------------------------
# DATABASE ENGINE
# --------------------------------------------------

def get_engine(database_url: str | None = None):
    """Create the SQLAlchemy database engine."""

    url = normalize_database_url(
        database_url or os.getenv("DATABASE_URL")
    )

    if not url:
        logger.error("DATABASE_URL is not configured.")
        return None

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
    )


# Create engine and session factory.
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


# --------------------------------------------------
# DATABASE SESSION
# --------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """Provide a database session to FastAPI routes."""

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured. Set DATABASE_URL on the server.",
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


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def initialize_database() -> bool:
    """
    Test the database connection and create missing tables.

    Detailed errors are printed to Render application logs.
    """

    global engine, SessionLocal

    print("\n========== EDULINK DATABASE INITIALIZATION ==========")

    # Create engine if it does not exist.
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

    # Check whether DATABASE_URL exists.
    if engine is None:
        print("ERROR: DATABASE_URL is missing or invalid.")
        logger.error(
            "DATABASE_URL is missing. Database initialization skipped."
        )
        return False

    try:
        # Import models so SQLAlchemy registers all tables.
        from app import models  # noqa: F401

        print("Step 1: Models imported successfully.")

        # Test PostgreSQL connectivity.
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

        print("Step 2: PostgreSQL connection successful.")

        logger.info(
            "PostgreSQL connection established successfully."
        )

        # Create missing database tables.
        Base.metadata.create_all(bind=engine)

        print("Step 3: Database tables created successfully.")

        logger.info(
            "EduLink database initialized successfully."
        )

        print("========== DATABASE INITIALIZATION SUCCESS ==========\n")

        return True

    except Exception as exc:
        # Print the original exception directly into Render logs.
        print("\n========== DATABASE INITIALIZATION FAILED ==========")
        print("ERROR TYPE:", type(exc).__name__)
        print("ERROR MESSAGE:", str(exc))
        traceback.print_exc()
        print("=====================================================\n")

        logger.exception(
            "DATABASE INITIALIZATION FAILED."
        )

        return False
