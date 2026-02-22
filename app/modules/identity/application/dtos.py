"""DTOs for identity module."""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class RegisterInput:
    """Input para registro de usuário."""

    email: str
    password: str
    full_name: str


@dataclass
class LoginInput:
    """Input para login."""

    email: str
    password: str


@dataclass
class UserDTO:
    """Output de usuário (sem dados sensíveis)."""

    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    bio: Optional[str] = None
    locale: Optional[str] = None
    phone_number: Optional[str] = None


@dataclass
class UpdateProfileInput:
    """Input para atualização de perfil."""

    bio: Optional[str] = None
    locale: Optional[str] = None
    phone_number: Optional[str] = None


@dataclass
class TokensDTO:
    """Output de tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
