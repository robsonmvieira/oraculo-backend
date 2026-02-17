from app.models.lead import Lead
from app.modules.shared.infra.database.database import SessionLocal


class LeadRepository:
    """
    Repositório para leads
    """

    def __init__(self, db: SessionLocal):
        """
        Inicializa o repositório
        """
        self.db = db

    def list_leads(self):
        """
        Lista todos os leads
        """
        return self.db.query(Lead).all()
