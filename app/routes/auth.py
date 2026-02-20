"""Routes for authentication."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.identity.application.dtos import RegisterInput, LoginInput
from app.modules.identity.application.use_cases.login_use_case import LoginUseCase
from app.modules.identity.application.use_cases.refresh_token_use_case import (
    RefreshTokenUseCase,
)
from app.modules.identity.application.use_cases.register_use_case import (
    RegisterUseCase,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Cria um novo usuário."""
    use_case = RegisterUseCase(db)
    try:
        user = use_case.execute(
            RegisterInput(
                email=request.email,
                password=request.password,
                full_name=request.full_name,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return vars(user)


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Autentica e retorna tokens JWT."""
    use_case = LoginUseCase(db)
    try:
        tokens = use_case.execute(
            LoginInput(email=request.email, password=request.password)
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return vars(tokens)


@router.post("/refresh")
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """Renova access_token a partir de refresh_token."""
    use_case = RefreshTokenUseCase(db)
    try:
        tokens = use_case.execute(request.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return vars(tokens)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    """Retorna dados do usuário logado."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
    }
