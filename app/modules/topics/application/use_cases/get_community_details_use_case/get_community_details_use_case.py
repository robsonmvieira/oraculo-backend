import threading

from sqlalchemy.orm import Session

from app.modules.shared.application.services.community_stats_service import (
    CommunityStatsService,
)
from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.shared.infra.repositories.related_subs_repository import (
    RelatedSubsRepository,
)
from app.modules.topics.application.use_cases.get_community_details_use_case.agent.communit_detail_analiser_agent import (
    create_community_analyzer_agent,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)
from app.modules.topics.infra.providers.reddit_provider.old_reddit_scraper import (
    OldRedditScraper,
)


class GetCommunityDetailsUseCase:
    """
    Get details of a community by name, including related communities.
    """

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        cache: RedisCache,
        db: Session,
        scraper: OldRedditScraper | None = None,
    ):
        """
        Inicializa o use case.

        Args:
            reddit_provider: Provider para buscar dados do Reddit
            cache: Serviço de cache Redis
            db: Sessão do banco de dados
            scraper: Scraper para old.reddit.com (opcional)
        """
        self.reddit_provider = reddit_provider
        self.cache = cache
        self.db = db
        self.llm_cache = LLMCacheService(db)
        self.related_subs_repo = RelatedSubsRepository(db)
        self.stats_service = CommunityStatsService(db)
        self.scraper = scraper or OldRedditScraper()

    def execute(self, community_name: str) -> dict:
        """
        Executa o use case.

        Args:
            community_name: Nome da comunidade

        Returns:
            Detalhes da comunidade com related_communities
        """
        # 1. Buscar dados da comunidade no Reddit (via Redis cache)
        cache_key = f"community_details_{community_name}"
        cached_data = self.cache.get(cache_key)

        if cached_data:
            community_data = cached_data
        else:
            response = self.reddit_provider.get_community_details(community_name)
            community_data = response.get("data", response)
            self.cache.set(cache_key, community_data)

        # 2. Buscar termos relacionados no LLM cache (PostgreSQL)
        title = community_data.get("title", "")
        description = community_data.get("public_description", "")
        input_text = f"{title}|{description}"

        related_terms = self.llm_cache.get_or_compute(
            input_text=input_text,
            task_type=TaskType.RELATED_TERMS,
            compute_fn=lambda: self._compute_related_terms(title, description),
        )

        community_data["related_terms"] = related_terms.get("terms", [])

        # 3. Buscar comunidades relacionadas do cache (related_subs table)
        related_communities = self._get_related_communities(community_name)

        if related_communities:
            community_data["related_communities"] = related_communities
            community_data["related_communities_status"] = "ready"
        else:
            community_data["related_communities"] = []
            community_data["related_communities_status"] = "processing"
            # Disparar busca em background
            self._fetch_related_in_background(community_name)

        # 4. Adicionar dados de growth
        stats = self.stats_service.get_stats(
            subreddit_name=community_name,
            reddit_data=community_data,
        )
        if stats:
            community_data["growth_week"] = stats.growth_week
            community_data["growth_month"] = stats.growth_month

        return community_data

    def _compute_related_terms(self, title: str, description: str) -> dict:
        """
        Chama o LLM para gerar termos relacionados.
        """
        agent = create_community_analyzer_agent()
        result = agent.invoke(
            {
                "title": title,
                "public_description": description,
            }
        )
        return {"terms": result["derived_terms"]}

    def _get_related_communities(self, community_name: str) -> list[dict]:
        """
        Busca comunidades relacionadas do cache (related_subs table).

        Returns:
            Lista de comunidades relacionadas formatadas para o frontend
        """
        related_subs = self.related_subs_repo.find_by_source(community_name)

        if not related_subs:
            return []

        return [
            {
                "name": sub.related_sub,
                "title": sub.related_sub_title,
                "description": sub.related_sub_description,
                "subscribers": sub.related_sub_subscribers,
                "discovered_via": sub.discovered_via,
            }
            for sub in related_subs
        ]

    def _fetch_related_in_background(
        self,
        community_name: str,
    ) -> None:
        """
        Dispara busca de comunidades relacionadas em background.
        Usa threading para não bloquear a resposta da API.
        """
        # Import here to avoid circular imports
        from app.modules.shared.infra.database.database import SessionLocal
        from app.modules.topics.application.use_cases.get_related_communities_use_case.get_related_communities_use_case import (
            GetRelatedCommunitiesUseCase,
        )

        def background_task():
            # Criar nova sessão do banco para a thread
            db = SessionLocal()
            try:
                use_case = GetRelatedCommunitiesUseCase(
                    reddit_provider=self.reddit_provider,
                    scraper=self.scraper,
                    cache=self.cache,
                    db=db,
                )
                use_case.execute(community_name, limit=10)
            except Exception:
                pass  # Silently fail - will retry on next request
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
