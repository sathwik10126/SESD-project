from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Answer, Question, User, Vote
from app.schemas import (
    AnswerCreate,
    AnswerResponse,
    AnswerUpdate,
    AnswerVerificationUpdate,
)
from app.services.answer_ranking import answer_rank_score

router = APIRouter(prefix="/questions", tags=["Answers"])


def build_answer_dict(
    a: Answer,
    author_name: str,
    helpful_votes: int,
    ranking_score: float | None = None,
) -> dict:
    return {
        "id": a.id,
        "question_id": a.question_id,
        "author_id": a.author_id,
        "author_name": author_name,
        "body": a.body,
        "content": a.body,
        "faculty_verified": a.faculty_verified,
        "helpful_votes": helpful_votes,
        "ranking_score": ranking_score,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


def answer_score(answer: Answer, helpful_votes: int) -> float:
    return answer_rank_score(
        helpful_votes=helpful_votes,
        faculty_verified=answer.faculty_verified,
        created_at=answer.created_at,
        now=datetime.now(timezone.utc),
    )


@router.get("/{question_id}/answers", response_model=list[AnswerResponse])
def get_answers(question_id: int, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    stmt = (
        select(
            Answer,
            User.full_name.label("author_name"),
            func.count(func.distinct(Vote.id))
            .filter(Vote.vote_type == "helpful")
            .label("helpful_votes"),
        )
        .join(User, Answer.author_id == User.id)
        .outerjoin(Vote, Answer.id == Vote.answer_id)
        .where(Answer.question_id == question_id)
        .group_by(Answer.id, User.full_name)
    )

    results = db.execute(stmt).all()
    rows = [
        (
            row[0],
            row[1],
            int(row[2] or 0),
        )
        for row in results
    ]
    rows.sort(
        key=lambda row: (
            answer_score(row[0], row[2]),
            row[0].created_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    return [
        build_answer_dict(
            answer,
            author_name,
            helpful_votes,
            ranking_score=answer_score(answer, helpful_votes),
        )
        for answer, author_name, helpful_votes in rows
    ]


@router.post(
    "/{question_id}/answers",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_answer(
    question_id: int,
    data: AnswerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    answer = Answer(
        question_id=question_id,
        author_id=current_user.id,
        body=data.body.strip(),
        faculty_verified=False,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)

    # Faculty verification is an explicit moderation signal, not automatic.
    return build_answer_dict(
        answer,
        current_user.full_name,
        helpful_votes=0,
        ranking_score=answer_score(answer, 0),
    )


@router.put("/answers/{answer_id}", response_model=AnswerResponse)
def update_answer(
    answer_id: int,
    data: AnswerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )

    if answer.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this answer",
        )

    answer.body = data.body.strip()
    db.commit()
    db.refresh(answer)

    helpful_votes = (
        db.scalar(
            select(func.count())
            .select_from(Vote)
            .where(
                Vote.answer_id == answer_id,
                Vote.vote_type == "helpful",
            )
        )
        or 0
    )
    author = db.get(User, answer.author_id)
    return build_answer_dict(
        answer,
        author.full_name if author else "Student",
        helpful_votes,
        answer_score(answer, helpful_votes),
    )


@router.delete("/answers/{answer_id}")
def delete_answer(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )

    if answer.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this answer",
        )

    db.delete(answer)
    db.commit()
    return {"message": "Answer deleted successfully"}


@router.patch(
    "/answers/{answer_id}/verification",
    response_model=AnswerResponse,
)
def verify_answer(
    answer_id: int,
    data: AnswerVerificationUpdate,
    current_user: User = Depends(require_role("faculty", "admin")),
    db: Session = Depends(get_db),
):
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )

    answer.faculty_verified = data.verified
    db.commit()
    db.refresh(answer)

    helpful_votes = (
        db.scalar(
            select(func.count())
            .select_from(Vote)
            .where(
                Vote.answer_id == answer_id,
                Vote.vote_type == "helpful",
            )
        )
        or 0
    )
    author = db.get(User, answer.author_id)
    return build_answer_dict(
        answer,
        author.full_name if author else "Student",
        helpful_votes,
        answer_score(answer, helpful_votes),
    )


@router.post("/answers/{answer_id}/helpful")
def helpful_answer(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    answer = db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found",
        )

    existing_vote = db.scalar(
        select(Vote).where(
            Vote.user_id == current_user.id,
            Vote.answer_id == answer_id,
            Vote.vote_type == "helpful",
        )
    )

    if existing_vote:
        db.delete(existing_vote)
        db.commit()
        message = "Helpful vote removed"
    else:
        new_vote = Vote(
            user_id=current_user.id,
            answer_id=answer_id,
            vote_type="helpful",
        )
        db.add(new_vote)
        try:
            db.commit()
            message = "Answer marked helpful"
        except IntegrityError:
            db.rollback()
            message = "Answer marked helpful"

    total_helpful = (
        db.scalar(
            select(func.count())
            .select_from(Vote)
            .where(
                Vote.answer_id == answer_id,
                Vote.vote_type == "helpful",
            )
        )
        or 0
    )

    return {
        "message": message,
        "helpful_votes": total_helpful,
        "ranking_score": answer_score(answer, total_helpful),
    }
