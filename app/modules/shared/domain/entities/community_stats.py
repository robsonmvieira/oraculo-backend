import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class CommunityStats(Base):
    """
    Cache de estatísticas de comunidades do Reddit.
    Armazena dados de crescimento para evitar requests repetidos.
    """

    __tablename__ = "community_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subreddit_name = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    subscribers = Column(Integer, nullable=True)
    icon_url = Column(String(1000), nullable=True)
    growth_week = Column(Float, nullable=True)  # Ex: 0.85 = 0.85%
    growth_month = Column(Float, nullable=True)
    category = Column(String(50), nullable=True, index=True)
    size_tag = Column(String(20), nullable=True)
    activity_tag = Column(String(20), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def is_cache_valid(self, max_age_hours: int = 24) -> bool:
        """
        Verifica se o cache ainda é válido.

        Args:
            max_age_hours: Idade máxima do cache em horas

        Returns:
            True se o cache ainda é válido
        """
        if not self.updated_at:
            return False
        age = datetime.now(timezone.utc) - self.updated_at
        return age.total_seconds() < (max_age_hours * 3600)
