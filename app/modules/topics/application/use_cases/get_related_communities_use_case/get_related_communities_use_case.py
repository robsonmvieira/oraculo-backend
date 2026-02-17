from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.shared.domain.entities.related_sub import RelatedSub
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


# TTL de 7 dias para relacionamentos (conforme doc)
RELATED_SUBS_TTL_DAYS = 7


class GetRelatedCommunitiesUseCase:
    """
    Busca comunidades relacionadas a uma comunidade de origem.

    Fluxo:
    1. Verifica se já existem relacionamentos no banco (PostgreSQL)
    2. Se não existem ou expiraram:
       a. Busca detalhes da comunidade (via API .json ou cache Redis)
       b. Gera termos derivados via LLM (usa LLM cache)
       c. Busca comunidades via old.reddit.com (scraping)
       d. Salva relacionamentos no banco
    """

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        scraper: OldRedditScraper,
        cache: RedisCache,
        db: Session,
    ):
        self.reddit_provider = reddit_provider
        self.scraper = scraper
        self.cache = cache
        self.db = db
        self.related_subs_repo = RelatedSubsRepository(db)
        self.llm_cache = LLMCacheService(db)

    def execute(self, community_name: str, limit: int = 10) -> dict:
        """
        Executa a busca de comunidades relacionadas

        Args:
            community_name: Nome da comunidade de origem
            limit: Número máximo de comunidades relacionadas

        Returns:
            Dict com source_community e related_communities
        """
        source_name = community_name.lower()

        # 1. Verificar cache no banco (related_subs)
        cached_relations = self.related_subs_repo.find_by_source(source_name)
        if cached_relations:
            return self._format_response(source_name, cached_relations[:limit])

        # 2. Buscar detalhes da comunidade de origem
        community_data = self._get_community_data(community_name)

        # 3. Gerar termos derivados via LLM (com cache)
        title = community_data.get("title", "")
        description = community_data.get("public_description", "")
        input_text = f"{title}|{description}"

        related_terms_result = self.llm_cache.get_or_compute(
            input_text=input_text,
            task_type=TaskType.RELATED_TERMS,
            compute_fn=lambda: self._compute_related_terms(title, description),
        )
        terms = related_terms_result.get("terms", [])

        # 4. Buscar comunidades via old.reddit.com (scraping)
        # Usar apenas 3 termos mais relevantes para economizar requests
        search_terms = terms[:3]
        scraped_subs = self.scraper.search_multiple_terms(
            search_terms, limit_per_term=5
        )

        # 5. Filtrar: remover a própria comunidade de origem
        scraped_subs = [
            sub for sub in scraped_subs if sub.name.lower() != source_name
        ]

        # 6. Salvar relacionamentos no banco
        expires_at = datetime.now(timezone.utc) + timedelta(days=RELATED_SUBS_TTL_DAYS)
        related_subs = []

        for sub in scraped_subs[:limit]:
            related_sub = RelatedSub(
                source_sub=source_name,
                related_sub=sub.name.lower(),
                related_sub_title=sub.title,
                related_sub_description=sub.description,
                related_sub_subscribers=sub.subscribers,
                discovered_via=",".join(search_terms),
                expires_at=expires_at,
            )
            saved = self.related_subs_repo.upsert(related_sub)
            related_subs.append(saved)

        return self._format_response(source_name, related_subs)

    def _get_community_data(self, community_name: str) -> dict:
        """
        Busca dados da comunidade (Redis cache ou API)
        """
        cache_key = f"community_details_{community_name}"
        cached_data = self.cache.get(cache_key)

        if cached_data:
            return cached_data

        response = self.reddit_provider.get_community_details(community_name)
        community_data = response.get("data", response)
        self.cache.set(cache_key, community_data)
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

    def _format_response(
        self, source_name: str, related_subs: list[RelatedSub]
    ) -> dict:
        """
        Formata a resposta final
        """
        return {
            "source_community": source_name,
            "related_communities": [
                {
                    "name": sub.related_sub,
                    "title": sub.related_sub_title,
                    "description": sub.related_sub_description,
                    "subscribers": sub.related_sub_subscribers,
                    "discovered_via": sub.discovered_via,
                }
                for sub in related_subs
            ],
            "total": len(related_subs),
        }
