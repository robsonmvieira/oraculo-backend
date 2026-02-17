import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.proposta import Proposta


class ItemProposta(BaseModel):
    __tablename__ = "itens_proposta"

    proposta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("propostas.id"), nullable=False
    )
    descricao: Mapped[str] = mapped_column(String, nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    proposta: Mapped["Proposta"] = relationship("Proposta", back_populates="itens")
