from fastapi import APIRouter, HTTPException
from src.models import SignupRequest, LoginRequest, UpdateProfileRequest
from src.services.auth_service import create_user, verify_login, get_user_by_email, get_user_by_id
from src.db.database import get_connection

router = APIRouter(prefix="/auth", tags=["Auth"])
profile_router = APIRouter(tags=["Profile"])


@router.post("/signup")
def signup(req: SignupRequest):
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already exists.")
    user = create_user(req)
    user.pop("password_hash", None)
    return {"message": "Signup successful", "user": user}


@router.post("/login")
def login(req: LoginRequest):
    user, login_type = verify_login(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail=login_type)
    user.pop("password_hash", None)
    return {"message": "Login successful", "login_type": login_type, "user": user}

def _update_profile_impl(req: UpdateProfileRequest):
    user = get_user_by_id(req.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conn = get_connection()
    cur = conn.cursor()

    diseases = ", ".join(req.diseases or [])

    cur.execute(
        """
        UPDATE users
        SET phone = ?,
            height = ?,
            weight = ?,
            age = ?,
            profession = ?,
            diseases = ?,
            disability = ?
        WHERE id = ?
        """,
        (
            req.phone,
            req.height,
            req.weight,
            req.age,
            req.profession,
            diseases,
            req.disability,
            req.user_id,
        ),
    )

    conn.commit()
    conn.close()

    updated_user = get_user_by_id(req.user_id)
    updated_user.pop("password_hash", None)

    return {
        "message": "Profile updated successfully",
        "user": updated_user,
    }


@router.post("/profile/update")
def update_profile(req: UpdateProfileRequest):
    return _update_profile_impl(req)


@profile_router.post("/profile/update")
def update_profile_legacy(req: UpdateProfileRequest):
    return _update_profile_impl(req)
