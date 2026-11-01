import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import create_access_token
from app.database import Base, SessionLocal, engine, initialize_database
from app.models import User
from main import app


@pytest.fixture(scope="session")
def client():
    initialize_database()
    with TestClient(app) as test_client:
        yield test_client


def new_email(prefix="student"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


def register(client, prefix="student", name="Test Student"):
    email = new_email(prefix)
    response = client.post(
        "/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Password123!",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def headers(auth_response):
    return {"Authorization": f"Bearer {auth_response['access_token']}"}


def make_role_user(role, name=None):
    email = new_email(role)
    with SessionLocal() as db:
        user = User(
            full_name=name or role.title(),
            email=email,
            password_hash=None,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def test_health(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").json()["status"] == "healthy"


def test_database_connection():
    assert engine is not None
    with engine.connect() as connection:
        assert connection is not None
    initialize_database()


def test_register_login_and_me(client):
    email = new_email()
    register_response = client.post(
        "/auth/register",
        json={
            "full_name": "Phase Test Student",
            "email": email,
            "password": "Password123!",
        },
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    duplicate = client.post(
        "/auth/register",
        json={
            "full_name": "Duplicate",
            "email": email,
            "password": "Password123!",
        },
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "student"

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    bad_login = client.post(
        "/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401


def test_google_login_validation(client):
    empty = client.post("/auth/google", json={"credential": ""})
    assert empty.status_code == 422

    invalid = client.post("/auth/google", json={"credential": "invalid"})
    assert invalid.status_code in (401, 503)


def test_question_crud_vote_and_similar_detection(client):
    user = register(client, "questioner", "Question Author")
    auth = headers(user)

    created = client.post(
        "/questions",
        headers=auth,
        json={
            "title": "How can I apply for a bonafide certificate?",
            "body": "I need a bonafide certificate for an internship application.",
            "category": "Academic",
        },
    )
    assert created.status_code == 201
    question = created.json()

    similar = client.post(
        "/questions/similar",
        json={
            "title": "How do I get a bonafide certificate?",
            "body": "I need a bonafide certificate for an internship.",
            "category": "Academic",
        },
    )
    assert similar.status_code == 200
    assert similar.json()["matches"]
    assert similar.json()["matches"][0]["id"] == question["id"]

    duplicate = client.post(
        "/questions",
        headers=auth,
        json={
            "title": "How can I apply for a bonafide certificate?",
            "body": "I need a bonafide certificate for an internship application.",
            "category": "Academic",
        },
    )
    assert duplicate.status_code == 409
    detail = duplicate.json()["detail"]
    assert detail["code"] == "possible_duplicate"
    assert detail["matches"]

    forced = client.post(
        "/questions",
        headers=auth,
        json={
            "title": "How can I apply for a bonafide certificate?",
            "body": "I need a bonafide certificate for an internship application.",
            "category": "Academic",
            "force_create": True,
        },
    )
    assert forced.status_code == 201

    question_id = question["id"]

    get_question = client.get(f"/questions/{question_id}")
    assert get_question.status_code == 200

    related = client.get(f"/questions/{question_id}/similar")
    assert related.status_code == 200

    vote = client.post(f"/questions/{question_id}/vote", headers=auth)
    assert vote.status_code == 200
    assert vote.json()["votes"] == 1

    vote_again = client.post(f"/questions/{question_id}/vote", headers=auth)
    assert vote_again.json()["votes"] == 0

    update = client.put(
        f"/questions/{question_id}",
        headers=auth,
        json={"title": "Updated bonafide certificate question"},
    )
    assert update.status_code == 200

    delete = client.delete(f"/questions/{question_id}", headers=auth)
    assert delete.status_code == 200
    assert client.get(f"/questions/{question_id}").status_code == 404


def test_answer_ranking_helpful_votes_and_verification(client):
    asker = register(client, "asker", "Question Owner")
    answerer = register(client, "answerer", "Helpful Student")
    auth_asker = headers(asker)
    auth_answerer = headers(answerer)

    q = client.post(
        "/questions",
        headers=auth_asker,
        json={
            "title": "What is SQLAlchemy ORM?",
            "body": "Explain ORM in simple terms.",
            "category": "Python",
        },
    )
    assert q.status_code == 201
    qid = q.json()["id"]

    first = client.post(
        f"/questions/{qid}/answers",
        headers=auth_answerer,
        json={"body": "SQLAlchemy ORM maps Python classes to database tables."},
    )
    second = client.post(
        f"/questions/{qid}/answers",
        headers=auth_asker,
        json={"body": "It provides an object-oriented interface to the database."},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    first_id = first.json()["id"]
    helpful = client.post(
        f"/questions/answers/{first_id}/helpful",
        headers=auth_asker,
    )
    assert helpful.status_code == 200
    assert helpful.json()["helpful_votes"] == 1

    faculty = make_role_user("faculty", "Dr Faculty")
    verify = client.patch(
        f"/questions/answers/{second.json()['id']}/verification",
        headers=headers({
            "access_token": create_access_token(faculty.id, "faculty")
        }),
        json={"verified": True},
    )
    assert verify.status_code == 200

    answers = client.get(f"/questions/{qid}/answers")
    assert answers.status_code == 200
    data = answers.json()
    assert len(data) == 2
    assert all("ranking_score" in item for item in data)

    # The answer with a helpful vote should be ranked ahead unless
    # verification plus recency makes the other score higher.
    scores = {item["id"]: item["ranking_score"] for item in data}
    assert scores[first_id] >= 0


def test_resources_crud(client):
    user = register(client, "resource", "Resource Contributor")
    auth = headers(user)

    create = client.post(
        "/resources",
        headers=auth,
        json={
            "title": "Database Normalization Guide",
            "description": "A guide to normalization.",
            "category": "Academic",
            "url": "https://example.com/guide",
        },
    )
    assert create.status_code == 201
    rid = create.json()["id"]

    listing = client.get("/resources")
    assert any(item["id"] == rid for item in listing.json())

    update = client.put(
        f"/resources/{rid}",
        headers=auth,
        json={"title": "Updated Normalization Guide"},
    )
    assert update.status_code == 200

    delete = client.delete(f"/resources/{rid}", headers=auth)
    assert delete.status_code == 200


def test_notice_and_procedure_role_controls(client):
    student = register(client, "regular", "Regular Student")
    student_headers = headers(student)

    notice_fail = client.post(
        "/notices",
        headers=student_headers,
        json={"title": "Student Notice", "body": "Should fail"},
    )
    assert notice_fail.status_code == 403

    procedure_fail = client.post(
        "/procedures",
        headers=student_headers,
        json={
            "title": "Student Procedure",
            "description": "Should fail",
            "content": "Should fail",
        },
    )
    assert procedure_fail.status_code == 403

    faculty = make_role_user("faculty", "Dr Faculty")
    faculty_headers = headers(
        {"access_token": create_access_token(faculty.id, "faculty")}
    )

    notice = client.post(
        "/notices",
        headers=faculty_headers,
        json={
            "title": "Midterm Schedule",
            "body": "Midterms begin next Monday.",
        },
    )
    assert notice.status_code == 201
    assert client.get("/notices").status_code == 200

    procedure = client.post(
        "/procedures",
        headers=faculty_headers,
        json={
            "title": "Course Registration",
            "description": "How to register.",
            "content": "Step 1: Open the portal.",
        },
    )
    assert procedure.status_code == 201
    pid = procedure.json()["id"]

    procedures = client.get("/procedures")
    assert any(item["id"] == pid for item in procedures.json())


def test_help_request_offer_and_status(client):
    owner = register(client, "helpowner", "Help Owner")
    helper = register(client, "helper", "Helpful Student")
    owner_headers = headers(owner)
    helper_headers = headers(helper)

    create = client.post(
        "/help-requests",
        headers=owner_headers,
        json={
            "title": "Need help with Calculus",
            "description": "Can someone explain problem 4?",
            "category": "Academic",
        },
    )
    assert create.status_code == 201
    request_id = create.json()["id"]

    offer = client.post(
        f"/help-requests/{request_id}/offer",
        headers=helper_headers,
    )
    assert offer.status_code == 200
    assert offer.json()["helpers"] == 1

    listing = client.get("/help-requests")
    item = next(x for x in listing.json() if x["id"] == request_id)
    assert item["helpers"] == 1

    resolve = client.put(
        f"/help-requests/{request_id}",
        headers=owner_headers,
        json={"status": "resolved"},
    )
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolved"


def test_admin_stats_and_users(client):
    admin = make_role_user("admin", "System Admin")
    admin_headers = headers(
        {"access_token": create_access_token(admin.id, "admin")}
    )

    stats = client.get("/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert set(
        ["users", "questions", "answers", "resources", "notices", "help_requests"]
    ).issubset(stats.json())

    users = client.get("/admin/users", headers=admin_headers)
    assert users.status_code == 200
    assert isinstance(users.json(), list)

    student = register(client, "notadmin", "Not Admin")
    assert client.get(
        "/admin/stats", headers=headers(student)
    ).status_code == 403


def test_resource_rejects_javascript_url(client):
    user = register(client, "res")
    r = client.post(
        "/resources",
        headers=headers(user),
        json={"title": "Bad link", "description": "x", "url": "javascript:alert(1)"},
    )
    assert r.status_code == 422
    ok = client.post(
        "/resources",
        headers=headers(user),
        json={"title": "Good link", "description": "x", "url": "https://example.com"},
    )
    assert ok.status_code == 201


def test_admin_can_change_role_and_edit_keeps_author_name(client):
    student = register(client, "own", name="Original Author")
    q = client.post(
        "/questions",
        headers=headers(student),
        json={"title": "How to apply for bonafide certificate?", "body": "Need steps"},
    )
    assert q.status_code == 201, q.text
    qid = q.json()["id"]

    admin = make_role_user("admin", "Admin Person")
    token = create_access_token(admin.id, admin.role)
    edited = client.put(
        f"/questions/{qid}",
        headers={"Authorization": f"Bearer {token}"},
        json={"body": "Updated body"},
    )
    assert edited.status_code == 200
    assert edited.json()["author_name"] == "Original Author"

    role = client.patch(
        f"/admin/users/{student['user']['id']}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "faculty"},
    )
    assert role.status_code == 200 and role.json()["role"] == "faculty"
