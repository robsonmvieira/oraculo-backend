"""Repositorio para drafts de conteudo produzido."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.content_suggestions.domain.entities.content_draft import ContentDraft
from app.modules.content_suggestions.domain.entities.content_suggestion import (
    ContentSuggestion,
)

logger = logging.getLogger(__name__)


class ContentDraftRepository:
    """CRUD e queries para drafts de conteudo."""

    def __init__(self, db: Session):
        self.db = db

    def save_drafts(
        self,
        suggestion_id: UUID,
        drafts: list[dict],
        image_url: str | None = None,
    ) -> list[ContentDraft]:
        """Salva drafts gerados e atualiza image_url na sugestao."""
        entities = []
        for d in drafts:
            entity = ContentDraft(
                suggestion_id=suggestion_id,
                platform=d.get("platform", ""),
                status="ready",
                hooks=d.get("hooks"),
                full_draft=d.get("full_draft"),
                narrative_arc=d.get("narrative_arc"),
                cta=d.get("cta"),
                platform_notes=d.get("platform_notes"),
                hashtags=d.get("hashtags"),
                image_url=image_url,
                image_aspect_ratio=d.get("image_aspect_ratio"),
                model_used=d.get("model_used"),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(entity)
            entities.append(entity)

        # Atualizar image_url na sugestao pai
        if image_url:
            self.db.query(ContentSuggestion).filter(
                ContentSuggestion.id == suggestion_id
            ).update({"image_url": image_url})

        self.db.commit()
        return entities

    def get_drafts_by_suggestion(self, suggestion_id: UUID) -> list[ContentDraft]:
        """Lista drafts de uma sugestao."""
        return (
            self.db.query(ContentDraft)
            .filter(ContentDraft.suggestion_id == suggestion_id)
            .order_by(ContentDraft.platform)
            .all()
        )

    def get_draft_by_id(self, draft_id: UUID) -> ContentDraft | None:
        """Busca draft por ID."""
        return (
            self.db.query(ContentDraft)
            .filter(ContentDraft.id == draft_id)
            .first()
        )

    def delete_drafts_by_suggestion(self, suggestion_id: UUID) -> int:
        """Remove drafts de uma sugestao (para re-geracao)."""
        deleted = (
            self.db.query(ContentDraft)
            .filter(ContentDraft.suggestion_id == suggestion_id)
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted

    def mark_drafts_failed(
        self, suggestion_id: UUID, error_message: str
    ) -> None:
        """Marca todos os drafts de uma sugestao como falha."""
        self.db.query(ContentDraft).filter(
            ContentDraft.suggestion_id == suggestion_id
        ).update(
            {"status": "failed", "error_message": error_message}
        )
        self.db.commit()
