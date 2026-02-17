import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.item_proposta import ItemProposta


class Proposta(BaseModel):
    __tablename__ = "propostas"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False
    )
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    moeda: Mapped[str] = mapped_column(String, nullable=False, default="BRL")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    desconto_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    corpo_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="propostas")
    itens: Mapped[list["ItemProposta"]] = relationship(
        "ItemProposta", back_populates="proposta"
    )
