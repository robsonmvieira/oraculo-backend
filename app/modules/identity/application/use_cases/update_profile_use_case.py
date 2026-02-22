"""Update profile use case."""

from sqlalchemy.orm import Session

from app.modules.identity.application.dtos import UpdateProfileInput, UserDTO
from app.modules.identity.domain.entities.user import User
from app.modules.identity.infra.repositories.user_repository import UserRepository


class UpdateProfileUseCase:
    """Atualiza o perfil do usuário."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def execute(self, user: User, input_data: UpdateProfileInput) -> UserDTO:
        updated_user = self.repository.update_profile(
            user,
            bio=input_data.bio,
            locale=input_data.locale,
            phone_number=input_data.phone_number,
        )

        return UserDTO(
            id=updated_user.id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            is_active=updated_user.is_active,
            is_superuser=updated_user.is_superuser,
            bio=updated_user.bio,
            locale=updated_user.locale,
            phone_number=updated_user.phone_number,
        )
