import os
import re
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.modules.audience_templates.domain.entities.audience_template import (
    AudienceTemplate,
)
from app.modules.audience_templates.infra.repositories.audience_template_repository import (
    AudienceTemplateRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


@dataclass
class GeneratedSubreddit:
    """Subreddit encontrado e validado."""

    name: str
    title: str
    subscribers: int
    relevance_score: float  # 0-1


@dataclass
class GenerateAudienceTemplateResult:
    """Resultado da geração de template."""

    template: AudienceTemplate
    subreddits_found: list[GeneratedSubreddit]
    subreddits_added: int


class GenerateAudienceTemplateUseCase:
    """
    Gera um template de audiência usando LLM + Reddit search.

    Fluxo:
    1. LLM gera keywords de busca baseado no nome da audiência
    2. Para cada keyword, busca subreddits no Reddit
    3. LLM filtra e valida os subreddits encontrados
    4. Salva os melhores subreddits no template
    """

    def __init__(
        self,
        db: Session,
        reddit_provider: GenericRedditProvider | None = None,
    ):
        self.db = db
        self.repository = AudienceTemplateRepository(db)
        self.reddit_provider = reddit_provider or GenericRedditProvider()
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
            temperature=0,
        )

    def execute(
        self,
        audience_name: str,
        description: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        max_subreddits: int = 15,
    ) -> GenerateAudienceTemplateResult:
        """
        Gera um template de audiência com subreddits relevantes.

        Args:
            audience_name: Nome da audiência (ex: "Startup Founders")
            description: Descrição opcional
            icon: Ícone opcional (emoji)
            category: Categoria opcional
            max_subreddits: Máximo de subreddits a adicionar

        Returns:
            GenerateAudienceTemplateResult com template e subreddits
        """
        # 1. Criar ou buscar template existente
        slug = self._generate_slug(audience_name)
        template = self.repository.find_by_slug(slug)

        if not template:
            template = self.repository.create(
                name=audience_name,
                slug=slug,
                description=description,
                icon=icon,
                category=category,
            )
        else:
            # Limpar comunidades existentes para regenerar
            self.repository.clear_communities(template.id)

        # 2. LLM gera keywords de busca
        keywords = self._generate_search_keywords(audience_name, description)

        # 3. Buscar subreddits para cada keyword
        all_subreddits = self._search_subreddits(keywords)

        # 4. LLM filtra e valida os subreddits
        validated_subreddits = self._validate_subreddits(
            audience_name, all_subreddits, max_subreddits
        )

        # 5. Adicionar subreddits ao template
        subreddit_names = [s.name for s in validated_subreddits]
        self.repository.add_communities(template.id, subreddit_names)

        return GenerateAudienceTemplateResult(
            template=template,
            subreddits_found=validated_subreddits,
            subreddits_added=len(subreddit_names),
        )

    def _generate_slug(self, name: str) -> str:
        """Gera slug a partir do nome."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        return slug

    def _generate_search_keywords(
        self, audience_name: str, description: str | None
    ) -> list[str]:
        """Usa LLM para gerar keywords de busca."""
        desc_text = f"\nDescrição: {description}" if description else ""

        prompt = f"""Você é um especialista em comunidades do Reddit.

Para a audiência "{audience_name}"{desc_text}

Gere 5-8 termos de busca em inglês que encontrariam subreddits relevantes para essa audiência.
Os termos devem ser específicos e variados para cobrir diferentes aspectos da audiência.

Responda APENAS com os termos separados por vírgula, sem explicações.
Exemplo: startups, entrepreneur, saas founders, bootstrapped, indie hackers"""

        response = self.llm.invoke(prompt)
        keywords = [k.strip() for k in response.content.split(",")]
        return keywords[:8]

    def _search_subreddits(self, keywords: list[str]) -> list[dict]:
        """Busca subreddits no Reddit para cada keyword."""
        all_subreddits = {}

        for keyword in keywords:
            try:
                result = self.reddit_provider.search_community_by_name(
                    keyword, limit=20
                )
                children = result.get("data", {}).get("children", [])

                for child in children:
                    data = child.get("data", {})
                    name = data.get("display_name", "").lower()

                    # Evitar duplicatas, manter o com mais subscribers
                    if name not in all_subreddits:
                        all_subreddits[name] = {
                            "name": name,
                            "title": data.get("title", ""),
                            "description": data.get("public_description", ""),
                            "subscribers": data.get("subscribers", 0),
                            "over18": data.get("over18", False),
                        }
            except Exception:
                continue

        # Ordenar por subscribers (tratar None como 0)
        sorted_subs = sorted(
            all_subreddits.values(),
            key=lambda x: x.get("subscribers") or 0,
            reverse=True,
        )

        return sorted_subs[:50]  # Top 50 para validação

    def _validate_subreddits(
        self, audience_name: str, subreddits: list[dict], max_count: int
    ) -> list[GeneratedSubreddit]:
        """Usa LLM para filtrar e validar subreddits."""
        if not subreddits:
            return []

        # Filtrar NSFW
        subreddits = [s for s in subreddits if not s.get("over18", False)]

        # Preparar lista para LLM
        subs_text = "\n".join(
            [
                f"- r/{s['name']}: {s['title']} ({s['subscribers']} members)"
                for s in subreddits[:30]
            ]
        )

        prompt = f"""Você é um especialista em comunidades do Reddit.

Audiência alvo: "{audience_name}"

Subreddits encontrados:
{subs_text}

Selecione os {max_count} subreddits MAIS RELEVANTES para essa audiência.
Considere:
- Relevância direta para o público alvo
- Tamanho da comunidade (prefira comunidades ativas)
- Evite comunidades muito genéricas ou off-topic

Responda APENAS com os nomes dos subreddits (sem r/), um por linha.
Exemplo:
startups
entrepreneur
SaaS"""

        response = self.llm.invoke(prompt)

        # Parsear resposta
        selected_names = set()
        for line in response.content.strip().split("\n"):
            name = line.strip().lower().replace("r/", "").replace("-", "")
            if name:
                selected_names.add(name)

        # Construir resultado com dados originais
        validated = []
        for sub in subreddits:
            if sub["name"].lower() in selected_names:
                validated.append(
                    GeneratedSubreddit(
                        name=sub["name"],
                        title=sub["title"],
                        subscribers=sub["subscribers"],
                        relevance_score=1.0,
                    )
                )

        return validated[:max_count]
