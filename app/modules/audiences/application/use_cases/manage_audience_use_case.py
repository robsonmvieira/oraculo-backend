from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)


@dataclass
class AudienceDTO:
    """DTO de audiência."""

    id: UUID
    name: str
    description: str | None
    user_id: UUID
    communities_count: int


@dataclass
class CreateAudienceInput:
    """Input para criar audiência."""

    name: str
    user_id: UUID
    description: str | None = None
    subreddit_names: list[str] = field(default_factory=list)


@dataclass
class UpdateAudienceInput:
    """Input para atualizar audiência."""

    name: str | None = None
    description: str | None = None
    subreddit_names: list[str] | None = None


class CreateAudienceUseCase:
    """Cria uma nova audiência com comunidades opcionais."""

    def __init__(self, db: Session):
        self.repository = AudienceRepository(db)

    def execute(self, input_data: CreateAudienceInput) -> AudienceDTO:
        audience = self.repository.create(
            name=input_data.name,
            description=input_data.description,
            user_id=input_data.user_id,
        )

        for subreddit_name in input_data.subreddit_names:
            self.repository.add_community(audience.id, subreddit_name)

        communities_count = len(input_data.subreddit_names)

        return AudienceDTO(
            id=audience.id,
            name=audience.name,
            description=audience.description,
            user_id=audience.user_id,
            communities_count=communities_count,
        )


class UpdateAudienceUseCase:
    """Atualiza uma audiência existente."""

    def __init__(self, db: Session):
        self.repository = AudienceRepository(db)

    def execute(
        self, audience_id: UUID, input_data: UpdateAudienceInput
    ) -> AudienceDTO | None:
        audience = self.repository.update(
            audience_id=audience_id,
            name=input_data.name,
            description=input_data.description,
        )
        if not audience:
            return None

        if input_data.subreddit_names is not None:
            communities = self.repository.sync_communities(
                audience_id, input_data.subreddit_names
            )
            communities_count = len(communities)
        else:
            communities_count = len(audience.communities)

        return AudienceDTO(
            id=audience.id,
            name=audience.name,
            description=audience.description,
            user_id=audience.user_id,
            communities_count=communities_count,
        )


class DeleteAudienceUseCase:
    """Remove uma audiência."""

    def __init__(self, db: Session):
        self.repository = AudienceRepository(db)

    def execute(self, audience_id: UUID) -> bool:
        return self.repository.delete(audience_id)


class AddCommunityToAudienceUseCase:
    """Adiciona uma comunidade a uma audiência."""

    def __init__(self, db: Session):
        self.repository = AudienceRepository(db)

    def execute(self, audience_id: UUID, subreddit_name: str) -> bool:
        result = self.repository.add_community(audience_id, subreddit_name)
        return result is not None


class RemoveCommunityFromAudienceUseCase:
    """Remove uma comunidade de uma audiência."""

    def __init__(self, db: Session):
        self.repository = AudienceRepository(db)

    def execute(self, audience_id: UUID, subreddit_name: str) -> bool:
        return self.repository.remove_community(audience_id, subreddit_name)
