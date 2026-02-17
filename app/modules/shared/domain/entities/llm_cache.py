import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, JSON, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class LLMCache(Base):
    __tablename__ = "llm_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_hash = Column(String(64), nullable=False, index=True)
    task_type = Column(String(50), nullable=False, index=True)
    input_text = Column(Text, nullable=False)
    result_json = Column(JSON, nullable=False)
    ttl_hours = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
