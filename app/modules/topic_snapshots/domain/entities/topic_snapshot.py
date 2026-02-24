import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.modules.shared.infra.database.orm.metadata import Base


class TopicSnapshot(Base):
    """
    Snapshot oportunistico de um topico em um momento especifico.
    Capturado antes de cada nova analise de topicos para permitir
    calculo de crescimento real entre execucoes.
    """

    __tablename__ = "topic_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audience_topic_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_name = Column(String(200), nullable=False)
    topic_name_normalized = Column(String(200), nullable=False, index=True)
    mention_frequency = Column(Float, nullable=True)
    mention_period = Column(String(10), nullable=True)  # day, week, month
    post_count = Column(Integer, nullable=True)
    growth_percentage = Column(Float, nullable=True)
    communities = Column(JSON, nullable=True)
    snapshot_date = Column(Date, nullable=False, default=lambda: date.today(), index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index(
            "ix_topic_snapshots_audience_name_date",
            "audience_id",
            "topic_name_normalized",
            "snapshot_date",
        ),
        Index(
            "ix_topic_snapshots_audience_date",
            "audience_id",
            "snapshot_date",
        ),
    )
