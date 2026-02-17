import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.lead import Lead


class NotaLead(BaseModel):
    __tablename__ = "notas_lead"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="notas")
