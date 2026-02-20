"""Refresh token use case."""

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.identity.application.dtos import TokensDTO
from app.modules.identity.infra.repositories.user_repository import UserRepository


class RefreshTokenUseCase:
    """Renova access_token a partir de um refresh_token válido."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def execute(self, refresh_token: str) -> TokensDTO:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Refresh token expirado")
        except jwt.InvalidTokenError:
            raise ValueError("Refresh token inválido")

        if payload.get("type") != "refresh":
            raise ValueError("Token não é do tipo refresh")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token inválido")

        user = self.repository.find_by_id(user_id)
        if not user or not user.is_active:
            raise ValueError("Usuário não encontrado ou desativado")

        access_token = self._create_token(
            data={"sub": str(user.id), "type": "access"},
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )

        new_refresh_token = self._create_token(
            data={"sub": str(user.id), "type": "refresh"},
            expires_delta=timedelta(days=settings.refresh_token_expire_days),
        )

        return TokensDTO(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )

    def _create_token(self, data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
