"""Repository for User entity."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.identity.domain.entities.user import User


class UserRepository:
    """Repositório para operações com users."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, email: str, password_hash: str, full_name: str) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            full_name=full_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def find_by_id(self, user_id: UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def find_by_email(self, email: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.email == email.lower().strip())
            .first()
        )

    def update_profile(self, user: User, **fields) -> User:
        for key, value in fields.items():
            if value is not None:
                setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user
