import logging
import threading
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_keywords.application.use_cases.trigger_keyword_analysis_use_case import (
    TriggerKeywordAnalysisUseCase,
)
from app.modules.audience_topics.application.use_cases.trigger_topic_analysis_use_case import (
    TriggerTopicAnalysisUseCase,
)
from app.modules.audiences.domain.constants import MAX_COMMUNITIES_PER_AUDIENCE
from app.modules.audiences.domain.validators.subreddit_name_validator import (
    validate_subreddit_names_format,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.notifications.application.services.notification_event_service import (
    NotificationEventService,
)
from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.shared.infra.database.database import SessionLocal

logger = logging.getLogger(__name__)


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
        self.trigger_topics = TriggerTopicAnalysisUseCase(db)
        self.trigger_keywords = TriggerKeywordAnalysisUseCase(db)

    def execute(self, input_data: CreateAudienceInput) -> AudienceDTO:
        if input_data.subreddit_names:
            _validate_names_format(input_data.subreddit_names)
            _validate_communities_limit(input_data.subreddit_names)

        audience = self.repository.create(
            name=input_data.name,
            description=input_data.description,
            user_id=input_data.user_id,
        )

        for subreddit_name in input_data.subreddit_names:
            self.repository.add_community(audience.id, subreddit_name)

        communities_count = len(input_data.subreddit_names)

        # Dispara análises em background se há comunidades
        if input_data.subreddit_names:
            self.trigger_topics.execute(audience.id)
            self.trigger_keywords.execute(audience.id)

            # Validar existência no Reddit em background
            _validate_communities_in_background(
                audience.id,
                audience.user_id,
                input_data.subreddit_names,
            )

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
        self.db = db
        self.repository = AudienceRepository(db)
        self.trigger_topics = TriggerTopicAnalysisUseCase(db)
        self.trigger_keywords = TriggerKeywordAnalysisUseCase(db)
        self.notification_service = NotificationEventService(db)
        self.cache = RedisCache()

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
            communities_count = self._sync_and_notify(
                audience_id, audience.user_id, input_data.subreddit_names
            )
        else:
            communities_count = len(audience.communities)

        return AudienceDTO(
            id=audience.id,
            name=audience.name,
            description=audience.description,
            user_id=audience.user_id,
            communities_count=communities_count,
        )

    def _sync_and_notify(
        self, audience_id: UUID, user_id: UUID, subreddit_names: list[str]
    ) -> int:
        """Valida, sincroniza comunidades e dispara análises/notificações."""
        _validate_names_format(subreddit_names)
        _validate_communities_limit(subreddit_names)

        communities, to_add, to_remove = self.repository.sync_communities(
            audience_id, subreddit_names
        )

        # Só dispara análises e notificações quando realmente mudou
        if to_add or to_remove:
            self.trigger_topics.execute(audience_id)
            self.trigger_keywords.execute(audience_id)

            self.notification_service.notify(
                user_id=user_id,
                type_="communities_changed",
                title="Communities Updated",
                message=(
                    f"Audience communities updated: "
                    f"{len(to_add)} added, {len(to_remove)} removed."
                ),
                metadata={
                    "audience_id": str(audience_id),
                    "added": sorted(to_add),
                    "removed": sorted(to_remove),
                },
            )

            for name in to_remove:
                self.cache.delete(f"community_details_{name}")

            if to_add:
                _validate_communities_in_background(audience_id, user_id, list(to_add))

        return len(communities)


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
        self.trigger_topics = TriggerTopicAnalysisUseCase(db)
        self.trigger_keywords = TriggerKeywordAnalysisUseCase(db)

    def execute(self, audience_id: UUID, subreddit_name: str) -> bool:
        _validate_names_format([subreddit_name])

        current_communities = self.repository.get_communities(audience_id)
        if len(current_communities) >= MAX_COMMUNITIES_PER_AUDIENCE:
            raise ValueError(
                f"Maximum of {MAX_COMMUNITIES_PER_AUDIENCE} communities per audience reached."
            )

        result = self.repository.add_community(audience_id, subreddit_name)
        if result is not None:
            self.trigger_topics.execute(audience_id)
            self.trigger_keywords.execute(audience_id)
        return result is not None


class RemoveCommunityFromAudienceUseCase:
    """Remove uma comunidade de uma audiência."""

    def __init__(self, db: Session):
        self.repository = AudienceRepository(db)
        self.trigger_topics = TriggerTopicAnalysisUseCase(db)
        self.trigger_keywords = TriggerKeywordAnalysisUseCase(db)

    def execute(self, audience_id: UUID, subreddit_name: str) -> bool:
        removed = self.repository.remove_community(audience_id, subreddit_name)
        if removed:
            self.trigger_topics.execute(audience_id)
            self.trigger_keywords.execute(audience_id)
        return removed


def _validate_names_format(subreddit_names: list[str]) -> None:
    """Valida formato dos nomes de subreddit. Levanta ValueError se inválido."""
    _, invalid_names = validate_subreddit_names_format(subreddit_names)
    if invalid_names:
        raise ValueError(
            f"Invalid subreddit name format: {', '.join(invalid_names)}. "
            "Names must be 3-21 characters, alphanumeric and underscores only."
        )


def _validate_communities_limit(subreddit_names: list[str]) -> None:
    """Valida limite de comunidades por audiência. Levanta ValueError se excedido."""
    if len(subreddit_names) > MAX_COMMUNITIES_PER_AUDIENCE:
        raise ValueError(
            f"Maximum of {MAX_COMMUNITIES_PER_AUDIENCE} communities per audience exceeded. "
            f"Received {len(subreddit_names)}."
        )


def _validate_communities_in_background(
    audience_id: UUID, user_id: UUID, subreddit_names: list[str]
) -> None:
    """Dispara validação de existência no Reddit em background thread."""

    def _run():
        from app.modules.audiences.application.use_cases.validate_communities_use_case import (
            ValidateCommunitiesUseCase,
        )

        db = SessionLocal()
        try:
            use_case = ValidateCommunitiesUseCase(db)
            use_case.execute(audience_id, user_id, subreddit_names)
        except Exception:
            logger.exception(
                "Background community validation failed for audience %s",
                audience_id,
            )
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
