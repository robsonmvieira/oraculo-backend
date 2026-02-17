import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.status_lead import StatusLead
    from app.models.nota_lead import NotaLead
    from app.models.tarefa_lead import TarefaLead
    from app.models.proposta import Proposta


class Lead(BaseModel):
    __tablename__ = "leads"

    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String, nullable=True)
    empresa: Mapped[str | None] = mapped_column(String, nullable=True)
    origem: Mapped[str | None] = mapped_column(String, nullable=True)
    qualificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status_codigo: Mapped[str] = mapped_column(
        String, ForeignKey("status_lead.codigo"), nullable=False
    )
    ultimo_contato_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    proxima_acao_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped["StatusLead"] = relationship("StatusLead", back_populates="leads")
    notas: Mapped[list["NotaLead"]] = relationship("NotaLead", back_populates="lead")
    tarefas: Mapped[list["TarefaLead"]] = relationship(
        "TarefaLead", back_populates="lead"
    )
    propostas: Mapped[list["Proposta"]] = relationship("Proposta", back_populates="lead")
