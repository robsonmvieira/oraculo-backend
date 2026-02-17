from app.modules.leads.infra.repositories.lead_repository import LeadRepository


class ListLeadsUseCase:
    """
    Use case para listar leads
    """

    def __init__(self, lead_repository: LeadRepository):
        """
        Inicializa o use case
        """
        self.lead_repository = lead_repository

    def execute(self):
        """Executa o use case"""
        return self.lead_repository.list_leads()
