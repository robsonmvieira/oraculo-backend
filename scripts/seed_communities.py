"""
Script para popular a base de comunidades por categoria usando LLM.

Gera a base inicial de comunidades para o browse endpoint.
Para cada categoria, o LLM sugere 25-30 subreddits relevantes,
que são então validados via Reddit API e salvos com stats e embeddings.

Uso:
    python -m scripts.seed_communities

    # Apenas uma categoria
    python -m scripts.seed_communities --category tech

    # Modo dry-run
    python -m scripts.seed_communities --dry-run
"""

import argparse
import os
import sys
import time

from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.modules.shared.application.services.community_stats_service import (
    CommunityStatsService,
)
from app.modules.shared.infra.database.database import SessionLocal
from app.modules.similar_communities.application.services.embedding_service import (
    EmbeddingService,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


SEED_CATEGORIES = {
    "tech": "Technology, programming, software development, gadgets, and IT",
    "finance": "Personal finance, investing, cryptocurrency, financial planning",
    "health": "Fitness, mental health, nutrition, medical topics, wellness",
    "gaming": "Video games, board games, esports, game development",
    "marketing": "Digital marketing, SEO, social media marketing, advertising",
    "lifestyle": "Home improvement, fashion, food, travel, relationships",
    "education": "Learning, online courses, academic subjects, career development",
    "business": "Entrepreneurship, startups, freelancing, remote work, management",
    "science": "Research, space, biology, physics, environment",
    "entertainment": "Movies, TV shows, music, books, art, podcasts",
}


def generate_community_names(llm: ChatOpenAI, category: str, description: str) -> list[str]:
    """Usa LLM para gerar lista de subreddits por categoria."""
    prompt = f"""You are an expert on Reddit communities.

For the category "{category}" ({description}):

List 25-30 real, active subreddit names (without the r/ prefix) that belong to this category.
Focus on:
- Communities with at least 10,000 subscribers
- Active communities (regular posts)
- Mix of large and medium-sized communities
- Cover different sub-topics within the category

Respond ONLY with subreddit names, one per line, no explanations.
Example:
programming
webdev
learnpython"""

    response = llm.invoke(prompt)

    names = []
    for line in response.content.strip().split("\n"):
        name = line.strip().lower().replace("r/", "").replace(" ", "")
        if name and not any(c in name for c in [".", ",", ":", "-"]):
            names.append(name)

    return names


def process_category(
    db: Session,
    llm: ChatOpenAI,
    reddit: GenericRedditProvider,
    stats_service: CommunityStatsService,
    embedding_service: EmbeddingService,
    category: str,
    description: str,
    delay: int,
    dry_run: bool,
) -> dict:
    """Processa uma categoria: gera nomes, busca stats, gera embeddings."""
    print(f"\n{'='*60}")
    print(f"Categoria: {category}")
    print(f"Descrição: {description}")
    print(f"{'='*60}")

    # 1. LLM gera nomes
    print("\nGerando lista de comunidades via LLM...")
    names = generate_community_names(llm, category, description)
    print(f"Comunidades sugeridas: {len(names)}")

    if dry_run:
        for name in names:
            print(f"  - r/{name}")
        return {"category": category, "suggested": len(names), "saved": 0, "failed": 0, "status": "dry-run"}

    # 2. Buscar stats e salvar
    saved = 0
    failed = 0
    community_data_for_embeddings = []

    for name in names:
        try:
            print(f"  Processando r/{name}...", end=" ")
            reddit_data = reddit.get_community_details(name)
            data = reddit_data.get("data", {})

            if not data.get("subscribers"):
                print("(sem dados, pulando)")
                failed += 1
                continue

            stats = stats_service.get_stats(
                subreddit_name=name,
                reddit_data=reddit_data,
                category=category,
            )

            if stats:
                print(f"OK ({stats.subscribers:,} members)")
                saved += 1
                community_data_for_embeddings.append({
                    "name": name,
                    "title": data.get("title", name),
                    "description": data.get("public_description", ""),
                    "subscribers": data.get("subscribers", 0),
                })
            else:
                print("(falhou)")
                failed += 1

            time.sleep(delay)

        except Exception as e:
            print(f"ERRO: {e}")
            failed += 1
            continue

    # 3. Gerar embeddings em batch
    if community_data_for_embeddings:
        print(f"\n  Gerando embeddings para {len(community_data_for_embeddings)} comunidades...")
        try:
            results = embedding_service.batch_get_or_create_embeddings(
                community_data_for_embeddings
            )
            print(f"  Embeddings gerados: {len(results)}")
        except Exception as e:
            print(f"  Erro ao gerar embeddings: {e}")

    return {
        "category": category,
        "suggested": len(names),
        "saved": saved,
        "failed": failed,
        "status": "success",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Popula base de comunidades por categoria usando LLM"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Processar apenas uma categoria específica",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem salvar",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=1,
        help="Delay entre requests ao Reddit em segundos (default: 1)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("SEED DE COMUNIDADES POR CATEGORIA")
    print("=" * 60)

    if args.dry_run:
        print("[MODO DRY-RUN ATIVADO]")

    # Filtrar categorias
    categories = SEED_CATEGORIES
    if args.category:
        if args.category not in SEED_CATEGORIES:
            print(f"\n[ERRO] Categoria '{args.category}' não encontrada.")
            print("Categorias disponíveis:")
            for cat in SEED_CATEGORIES:
                print(f"  - {cat}")
            sys.exit(1)
        categories = {args.category: SEED_CATEGORIES[args.category]}

    print(f"Categorias a processar: {len(categories)}")

    # Setup
    db = SessionLocal()
    llm = ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=0,
    )
    reddit = GenericRedditProvider()
    stats_service = CommunityStatsService(db)
    embedding_service = EmbeddingService(db)

    results = []

    try:
        for category, description in categories.items():
            result = process_category(
                db=db,
                llm=llm,
                reddit=reddit,
                stats_service=stats_service,
                embedding_service=embedding_service,
                category=category,
                description=description,
                delay=args.delay,
                dry_run=args.dry_run,
            )
            results.append(result)

    finally:
        db.close()

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)

    total_suggested = sum(r["suggested"] for r in results)
    total_saved = sum(r["saved"] for r in results)
    total_failed = sum(r["failed"] for r in results)

    for r in results:
        status = f"{r['saved']}/{r['suggested']} salvas"
        if r["failed"]:
            status += f", {r['failed']} falhas"
        print(f"  {r['category']}: {status}")

    print(f"\nTotal: {total_saved} salvas, {total_failed} falhas, de {total_suggested} sugeridas")
    print("=" * 60)


if __name__ == "__main__":
    main()
