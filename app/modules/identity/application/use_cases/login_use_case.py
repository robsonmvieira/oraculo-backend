"""Login use case."""

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.identity.application.dtos import LoginInput, TokensDTO
from app.modules.identity.application.password import verify_password
from app.modules.identity.infra.repositories.user_repository import UserRepository


class LoginUseCase:
    """Autentica um usuário e retorna tokens JWT."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def execute(self, input_data: LoginInput) -> TokensDTO:
        user = self.repository.find_by_email(input_data.email)
        if not user or not verify_password(input_data.password, user.password_hash):
            raise ValueError("Email ou senha inválidos")

        if not user.is_active:
            raise ValueError("Conta desativada")

        access_token = self._create_token(
            data={"sub": str(user.id), "type": "access"},
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )

        refresh_token = self._create_token(
            data={"sub": str(user.id), "type": "refresh"},
            expires_delta=timedelta(days=settings.refresh_token_expire_days),
        )

        return TokensDTO(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def _create_token(self, data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
