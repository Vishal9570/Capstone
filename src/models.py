from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from typing import List, Dict, Any, Optional

class SignupRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: str
    height: float
    weight: float
    gender: str
    age: int
    profession: str
    diseases: Optional[List[str]] = []
    disability: Optional[str] = ""


class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None


class DayPlanRequest(BaseModel):
    user_id: int
    wake_time: str
    sleep_time: str
    diet_type: str
    fitness_type: str
    workout_duration: str
    phone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = {}


class FeedbackRequest(BaseModel):
    user_id: int
    plan_id: int
    rating: int
    comments: Optional[str] = ""


class UpdatePlanRequest(BaseModel):
    user_id: int
    plan_id: Optional[int] = None
    wake_time: str
    sleep_time: str
    diet_type: str
    fitness_type: str
    workout_duration: str
    events: List[Dict[str, Any]]


class FinalizePlanRequest(BaseModel):
    user_id: int
    plan_id: Optional[int] = None
    wake_time: str
    sleep_time: str
    diet_type: str
    fitness_type: str
    workout_duration: str
    events: List[Dict[str, Any]]
    preferences: Optional[Dict[str, Any]] = {}

class UpdateProfileRequest(BaseModel):
    user_id: int
    phone: str | None = None
    height: float
    weight: float
    age: int
    profession: str | None = None
    diseases: list[str] = []
    disability: str | None = None
