import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Answer, Question, User, Vote
from app.schemas import (
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
    SimilarQuestionsResponse,
)
from app.services.question_similarity import find_similar_questions

load_dotenv()

router = APIRouter(prefix="/questions", tags=["Questions"])

SUGGESTION_THRESHOLD = float(os.getenv("QUESTION_SIMILARITY_THRESHOLD", "0.35"))
DUPLICATE_THRESHOLD = float(os.getenv("QUESTION_DUPLICATE_THRESHOLD", "0.72"))
SIMILAR_LIMIT = int(os.getenv("QUESTION_SIMILARITY_LIMIT", "5"))


def build_question_dict(
    q: Question,
    author_name: str,
    votes_count: int,
    answers_count: int,
) -> dict:
    return {
        "id": q.id,
        "title": q.title,
        "body": q.body,
        "description": q.body,
        "category": q.category,
        "author_id": q.author_id,
        "author_name": author_name,
        "votes": votes_count,
        "answers": answers_count,
        "created_at": q.created_at,
        "updated_at": q.updated_at,
    }


def similar_questions_for(title: str, body: str, db: Session) -> list[dict]:
    candidates = db.scalars(
        select(Question).order_by(Question.created_at.desc())
    ).all()

    return find_similar_questions(
        title,
        body,
        candidates,
        limit=SIMILAR_LIMIT,
        suggestion_threshold=SUGGESTION_THRESHOLD,
        duplicate_threshold=DUPLICATE_THRESHOLD,
    )


@router.post("/similar", response_model=SimilarQuestionsResponse)
def find_similar(
    data: QuestionCreate,
    db: Session = Depends(get_db),
):
    matches = similar_questions_for(data.title.strip(), data.body.strip(), db)
    return {
        "matches": matches,
        "suggestion_threshold": SUGGESTION_THRESHOLD,
        "duplicate_threshold": DUPLICATE_THRESHOLD,
    }


@router.get("", response_model=list[QuestionResponse])
def list_questions(db: Session = Depends(get_db)):
    stmt = (
        select(
            Question,
            User.full_name.label("author_name"),
            func.count(func.distinct(Vote.id))
            .filter(Vote.vote_type == "upvote")
            .label("votes_count"),
            func.count(func.distinct(Answer.id)).label("answers_count"),
        )
        .join(User, Question.author_id == User.id)
        .outerjoin(Vote, Question.id == Vote.question_id)
        .outerjoin(Answer, Question.id == Answer.question_id)
        .group_by(Question.id, User.full_name)
        .order_by(Question.created_at.desc())
    )

    results = db.execute(stmt).all()
    return [
        build_question_dict(row[0], row[1], row[2], row[3])
        for row in results
    ]


@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    data: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = data.title.strip()
    body = data.body.strip()

    matches = similar_questions_for(title, body, db)
    duplicates = [m for m in matches if m["possible_duplicate"]]

    if duplicates and not data.force_create:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "possible_duplicate",
                "message": "Similar questions already exist. Review them before posting.",
                "matches": duplicates,
            },
        )

    question = Question(
        title=title,
        body=body,
        category=(data.category or "General").strip() or "General",
        author_id=current_user.id,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    return build_question_dict(
        question,
        current_user.full_name,
        votes_count=0,
        answers_count=0,
    )


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(
            Question,
            User.full_name.label("author_name"),
            func.count(func.distinct(Vote.id))
            .filter(Vote.vote_type == "upvote")
            .label("votes_count"),
            func.count(func.distinct(Answer.id)).label("answers_count"),
        )
        .join(User, Question.author_id == User.id)
        .outerjoin(Vote, Question.id == Vote.question_id)
        .outerjoin(Answer, Question.id == Answer.question_id)
        .where(Question.id == question_id)
        .group_by(Question.id, User.full_name)
    )

    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    return build_question_dict(result[0], result[1], result[2], result[3])


@router.get("/{question_id}/similar", response_model=SimilarQuestionsResponse)
def similar_to_existing_question(
    question_id: int,
    db: Session = Depends(get_db),
):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    candidates = db.scalars(
        select(Question)
        .where(Question.id != question_id)
        .order_by(Question.created_at.desc())
    ).all()

    matches = find_similar_questions(
        question.title,
        question.body,
        candidates,
        limit=SIMILAR_LIMIT,
        suggestion_threshold=SUGGESTION_THRESHOLD,
        duplicate_threshold=DUPLICATE_THRESHOLD,
    )

    return {
        "matches": matches,
        "suggestion_threshold": SUGGESTION_THRESHOLD,
        "duplicate_threshold": DUPLICATE_THRESHOLD,
    }




@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if question.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this question",
        )

    if data.title is not None:
        question.title = data.title.strip()
    if data.body is not None:
        question.body = data.body.strip()
    if data.category is not None:
        question.category = data.category.strip() or "General"

    db.commit()
    db.refresh(question)

    votes = (
        db.scalar(
            select(func.count())
            .select_from(Vote)
            .where(Vote.question_id == question_id, Vote.vote_type == "upvote")
        )
        or 0
    )
    answers = (
        db.scalar(
            select(func.count())
            .select_from(Answer)
            .where(Answer.question_id == question_id)
        )
        or 0
    )
    author = db.get(User, question.author_id)
    return build_question_dict(
        question,
        author.full_name if author else "Student",
        votes,
        answers,
    )


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    if question.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this question",
        )

    db.delete(question)
    db.commit()
    return {"message": "Question deleted successfully"}


@router.post("/{question_id}/vote")
def vote_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    existing_vote = db.scalar(
        select(Vote).where(
            Vote.user_id == current_user.id,
            Vote.question_id == question_id,
            Vote.vote_type == "upvote",
        )
    )

    if existing_vote:
        db.delete(existing_vote)
        db.commit()
        message = "Vote removed"
    else:
        new_vote = Vote(
            user_id=current_user.id,
            question_id=question_id,
            vote_type="upvote",
        )
        db.add(new_vote)
        try:
            db.commit()
            message = "Question upvoted"
        except IntegrityError:
            db.rollback()
            message = "Question upvoted"

    total_votes = (
        db.scalar(
            select(func.count())
            .select_from(Vote)
            .where(
                Vote.question_id == question_id,
                Vote.vote_type == "upvote",
            )
        )
        or 0
    )

    return {"message": message, "votes": total_votes}
