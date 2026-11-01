"""Promote an existing user to admin/faculty.

Usage (from the backend folder):
    python create_admin.py user@example.com admin
    python create_admin.py teacher@example.com faculty
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal, initialize_database  # noqa: E402
from app.models import User  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in ("student", "faculty", "admin"):
        print(__doc__)
        return 1
    initialize_database()
    from app import database
    with database.SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == sys.argv[1].lower().strip()))
        if not user:
            print("No user with that email. Register through the app first.")
            return 1
        user.role = sys.argv[2]
        db.commit()
        print(f"{user.email} is now {user.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
