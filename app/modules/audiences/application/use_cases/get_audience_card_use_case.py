from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.shared.application.services.community_stats_service import (
    CommunityStatsService,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


@dataclass
class CommunityCardData:
    """Dados de uma comunidade para o card."""

    subreddit_name: str
    icon_url: str | None = None
    subscribers: int | None = None


@dataclass
class AudienceCardData:
    """Dados agregados do card de audiência."""

    audience_id: UUID
    name: str
    description: str | None
    total_subs: int  # Quantidade de comunidades
    total_members: int  # Soma de subscribers
    growth_week: float | None  # Média de crescimento semanal
    growth_month: float | None  # Média de crescimento mensal
    communities: list[CommunityCardData]  # Ícones das comunidades


class GetAudienceCardUseCase:
    """
    Retorna dados agregados para o card de uma audiência.

    Fontes de dados:
    - Nome da audiência → audiences.name
    - Qtd de subs → COUNT(audience_communities)
    - Total de membros → SUM(subscribers) via Reddit API + cache
    - Crescimento %/wk → AVG(subscriberRatios.week) via SubredditStats
    - Ícones das comunidades → community_icon via Reddit API
    """

    def __init__(
        self,
        db: Session,
        reddit_provider: GenericRedditProvider | None = None,
    ):
        self.repository = AudienceRepository(db)
        self.stats_service = CommunityStatsService(db)
        self.reddit_provider = reddit_provider or GenericRedditProvider()

    def execute(self, audience_id: UUID) -> AudienceCardData | None:
        """
        Busca dados agregados de uma audiência para o card.

        Args:
            audience_id: ID da audiência

        Returns:
            AudienceCardData ou None se não encontrada
        """
        # 1. Buscar audiência
        audience = self.repository.find_by_id(audience_id)
        if not audience:
            return None

        # 2. Buscar comunidades da audiência
        audience_communities = self.repository.get_communities(audience_id)

        if not audience_communities:
            return AudienceCardData(
                audience_id=audience.id,
                name=audience.name,
                description=audience.description,
                total_subs=0,
                total_members=0,
                growth_week=None,
                growth_month=None,
                communities=[],
            )

        # 3. Para cada comunidade, buscar stats (com cache)
        communities_data: list[CommunityCardData] = []
        total_members = 0
        growth_week_values: list[float] = []
        growth_month_values: list[float] = []

        for ac in audience_communities:
            # Buscar dados do Reddit se não tiver no cache
            reddit_data = None
            try:
                reddit_response = self.reddit_provider.get_community_details(
                    ac.subreddit_name
                )
                reddit_data = reddit_response.get("data", reddit_response)
            except Exception:
                pass

            # Buscar/atualizar stats (usa cache do banco)
            stats = self.stats_service.get_stats(
                subreddit_name=ac.subreddit_name,
                reddit_data=reddit_data,
            )

            icon_url = None
            subscribers = 0

            if stats:
                icon_url = stats.icon_url
                subscribers = stats.subscribers or 0
                if stats.growth_week is not None:
                    growth_week_values.append(stats.growth_week)
                if stats.growth_month is not None:
                    growth_month_values.append(stats.growth_month)
            elif reddit_data:
                icon_url = reddit_data.get("community_icon") or reddit_data.get(
                    "icon_img"
                )
                if icon_url:
                    icon_url = icon_url.replace("&amp;", "&")
                subscribers = reddit_data.get("subscribers", 0)

            total_members += subscribers

            communities_data.append(
                CommunityCardData(
                    subreddit_name=ac.subreddit_name,
                    icon_url=icon_url,
                    subscribers=subscribers,
                )
            )

        # 4. Calcular médias de crescimento
        avg_growth_week = None
        avg_growth_month = None

        if growth_week_values:
            avg_growth_week = sum(growth_week_values) / len(growth_week_values)

        if growth_month_values:
            avg_growth_month = sum(growth_month_values) / len(growth_month_values)

        return AudienceCardData(
            audience_id=audience.id,
            name=audience.name,
            description=audience.description,
            total_subs=len(audience_communities),
            total_members=total_members,
            growth_week=round(avg_growth_week, 2) if avg_growth_week else None,
            growth_month=round(avg_growth_month, 2) if avg_growth_month else None,
            communities=communities_data,
        )


class ListAudienceCardsUseCase:
    """
    Lista todas as audiências com dados de card.
    """

    def __init__(
        self,
        db: Session,
        reddit_provider: GenericRedditProvider | None = None,
    ):
        self.db = db
        self.repository = AudienceRepository(db)
        self.reddit_provider = reddit_provider or GenericRedditProvider()

    def execute(self, user_id: UUID | None = None) -> list[AudienceCardData]:
        """
        Lista todas as audiências com dados agregados.

        Args:
            user_id: Filtrar por usuário (opcional)

        Returns:
            Lista de AudienceCardData
        """
        audiences = self.repository.find_all(user_id)
        get_card_use_case = GetAudienceCardUseCase(self.db, self.reddit_provider)

        cards = []
        for audience in audiences:
            card = get_card_use_case.execute(audience.id)
            if card:
                cards.append(card)

        return cards
