import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead


class StatusLead(Base):
    __tablename__ = "status_lead"

    codigo: Mapped[str] = mapped_column(String, primary_key=True)
    rotulo: Mapped[str] = mapped_column(String, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="status")
