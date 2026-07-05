import sqlite3
from contextlib import suppress

from src.config import DB_PATH, DATABASE_URL

try:
    import psycopg2
    from psycopg2 import sql as pg_sql
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover - optional dependency
    psycopg2 = None
    pg_sql = None
    RealDictCursor = None


DB_URL = str(DATABASE_URL or "").strip()
USE_POSTGRES = DB_URL.startswith(("postgresql://", "postgres://")) and psycopg2 is not None
DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + ((psycopg2.IntegrityError,) if psycopg2 is not None else ())


class CursorAdapter:
    def __init__(self, cursor, backend: str):
        self._cursor = cursor
        self._backend = backend
        self._lastrowid = None

    def execute(self, query, params=None):
        params = params or ()
        translated = query.replace("?", "%s") if self._backend == "postgresql" else query
        self._cursor.execute(translated, params)

        if self._backend == "postgresql" and translated.lstrip().upper().startswith("INSERT") and "RETURNING" not in translated.upper():
            with suppress(Exception):
                self._cursor.execute("SELECT LASTVAL()")
                row = self._cursor.fetchone()
                if row is None:
                    self._lastrowid = None
                elif isinstance(row, dict):
                    self._lastrowid = next(iter(row.values()), None)
                else:
                    try:
                        self._lastrowid = row[0]
                    except Exception:
                        self._lastrowid = next(iter(row), None)
        else:
            self._lastrowid = getattr(self._cursor, "lastrowid", None)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return row

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    @property
    def lastrowid(self):
        return self._lastrowid

    def __getattr__(self, item):
        return getattr(self._cursor, item)


class ConnectionAdapter:
    def __init__(self, conn, backend: str):
        self._conn = conn
        self._backend = backend

    def cursor(self):
        if self._backend == "postgresql":
            return CursorAdapter(self._conn.cursor(cursor_factory=RealDictCursor), self._backend)
        return CursorAdapter(self._conn.cursor(), self._backend)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def __getattr__(self, item):
        return getattr(self._conn, item)


def _get_sqlite_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return ConnectionAdapter(conn, "sqlite")


def _get_postgres_connection():
    conn = psycopg2.connect(DB_URL)
    return ConnectionAdapter(conn, "postgresql")


def get_connection():
    if USE_POSTGRES:
        try:
            return _get_postgres_connection()
        except Exception:
            return _get_sqlite_connection()
    return _get_sqlite_connection()


def _create_tables_sql(backend: str):
    if backend == "postgresql":
        return [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
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
            """,
            """
            CREATE TABLE IF NOT EXISTS day_plans (
                id SERIAL PRIMARY KEY,
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
            """,
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                plan_id INTEGER,
                rating INTEGER,
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ]

    return [
        """
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
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_id INTEGER,
            rating INTEGER,
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]


def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    for statement in _create_tables_sql(getattr(conn, "_backend", "sqlite")):
        cur.execute(statement)
    conn.commit()
    conn.close()
