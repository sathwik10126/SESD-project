from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Answer, HelpRequest, Notice, Question, Resource, User
from app.schemas import AdminStats, RoleUpdate, UserResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", response_model=AdminStats)
def admin_stats(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users_count = db.scalar(select(func.count()).select_from(User)) or 0
    questions_count = db.scalar(select(func.count()).select_from(Question)) or 0
    answers_count = db.scalar(select(func.count()).select_from(Answer)) or 0
    resources_count = db.scalar(select(func.count()).select_from(Resource)) or 0
    notices_count = db.scalar(select(func.count()).select_from(Notice)) or 0
    help_requests_count = db.scalar(select(func.count()).select_from(HelpRequest)) or 0

    return {
        "users": users_count,
        "questions": questions_count,
        "answers": answers_count,
        "resources": resources_count,
        "notices": notices_count,
        "help_requests": help_requests_count,
    }


@router.get("/users", response_model=list[UserResponse])
def get_users(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return [
        UserResponse(
            id=u.id,
            full_name=u.full_name,
            name=u.full_name,
            email=u.email,
            role=u.role,
        )
        for u in users
    ]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def set_user_role(
    user_id: int,
    data: RoleUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id and data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin role",
        )
    user.role = data.role
    db.commit()
    db.refresh(user)
    return UserResponse(
        id=user.id, full_name=user.full_name, name=user.full_name, email=user.email, role=user.role
    )
