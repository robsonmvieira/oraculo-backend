from sqlalchemy.orm import Session

from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.topics.application.use_cases.get_community_details_use_case.agent.communit_detail_analiser_agent import (
    create_community_analyzer_agent,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


class GetCommunityDetailsUseCase:
    """
    Get details of a community by name
    """

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        cache: RedisCache,
        db: Session,
    ):
        """
        Inicializa o use case

        Args:
            reddit_provider: Provider para buscar dados do Reddit
            cache: Serviço de cache Redis
            db: Sessão do banco de dados
        """
        self.reddit_provider = reddit_provider
        self.cache = cache
        self.llm_cache = LLMCacheService(db)

    def execute(self, community_name: str):
        """
        Executa o use case

        Args:
            community_name: Nome da comunidade

        Returns:
            Detalhes da comunidade
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
        return community_data

    def _compute_related_terms(self, title: str, description: str) -> dict:
        """
        Chama o LLM para gerar termos relacionados
        """
        agent = create_community_analyzer_agent()
        result = agent.invoke(
            {
                "title": title,
                "public_description": description,
            }
        )
        return {"terms": result["derived_terms"]}
