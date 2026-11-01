from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Procedure, User
from app.schemas import ProcedureCreate, ProcedureResponse, ProcedureUpdate

router = APIRouter(prefix="/procedures", tags=["Procedures"])


def build_procedure_dict(p: Procedure, creator_name: str) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "content": p.content,
        "created_by": p.created_by,
        "creator_name": creator_name,
        "verified": p.verified,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("", response_model=list[ProcedureResponse])
def list_procedures(db: Session = Depends(get_db)):
    stmt = (
        select(Procedure, User.full_name.label("creator_name"))
        .join(User, Procedure.created_by == User.id)
        .order_by(Procedure.created_at.desc())
    )
    results = db.execute(stmt).all()
    return [build_procedure_dict(row[0], row[1]) for row in results]


@router.post("", response_model=ProcedureResponse, status_code=status.HTTP_201_CREATED)
def create_procedure(
    data: ProcedureCreate,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    procedure = Procedure(
        title=data.title.strip(),
        description=data.description.strip(),
        content=data.content.strip(),
        verified=data.verified,
        created_by=current_user.id,
    )
    db.add(procedure)
    db.commit()
    db.refresh(procedure)

    return build_procedure_dict(procedure, current_user.full_name)


@router.put("/{procedure_id}", response_model=ProcedureResponse)
def update_procedure(
    procedure_id: int,
    data: ProcedureUpdate,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    procedure = db.get(Procedure, procedure_id)
    if not procedure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procedure not found")

    if data.title is not None:
        procedure.title = data.title.strip()
    if data.description is not None:
        procedure.description = data.description.strip()
    if data.content is not None:
        procedure.content = data.content.strip()
    if data.verified is not None:
        procedure.verified = data.verified

    db.commit()
    db.refresh(procedure)

    creator = db.get(User, procedure.created_by)
    creator_name = creator.full_name if creator else "College Administration"
    return build_procedure_dict(procedure, creator_name)


@router.delete("/{procedure_id}")
def delete_procedure(
    procedure_id: int,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    procedure = db.get(Procedure, procedure_id)
    if not procedure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procedure not found")

    db.delete(procedure)
    db.commit()
    return {"message": "Procedure deleted successfully"}

