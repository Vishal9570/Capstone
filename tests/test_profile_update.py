import sqlite3

from fastapi.testclient import TestClient

from src.main import app
from src.routes import auth as auth_routes


def _make_temp_db(tmp_path):
    db_path = tmp_path / "test_profile_update.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            height REAL,
            weight REAL,
            gender TEXT,
            age INTEGER,
            profession TEXT,
            diseases TEXT,
            disability TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        INSERT INTO users (name, email, phone, password_hash, height, weight, gender, age, profession, diseases, disability)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Test User", "test@example.com", "1111111111", "hash", 170, 70, "Male", 30, "Engineer", "", ""),
    )
    conn.commit()
    return conn


def test_profile_update_endpoint_available_on_both_paths(monkeypatch, tmp_path):
    conn = _make_temp_db(tmp_path)
    db_path = tmp_path / "test_profile_update.db"
    conn.close()

    def _get_user_by_id(user_id):
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db.close()
        return dict(row) if row else None

    def _get_connection():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        return db

    monkeypatch.setattr(auth_routes, "get_user_by_id", _get_user_by_id)
    monkeypatch.setattr(auth_routes, "get_connection", _get_connection)

    client = TestClient(app)
    payload = {
        "user_id": 1,
        "phone": "2222222222",
        "height": 171,
        "weight": 68,
        "age": 31,
        "profession": "Architect",
        "diseases": ["Sugar", "BP"],
        "disability": "None",
    }

    response = client.post("/auth/profile/update", json=payload)
    assert response.status_code == 200
    assert "Sugar" in response.json()["user"]["diseases"]

    response_alias = client.post("/profile/update", json=payload)
    assert response_alias.status_code == 200
    assert "BP" in response_alias.json()["user"]["diseases"]
