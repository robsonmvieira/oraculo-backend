"""Validação assíncrona de existência de subreddits no Reddit."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.notifications.application.services.notification_event_service import (
    NotificationEventService,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

logger = logging.getLogger(__name__)


class ValidateCommunitiesUseCase:
    """Valida existência de subreddits no Reddit em background."""

    def __init__(self, db: Session):
        self.audience_repo = AudienceRepository(db)
        self.reddit_provider = GenericRedditProvider()
        self.notification_service = NotificationEventService(db)

    def execute(
        self, audience_id: UUID, user_id: UUID, subreddit_names: list[str]
    ) -> None:
        """Valida cada subreddit no Reddit. Remove inválidos e notifica o usuário."""
        invalid_names = []

        for name in subreddit_names:
            try:
                self.reddit_provider.get_community_details(name)
            except Exception:
                logger.warning(
                    "Subreddit '%s' not found on Reddit for audience %s",
                    name,
                    audience_id,
                )
                invalid_names.append(name)

        if not invalid_names:
            return

        self.audience_repo.remove_communities_by_names(audience_id, invalid_names)

        self.notification_service.notify(
            user_id=user_id,
            type_="communities_validation_failed",
            title="Invalid Communities Removed",
            message=(
                f"The following communities were not found on Reddit and have been "
                f"removed: {', '.join(invalid_names)}"
            ),
            metadata={
                "audience_id": str(audience_id),
                "invalid_names": invalid_names,
            },
        )
