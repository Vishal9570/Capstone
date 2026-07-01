# AI Day Planner

FastAPI backend + Streamlit UI for a multi-agent day planner.

## What is included
- Signup / login and user profile storage
- Agent 1 day plan generation with OpenAI primary and Gemini fallback
- Agent 2 history analysis with Groq
- Agent 3 safety feedback with Anthropic primary and Cohere fallback
- Office-time validation against wake/sleep timing
- Disease-aware meal suggestions
- Reading activity embedded in the plan table
- Health tip returned after plan generation
- Prometheus, Grafana, and Loki observability

## Environment
Put API keys and database settings in `Capstone/.env`:

```env
OPENAI_API_KEY=...
GEMINI_API_KEY=...
GROQ_API_KEY=...
ANTHROPIC_API_KEY=...
COHERE_API_KEY=...
DATABASE_URL=postgresql://postgres:admin123@localhost:5432/ai_day_planner
```

The current code uses SQLite for local persistence and creates the database file automatically at `data/day_planner.db`. The `DATABASE_URL` value is kept for compatibility with the older PostgreSQL path, but you do not need to set up Postgres for the current SQLite-backed build.

## Run Backend

```powershell
cd C:\Training\AI-ML-Training-Projects\Capstone
venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

Backend docs:
- `http://127.0.0.1:8000/docs`

## Run UI

```powershell
cd C:\Training\AI-ML-Training-Projects\Capstone
venv\Scripts\activate
streamlit run ui/app.py
```

The Streamlit app expects the backend at `http://127.0.0.1:8000`.

## Observability

Start the monitoring stack:

```powershell
cd C:\Training\AI-ML-Training-Projects\Capstone
docker compose -f observability/docker-compose.observability.yml up -d
```

Then open:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Loki: `http://localhost:3100`

The backend exposes:
- `/metrics` for Prometheus
- JSON-line logs in `logs/capstone.jsonl`

## Notes
- If Streamlit does not open on `http://localhost:8501`, check whether another process such as Docker Desktop already owns that port and stop it before starting the UI.
- Office time must fit inside the awake window or the API will return a 400 error.
