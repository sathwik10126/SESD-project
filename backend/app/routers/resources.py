from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Resource, User
from app.schemas import ResourceCreate, ResourceResponse, ResourceUpdate

router = APIRouter(prefix="/resources", tags=["Resources"])


def build_resource_dict(r: Resource, author_name: str) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "category": r.category,
        "url": r.url,
        "author_id": r.author_id,
        "author_name": author_name,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


@router.get("", response_model=list[ResourceResponse])
def list_resources(db: Session = Depends(get_db)):
    stmt = (
        select(Resource, User.full_name.label("author_name"))
        .join(User, Resource.author_id == User.id)
        .order_by(Resource.created_at.desc())
    )
    results = db.execute(stmt).all()
    return [build_resource_dict(row[0], row[1]) for row in results]


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
def create_resource(
    data: ResourceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resource = Resource(
        title=data.title.strip(),
        description=data.description.strip(),
        category=(data.category or "Academic").strip() or "Academic",
        url=data.url.strip() if data.url else None,
        author_id=current_user.id,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    return build_resource_dict(resource, current_user.full_name)


@router.put("/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: int,
    data: ResourceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    if resource.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this resource",
        )

    if data.title is not None:
        resource.title = data.title.strip()
    if data.description is not None:
        resource.description = data.description.strip()
    if data.category is not None:
        resource.category = data.category.strip() or "Academic"
    if data.url is not None:
        resource.url = data.url.strip() or None

    db.commit()
    db.refresh(resource)

    author = db.get(User, resource.author_id)
    return build_resource_dict(
        resource,
        author.full_name if author else "Student",
    )


@router.delete("/{resource_id}")
def delete_resource(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    if resource.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this resource",
        )

    db.delete(resource)
    db.commit()
    return {"message": "Resource deleted successfully"}
