import hashlib
from src.db.database import get_connection


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_user_by_id(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(data):
    conn = get_connection()
    cur = conn.cursor()
    diseases = ", ".join(data.diseases or [])
    cur.execute("""
    INSERT INTO users
    (name, email, phone, password_hash, height, weight, gender, age, profession, diseases, disability)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.name, data.email.lower(), data.phone, hash_password(data.password),
        data.height, data.weight, data.gender, data.age,
        data.profession, diseases, data.disability
    ))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return get_user_by_id(user_id)


def verify_login(email: str, password: str | None):
    user = get_user_by_email(email)
    if not user:
        return None, "Email not found"
    # Demo: email-only login allowed. For production, always require password.
    if not password:
        return user, "email_login"
    if user["password_hash"] == hash_password(password):
        return user, "password_login"
    return None, "Invalid password"
