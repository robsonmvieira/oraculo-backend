"""Repositório para operações com análises temporais de temas."""

import hashlib
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.theme_analysis.domain.entities.theme import (
    Theme,
    ThemeAnalysis,
    ThemePost,
)


class ThemeAnalysisRepository:
    """Repositório para operações com análises de temas temporais."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def get_period_bounds(window: str) -> tuple[date, date]:
        """Calcula início e fim do período para a janela temporal."""
        today = date.today()
        if window == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
        elif window == "month":
            start = today.replace(day=1)
            next_month = start.replace(day=28) + timedelta(days=4)
            end = next_month - timedelta(days=next_month.day)
        else:
            start = today
            end = today
        return start, end

    @staticmethod
    def generate_fingerprint(
        audience_id: UUID,
        community_names: list[str],
        window: str,
    ) -> str:
        """Gera fingerprint SHA256 incluindo período (semana ou mês ISO)."""
        today = date.today()
        if window == "week":
            period_key = f"{today.isocalendar().year}-W{today.isocalendar()[1]:02d}"
        elif window == "month":
            period_key = f"{today.year}-{today.month:02d}"
        else:
            period_key = str(today)

        sorted_names = sorted(n.lower() for n in community_names)
        raw = f"{audience_id}|{'|'.join(sorted_names)}|{window}|{period_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def find_latest_by_audience_and_window(
        self, audience_id: UUID, window: str
    ) -> ThemeAnalysis | None:
        """Busca a análise mais recente para audiência e janela temporal."""
        return (
            self.db.query(ThemeAnalysis)
            .filter(
                ThemeAnalysis.audience_id == audience_id,
                ThemeAnalysis.time_window == window,
            )
            .order_by(ThemeAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> ThemeAnalysis | None:
        """Busca análise por fingerprint (mesmo período e comunidades)."""
        return (
            self.db.query(ThemeAnalysis)
            .filter(
                ThemeAnalysis.audience_id == audience_id,
                ThemeAnalysis.communities_fingerprint == fingerprint,
                ThemeAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(ThemeAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self,
        audience_id: UUID,
        fingerprint: str,
        window: str,
        period_start: date,
        period_end: date,
    ) -> ThemeAnalysis:
        """Cria novo registro de análise com status 'processing'."""
        analysis = ThemeAnalysis(
            audience_id=audience_id,
            communities_fingerprint=fingerprint,
            status="processing",
            time_window=window,
            period_start=period_start,
            period_end=period_end,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(self, analysis_id: UUID, total_themes: int) -> ThemeAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()
        )
        if not analysis:
            return None

        analysis.status = "ready"
        analysis.total_themes = total_themes
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> ThemeAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()
        )
        if not analysis:
            return None

        analysis.status = "failed"
        analysis.error_message = error_message
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def save_themes(self, analysis_id: UUID, themes: list[dict]) -> list[Theme]:
        """Salva lista de temas extraídos."""
        entities = []
        for theme_data in themes:
            theme = Theme(
                analysis_id=analysis_id,
                name=theme_data["name"],
                summary=theme_data.get("summary"),
                post_count=theme_data.get("post_count"),
                avg_score=theme_data.get("avg_score"),
                avg_comments=theme_data.get("avg_comments"),
                engagement_score=theme_data.get("engagement_score"),
                top_subreddits=theme_data.get("top_subreddits"),
                top_keywords=theme_data.get("top_keywords"),
                representative_posts=theme_data.get("representative_posts"),
                rank=theme_data.get("rank"),
            )
            self.db.add(theme)
            entities.append(theme)

        self.db.commit()
        return entities

    def get_themes(
        self,
        analysis_id: UUID,
        sort_by: str = "rank",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Theme]:
        """Lista temas de uma análise com ordenação."""
        query = self.db.query(Theme).filter(Theme.analysis_id == analysis_id)

        if sort_by == "engagement":
            query = query.order_by(Theme.engagement_score.desc().nullslast())
        elif sort_by == "post_count":
            query = query.order_by(Theme.post_count.desc().nullslast())
        elif sort_by == "name":
            query = query.order_by(Theme.name.asc())
        else:
            query = query.order_by(Theme.rank.asc().nullslast())

        return query.offset(offset).limit(limit).all()

    def save_posts(self, analysis_id: UUID, posts: list) -> int:
        """Salva posts coletados do Reddit vinculados à análise."""
        for post_data in posts:
            post = ThemePost(
                analysis_id=analysis_id,
                post_reddit_id=post_data["id"],
                subreddit=post_data["subreddit"],
                title=post_data["title"],
                selftext=post_data.get("selftext"),
                score=post_data.get("score"),
                num_comments=post_data.get("num_comments"),
                created_utc=post_data.get("created_utc"),
                permalink=post_data.get("permalink", ""),
            )
            self.db.add(post)
        self.db.commit()
        return len(posts)

    def get_posts(self, analysis_id: UUID) -> list[ThemePost]:
        """Retorna todos os posts coletados de uma análise."""
        return (
            self.db.query(ThemePost).filter(ThemePost.analysis_id == analysis_id).all()
        )

    def delete_old_analyses(
        self, audience_id: UUID, window: str, keep_latest: int = 2
    ) -> int:
        """Remove análises antigas para a janela, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(ThemeAnalysis.id)
            .filter(
                ThemeAnalysis.audience_id == audience_id,
                ThemeAnalysis.time_window == window,
            )
            .order_by(ThemeAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(ThemeAnalysis)
            .filter(
                ThemeAnalysis.audience_id == audience_id,
                ThemeAnalysis.time_window == window,
                ThemeAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
