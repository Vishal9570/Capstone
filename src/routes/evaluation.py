from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from src.services.deepeval_service import evaluate_day_plan


router = APIRouter(prefix="/deepeval", tags=["DeepEval"])


class DeepEvalRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    health_tip: str = ""


@router.post("/evaluate")
def evaluate_plan(req: DeepEvalRequest):
    if not req.events:
        raise HTTPException(status_code=400, detail="At least one event is required for evaluation.")

    result = evaluate_day_plan(req.profile, req.preferences, req.events, req.health_tip)
    return result.as_dict()


@router.get("/evaluate")
def evaluate_help():
    return {
        "status": "ok",
        "message": "Use POST /deepeval/evaluate to run a DeepEval plan evaluation.",
        "health": "/deepeval/health",
    }


@router.get("/health")
def deepeval_health():
    return {
        "status": "ok",
        "evaluation": "/deepeval/evaluate",
        "method": "POST",
    }
