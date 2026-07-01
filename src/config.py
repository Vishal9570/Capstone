import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH, override=True)

DB_PATH = BASE_DIR / "data" / "day_planner.db"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
COHERE_MODEL = os.getenv("COHERE_MODEL", "command-r-plus-08-2024")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:admin123@localhost:5432/ai_day_planner"
)

# Backward-compatible aliases used by older modules during the migration.
AZURE_OPENAI_API_KEY = OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = OPENAI_MODEL
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
PROJECT_ENV_PATH = ENV_PATH
LOG_DIR = BASE_DIR / "logs"
