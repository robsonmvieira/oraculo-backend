"""Repositório para operações com sumários narrativos de temas."""

import hashlib
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.theme_analysis.domain.entities.theme_summary import ThemeSummary


class ThemeSummaryRepository:
    """Repositório para operações com sumários narrativos enriquecidos."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(
        theme_id: UUID,
        intent_analysis_id: UUID | None = None,
    ) -> str:
        """Gera fingerprint SHA256 baseado no theme_id e opcionalmente no intent_analysis_id."""
        raw = str(theme_id)
        if intent_analysis_id:
            raw += f"|{intent_analysis_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def find_by_theme_id(self, theme_id: UUID) -> ThemeSummary | None:
        """Busca o sumário mais recente para um tema."""
        return (
            self.db.query(ThemeSummary)
            .filter(ThemeSummary.theme_id == theme_id)
            .order_by(ThemeSummary.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, theme_id: UUID, fingerprint: str
    ) -> ThemeSummary | None:
        """Busca sumário por fingerprint (mesmo tema + mesma fonte de intents)."""
        return (
            self.db.query(ThemeSummary)
            .filter(
                ThemeSummary.theme_id == theme_id,
                ThemeSummary.fingerprint == fingerprint,
            )
            .order_by(ThemeSummary.created_at.desc())
            .first()
        )

    def create_summary(
        self,
        theme_id: UUID,
        analysis_id: UUID,
        fingerprint: str,
        narrative: str,
        highlights: list[dict] | None = None,
        emotional_tone: str | None = None,
        tone_description: str | None = None,
        key_themes: list[dict] | None = None,
        intent_breakdown: dict | None = None,
        week_differentiator: str | None = None,
    ) -> ThemeSummary:
        """Cria novo sumário narrativo para um tema."""
        summary = ThemeSummary(
            theme_id=theme_id,
            analysis_id=analysis_id,
            fingerprint=fingerprint,
            narrative=narrative,
            highlights=highlights,
            emotional_tone=emotional_tone,
            tone_description=tone_description,
            key_themes=key_themes,
            intent_breakdown=intent_breakdown,
            week_differentiator=week_differentiator,
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary

    def delete_old_summaries(self, theme_id: UUID, keep_latest: int = 2) -> int:
        """Remove sumários antigos de um tema, mantendo os N mais recentes."""
        latest_ids = (
            self.db.query(ThemeSummary.id)
            .filter(ThemeSummary.theme_id == theme_id)
            .order_by(ThemeSummary.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(ThemeSummary)
            .filter(
                ThemeSummary.theme_id == theme_id,
                ThemeSummary.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
