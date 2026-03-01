"""Repositório para sugestões de conteúdo."""

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.content_suggestions.domain.entities.content_suggestion import (
    ContentSuggestion,
    ContentSuggestionAnalysis,
)

logger = logging.getLogger(__name__)


class ContentSuggestionRepository:
    """CRUD e queries para sugestões de conteúdo."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(analysis_ids: dict[str, str | None]) -> str:
        """Gera fingerprint SHA256 a partir dos IDs das análises dos módulos."""
        parts = []
        for module in sorted(analysis_ids.keys()):
            aid = analysis_ids[module]
            if aid:
                parts.append(f"{module}:{aid}")
        fingerprint_input = "|".join(parts)
        return hashlib.sha256(fingerprint_input.encode()).hexdigest()

    def create_analysis(
        self,
        audience_id: UUID,
        user_id: UUID,
        fingerprint: str,
    ) -> ContentSuggestionAnalysis:
        """Cria registro de análise com status processing."""
        analysis = ContentSuggestionAnalysis(
            audience_id=audience_id,
            user_id=user_id,
            status="processing",
            fingerprint=fingerprint,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> ContentSuggestionAnalysis | None:
        """Busca análise pelo fingerprint."""
        return (
            self.db.query(ContentSuggestionAnalysis)
            .filter(
                ContentSuggestionAnalysis.audience_id == audience_id,
                ContentSuggestionAnalysis.fingerprint == fingerprint,
            )
            .first()
        )

    def find_latest_by_audience(
        self, audience_id: UUID
    ) -> ContentSuggestionAnalysis | None:
        """Busca a análise mais recente de uma audiência."""
        return (
            self.db.query(ContentSuggestionAnalysis)
            .filter(ContentSuggestionAnalysis.audience_id == audience_id)
            .order_by(ContentSuggestionAnalysis.created_at.desc())
            .first()
        )

    def mark_ready(
        self,
        analysis_id: UUID,
        modules_used: list[str],
        model_used: str,
    ) -> None:
        """Marca análise como pronta."""
        self.db.query(ContentSuggestionAnalysis).filter(
            ContentSuggestionAnalysis.id == analysis_id
        ).update(
            {
                "status": "ready",
                "modules_used": modules_used,
                "model_used": model_used,
                "completed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.db.commit()

    def mark_failed(self, analysis_id: UUID, error_message: str) -> None:
        """Marca análise como falha."""
        self.db.query(ContentSuggestionAnalysis).filter(
            ContentSuggestionAnalysis.id == analysis_id
        ).update(
            {
                "status": "failed",
                "error_message": error_message,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.db.commit()

    def save_suggestions(
        self, analysis_id: UUID, suggestions: list[dict]
    ) -> list[ContentSuggestion]:
        """Salva lista de sugestões no banco."""
        entities = []
        for s in suggestions:
            entity = ContentSuggestion(
                analysis_id=analysis_id,
                rank=s.get("rank", 0),
                priority=s.get("priority", "medium"),
                title=s.get("title", ""),
                approach=s.get("approach", ""),
                why_now=s.get("why_now", ""),
                evidence=s.get("evidence"),
                format=s.get("format", "thread"),
                format_rationale=s.get("format_rationale"),
                emotional_tone=s.get("emotional_tone", "educativo"),
                tone_rationale=s.get("tone_rationale"),
                outline=s.get("outline"),
                keywords=s.get("keywords"),
                research_notes=s.get("research_notes"),
                image_prompt=s.get("image_prompt"),
                differentiation_notes=s.get("differentiation_notes"),
                accuracy_notes=s.get("accuracy_notes"),
                source_topics=s.get("source_topics"),
                source_modules=s.get("source_modules"),
            )
            self.db.add(entity)
            entities.append(entity)
        self.db.commit()
        return entities

    def get_suggestions(
        self,
        analysis_id: UUID,
        priority: str | None = None,
        format_: str | None = None,
        feedback_status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ContentSuggestion]:
        """Lista sugestões com filtros opcionais."""
        query = (
            self.db.query(ContentSuggestion)
            .filter(ContentSuggestion.analysis_id == analysis_id)
        )
        if priority:
            query = query.filter(ContentSuggestion.priority == priority)
        if format_:
            query = query.filter(ContentSuggestion.format == format_)
        if feedback_status == "null":
            query = query.filter(ContentSuggestion.feedback_status.is_(None))
        elif feedback_status:
            query = query.filter(ContentSuggestion.feedback_status == feedback_status)

        return (
            query.order_by(ContentSuggestion.rank)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_suggestions(
        self,
        analysis_id: UUID,
        priority: str | None = None,
        format_: str | None = None,
        feedback_status: str | None = None,
    ) -> int:
        """Conta sugestões com filtros opcionais."""
        query = (
            self.db.query(ContentSuggestion)
            .filter(ContentSuggestion.analysis_id == analysis_id)
        )
        if priority:
            query = query.filter(ContentSuggestion.priority == priority)
        if format_:
            query = query.filter(ContentSuggestion.format == format_)
        if feedback_status == "null":
            query = query.filter(ContentSuggestion.feedback_status.is_(None))
        elif feedback_status:
            query = query.filter(ContentSuggestion.feedback_status == feedback_status)
        return query.count()

    def get_suggestion_by_id(self, suggestion_id: UUID) -> ContentSuggestion | None:
        """Busca sugestão por ID."""
        return (
            self.db.query(ContentSuggestion)
            .filter(ContentSuggestion.id == suggestion_id)
            .first()
        )

    def update_feedback(
        self, suggestion_id: UUID, feedback_status: str
    ) -> ContentSuggestion | None:
        """Atualiza feedback de uma sugestão."""
        suggestion = self.get_suggestion_by_id(suggestion_id)
        if not suggestion:
            return None
        suggestion.feedback_status = feedback_status
        suggestion.feedback_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def delete_old_analyses(
        self, audience_id: UUID, keep_latest: int = 3
    ) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(ContentSuggestionAnalysis.id)
            .filter(ContentSuggestionAnalysis.audience_id == audience_id)
            .order_by(ContentSuggestionAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(ContentSuggestionAnalysis)
            .filter(
                ContentSuggestionAnalysis.audience_id == audience_id,
                ContentSuggestionAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
