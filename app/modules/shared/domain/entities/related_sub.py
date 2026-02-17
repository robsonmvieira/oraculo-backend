import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class RelatedSub(Base):
    __tablename__ = "related_subs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_sub = Column(String(100), nullable=False, index=True)
    related_sub = Column(String(100), nullable=False, index=True)
    related_sub_title = Column(String(500), nullable=True)
    related_sub_description = Column(Text, nullable=True)
    related_sub_subscribers = Column(Integer, nullable=True)
    discovered_via = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
