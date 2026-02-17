from app.models.base import Base, BaseModel
from app.models.status_lead import StatusLead
from app.models.lead import Lead
from app.models.nota_lead import NotaLead
from app.models.tarefa_lead import TarefaLead
from app.models.proposta import Proposta
from app.models.item_proposta import ItemProposta

__all__ = [
    "Base",
    "BaseModel",
    "StatusLead",
    "Lead",
    "NotaLead",
    "TarefaLead",
    "Proposta",
    "ItemProposta",
]
