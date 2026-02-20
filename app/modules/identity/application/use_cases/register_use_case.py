"""Register use case."""

from sqlalchemy.orm import Session

from app.modules.identity.application.dtos import RegisterInput, UserDTO
from app.modules.identity.application.password import hash_password
from app.modules.identity.infra.repositories.user_repository import UserRepository


class RegisterUseCase:
    """Cria um novo usuário."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def execute(self, input_data: RegisterInput) -> UserDTO:
        existing = self.repository.find_by_email(input_data.email)
        if existing:
            raise ValueError("Email já cadastrado")

        password_hash = hash_password(input_data.password)

        user = self.repository.create(
            email=input_data.email,
            password_hash=password_hash,
            full_name=input_data.full_name,
        )

        return UserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
        )
