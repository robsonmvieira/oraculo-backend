import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class AudienceTemplate(Base):
    """
    Template de audiência pré-definida.
    Usado para sugerir audiências aos novos usuários.
    """

    __tablename__ = "audience_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)  # emoji ou icon name
    category = Column(String(100), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    display_order = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relacionamento com comunidades
    communities = relationship(
        "AudienceTemplateCommunity",
        back_populates="template",
        cascade="all, delete-orphan",
    )


class AudienceTemplateCommunity(Base):
    """
    Comunidade dentro de um template de audiência.
    """

    __tablename__ = "audience_template_communities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audience_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subreddit_name = Column(String(100), nullable=False)
    added_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamento com template
    template = relationship("AudienceTemplate", back_populates="communities")
