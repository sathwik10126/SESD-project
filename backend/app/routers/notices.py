from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Notice, User
from app.schemas import NoticeCreate, NoticeResponse, NoticeUpdate

router = APIRouter(prefix="/notices", tags=["Notices"])


def build_notice_dict(n: Notice, author_name: str) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "content": n.body,
        "category": "General",
        "created_by": n.created_by,
        "author_name": author_name,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
    }


@router.get("", response_model=list[NoticeResponse])
def get_notices(db: Session = Depends(get_db)):
    stmt = (
        select(Notice, User.full_name.label("author_name"))
        .join(User, Notice.created_by == User.id)
        .order_by(Notice.created_at.desc())
    )
    results = db.execute(stmt).all()
    return [build_notice_dict(row[0], row[1]) for row in results]


@router.get("/{notice_id}", response_model=NoticeResponse)
def get_notice(notice_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(Notice, User.full_name.label("author_name"))
        .join(User, Notice.created_by == User.id)
        .where(Notice.id == notice_id)
    )
    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    return build_notice_dict(result[0], result[1])


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def create_notice(
    data: NoticeCreate,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    notice = Notice(
        title=data.title.strip(),
        body=data.body.strip(),
        created_by=current_user.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)

    return build_notice_dict(notice, current_user.full_name)


@router.put("/{notice_id}", response_model=NoticeResponse)
def update_notice(
    notice_id: int,
    data: NoticeUpdate,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    if current_user.role != "admin" and notice.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this notice",
        )

    if data.title is not None:
        notice.title = data.title.strip()
    if data.body is not None:
        notice.body = data.body.strip()

    db.commit()
    db.refresh(notice)

    author = db.get(User, notice.created_by)
    return build_notice_dict(
        notice,
        author.full_name if author else "College Administration",
    )


@router.delete("/{notice_id}")
def delete_notice(
    notice_id: int,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    if current_user.role != "admin" and notice.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this notice",
        )

    db.delete(notice)
    db.commit()
    return {"message": "Notice deleted successfully"}
