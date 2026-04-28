from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.auth_repository import AuthRepository
from app.schemas import LoginRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(AuthRepository(db))
    service.ensure_seed_admin()
    result = service.login(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=result["access_token"], role=result["role"])
