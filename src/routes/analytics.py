from fastapi import APIRouter

from src.services.profession_analytics import get_profession_comparison

router = APIRouter(tags=["Analytics"])


@router.get("/analytics/professions")
def profession_analytics():
    rows = get_profession_comparison()
    return {
        "items": rows,
        "count": len(rows),
    }
