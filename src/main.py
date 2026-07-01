from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.db.database import create_tables
from src.routes.auth import router as auth_router, profile_router
from src.routes.analytics import router as analytics_router
from src.routes.planner import router as planner_router
from src.observability import setup_observability

create_tables()
app = FastAPI(title="AI Day Planner API", version="1.0.0")
setup_observability(app)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(analytics_router)
app.include_router(planner_router)


@app.get("/")
def root():
    return {"message": "AI Day Planner API is running", "docs": "http://127.0.0.1:8000/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
