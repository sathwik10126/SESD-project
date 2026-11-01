from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import HelpOffer, HelpRequest, User
from app.schemas import HelpRequestCreate, HelpRequestResponse, HelpRequestUpdate

router = APIRouter(prefix="/help-requests", tags=["Help Requests"])


def build_help_dict(h: HelpRequest, author_name: str, helpers: int = 0) -> dict:
    return {
        "id": h.id,
        "title": h.title,
        "description": h.description,
        "category": h.category,
        "author_id": h.author_id,
        "author_name": author_name,
        "status": h.status,
        "helpers": helpers,
        "created_at": h.created_at,
        "updated_at": h.updated_at,
    }


@router.get("", response_model=list[HelpRequestResponse])
def get_help_requests(db: Session = Depends(get_db)):
    stmt = (
        select(HelpRequest, User.full_name.label("author_name"))
        .join(User, HelpRequest.author_id == User.id)
        .order_by(HelpRequest.created_at.desc())
    )
    results = db.execute(stmt).all()
    offer_counts = dict(
        db.execute(
            select(HelpOffer.help_request_id, func.count(HelpOffer.id)).group_by(
                HelpOffer.help_request_id
            )
        ).all()
    )
    return [
        build_help_dict(request, author_name, int(offer_counts.get(request.id, 0)))
        for request, author_name in results
    ]


@router.post("", response_model=HelpRequestResponse, status_code=status.HTTP_201_CREATED)
def create_help_request(
    data: HelpRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = HelpRequest(
        title=data.title.strip(),
        description=data.description.strip(),
        category=(data.category or "General").strip() or "General",
        author_id=current_user.id,
        status="open",
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    return build_help_dict(request, current_user.full_name, helpers=0)


@router.put("/{request_id}", response_model=HelpRequestResponse)
def update_help_request(
    request_id: int,
    data: HelpRequestUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = db.get(HelpRequest, request_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help request not found")

    # Author or faculty/admin can update status
    if request.author_id != current_user.id and current_user.role not in ("faculty", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this help request",
        )

    request.status = data.status
    db.commit()
    db.refresh(request)

    author = db.get(User, request.author_id)
    author_name = author.full_name if author else "Student"
    helpers = (
        db.scalar(
            select(func.count())
            .select_from(HelpOffer)
            .where(HelpOffer.help_request_id == request.id)
        )
        or 0
    )
    return build_help_dict(request, author_name, helpers)

@router.post("/{request_id}/offer")
def offer_help(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = db.get(HelpRequest, request_id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Help request not found",
        )

    if request.author_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot offer help on your own request",
        )

    existing = db.scalar(
        select(HelpOffer).where(
            HelpOffer.help_request_id == request_id,
            HelpOffer.user_id == current_user.id,
        )
    )

    if existing:
        db.delete(existing)
        message = "Help offer removed"
    else:
        db.add(
            HelpOffer(
                help_request_id=request_id,
                user_id=current_user.id,
            )
        )
        message = "Help offered"

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    total = (
        db.scalar(
            select(func.count())
            .select_from(HelpOffer)
            .where(HelpOffer.help_request_id == request_id)
        )
        or 0
    )

    return {"message": message, "helpers": total}
