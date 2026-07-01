import sqlite3
from src.config import DB_PATH


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
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
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS day_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_date TEXT,
        wake_time TEXT,
        sleep_time TEXT,
        diet_type TEXT,
        fitness_type TEXT,
        workout_duration TEXT,
        events_json TEXT,
        analysis_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_id INTEGER,
        rating INTEGER,
        comments TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()





# import psycopg2
# from psycopg2.extras import RealDictCursor
# from app.config import DATABASE_URL


# def get_connection():
#     return psycopg2.connect(
#         DATABASE_URL,
#         cursor_factory=RealDictCursor
#     )


# def create_tables():
#     conn = get_connection()
#     cur = conn.cursor()

#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS users (
#         id SERIAL PRIMARY KEY,
#         name TEXT NOT NULL,
#         email TEXT UNIQUE NOT NULL,
#         phone TEXT,
#         password_hash TEXT NOT NULL,
#         height REAL,
#         weight REAL,
#         gender TEXT,
#         age INTEGER,
#         profession TEXT,
#         diseases TEXT,
#         disability TEXT,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     """)

#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS day_plans (
#         id SERIAL PRIMARY KEY,
#         user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
#         plan_date TEXT,
#         wake_time TEXT,
#         sleep_time TEXT,
#         diet_type TEXT,
#         fitness_type TEXT,
#         workout_duration TEXT,
#         events_json JSONB,
#         analysis_json JSONB,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     """)

#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS feedback (
#         id SERIAL PRIMARY KEY,
#         user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
#         plan_id INTEGER REFERENCES day_plans(id) ON DELETE CASCADE,
#         rating INTEGER,
#         comments TEXT,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
#     """)

#     conn.commit()
#     cur.close()
#     conn.close()
