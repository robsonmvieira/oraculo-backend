"""Repositório para operações com dados estruturados do painel de temas."""

import hashlib
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.theme_analysis.domain.entities.theme_panel import ThemePanel


class ThemePanelRepository:
    """Repositório para operações com painéis de dados estruturados."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(
        theme_id: UUID,
        summary_id: UUID | None = None,
    ) -> str:
        """Gera fingerprint SHA256 baseado no theme_id e opcionalmente no summary_id."""
        raw = str(theme_id)
        if summary_id:
            raw += f"|{summary_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def find_by_theme_id(self, theme_id: UUID) -> ThemePanel | None:
        """Busca o painel mais recente para um tema."""
        return (
            self.db.query(ThemePanel)
            .filter(ThemePanel.theme_id == theme_id)
            .order_by(ThemePanel.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, theme_id: UUID, fingerprint: str
    ) -> ThemePanel | None:
        """Busca painel por fingerprint (mesmo tema + mesma fonte de dados)."""
        return (
            self.db.query(ThemePanel)
            .filter(
                ThemePanel.theme_id == theme_id,
                ThemePanel.fingerprint == fingerprint,
            )
            .order_by(ThemePanel.created_at.desc())
            .first()
        )

    def create_panel(
        self,
        theme_id: UUID,
        analysis_id: UUID,
        fingerprint: str,
        subcategories: list[dict] | None = None,
        related_topics: list[dict] | None = None,
        subreddit_distribution: list[dict] | None = None,
        action_links: dict | None = None,
    ) -> ThemePanel:
        """Cria novo painel de dados estruturados para um tema."""
        panel = ThemePanel(
            theme_id=theme_id,
            analysis_id=analysis_id,
            fingerprint=fingerprint,
            subcategories=subcategories,
            related_topics=related_topics,
            subreddit_distribution=subreddit_distribution,
            action_links=action_links,
        )
        self.db.add(panel)
        self.db.commit()
        self.db.refresh(panel)
        return panel

    def delete_old_panels(self, theme_id: UUID, keep_latest: int = 2) -> int:
        """Remove painéis antigos de um tema, mantendo os N mais recentes."""
        latest_ids = (
            self.db.query(ThemePanel.id)
            .filter(ThemePanel.theme_id == theme_id)
            .order_by(ThemePanel.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(ThemePanel)
            .filter(
                ThemePanel.theme_id == theme_id,
                ThemePanel.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
