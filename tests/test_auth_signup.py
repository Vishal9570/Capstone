from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


def test_signup_accepts_trimmed_email_and_creates_user():
    client = TestClient(app)
    unique_email = f"signup-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "name": "Signup User",
            "email": f"  {unique_email}  ",
            "phone": "9999999999",
            "password": "secret123",
            "height": 170,
            "weight": 70,
            "gender": "Male",
            "age": 28,
            "profession": "Engineer",
            "diseases": ["None"],
            "disability": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == unique_email


def test_signup_rejects_duplicate_email():
    client = TestClient(app)
    unique_email = f"duplicate-{uuid4().hex[:8]}@example.com"

    payload = {
        "name": "Duplicate User",
        "email": unique_email,
        "phone": "9999999999",
        "password": "secret123",
        "height": 170,
        "weight": 70,
        "gender": "Male",
        "age": 28,
        "profession": "Engineer",
        "diseases": ["None"],
        "disability": "",
    }

    first = client.post("/auth/signup", json=payload)
    second = client.post("/auth/signup", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"] == "Email already exists."
