"""
Script para expandir a base de comunidades a partir das existentes.

Descobre novas comunidades usando:
1. related_subs (comunidades relacionadas já descobertas)
2. Embeddings (similaridade semântica via pgvector)

Processa comunidades com updated_at mais antigo primeiro (rotativo).

Uso:
    python -m scripts.expand_communities

    # Processar apenas 5 comunidades fonte
    python -m scripts.expand_communities --limit 5

    # Modo dry-run
    python -m scripts.expand_communities --dry-run
"""

import argparse
import time

from app.modules.shared.application.services.community_stats_service import (
    CommunityStatsService,
)
from app.modules.shared.infra.database.database import SessionLocal
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)
from app.modules.shared.infra.repositories.related_subs_repository import (
    RelatedSubsRepository,
)
from app.modules.similar_communities.application.services.embedding_service import (
    EmbeddingService,
)
from app.modules.similar_communities.infra.repositories.community_embedding_repository import (
    CommunityEmbeddingRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


def discover_from_related_subs(
    related_repo: RelatedSubsRepository,
    source_name: str,
) -> list[str]:
    """Descobre comunidades via related_subs (já existentes no cache)."""
    related = related_repo.find_by_source(source_name)
    return [r.related_sub for r in related]


def discover_from_embeddings(
    embedding_repo: CommunityEmbeddingRepository,
    source_name: str,
    limit: int = 10,
) -> list[str]:
    """Descobre comunidades via similaridade semântica."""
    similar = embedding_repo.find_similar_to_community(
        subreddit_name=source_name,
        limit=limit,
    )
    return [community.subreddit_name for community, _score in similar]


def process_source(
    source_name: str,
    source_category: str | None,
    stats_repo: CommunityStatsRepository,
    related_repo: RelatedSubsRepository,
    embedding_repo: CommunityEmbeddingRepository,
    stats_service: CommunityStatsService,
    embedding_service: EmbeddingService,
    reddit: GenericRedditProvider,
    delay: int,
    dry_run: bool,
) -> dict:
    """Processa uma comunidade fonte, descobrindo e salvando novas."""
    # 1. Descobrir candidatas de ambas as fontes
    from_related = discover_from_related_subs(related_repo, source_name)
    from_embeddings = discover_from_embeddings(embedding_repo, source_name)

    # 2. Merge e deduplica
    all_candidates = list(set(
        [n.lower() for n in from_related] + [n.lower() for n in from_embeddings]
    ))

    # 3. Filtrar as que já existem na base
    new_candidates = []
    for name in all_candidates:
        existing = stats_repo.find_by_name(name)
        if not existing:
            new_candidates.append(name)

    print(f"  r/{source_name}: {len(from_related)} related, {len(from_embeddings)} similar, {len(new_candidates)} novas")

    if dry_run:
        for name in new_candidates:
            print(f"    [DRY-RUN] r/{name}")
        return {
            "source": source_name,
            "from_related": len(from_related),
            "from_embeddings": len(from_embeddings),
            "new_found": len(new_candidates),
            "saved": 0,
        }

    # 4. Buscar stats e salvar novas comunidades
    saved = 0
    community_data_for_embeddings = []

    for name in new_candidates:
        try:
            reddit_data = reddit.get_community_details(name)
            data = reddit_data.get("data", {})

            if not data.get("subscribers"):
                continue

            stats = stats_service.get_stats(
                subreddit_name=name,
                reddit_data=reddit_data,
                category=source_category,
            )

            if stats:
                saved += 1
                community_data_for_embeddings.append({
                    "name": name,
                    "title": data.get("title", name),
                    "description": data.get("public_description", ""),
                    "subscribers": data.get("subscribers", 0),
                })

            time.sleep(delay)

        except Exception as e:
            print(f"    Erro r/{name}: {e}")
            continue

    # 5. Gerar embeddings em batch
    if community_data_for_embeddings:
        try:
            embedding_service.batch_get_or_create_embeddings(
                community_data_for_embeddings
            )
        except Exception as e:
            print(f"    Erro embeddings: {e}")

    print(f"    Salvas: {saved}")

    return {
        "source": source_name,
        "from_related": len(from_related),
        "from_embeddings": len(from_embeddings),
        "new_found": len(new_candidates),
        "saved": saved,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Expande base de comunidades descobrindo relacionadas"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Quantas comunidades fonte processar (default: 20)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=1,
        help="Delay entre requests ao Reddit em segundos (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem salvar",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("EXPANSÃO DE COMUNIDADES")
    print("=" * 60)

    if args.dry_run:
        print("[MODO DRY-RUN ATIVADO]")

    db = SessionLocal()
    reddit = GenericRedditProvider()

    try:
        stats_repo = CommunityStatsRepository(db)
        related_repo = RelatedSubsRepository(db)
        embedding_repo = CommunityEmbeddingRepository(db)
        stats_service = CommunityStatsService(db)
        embedding_service = EmbeddingService(db)

        # Buscar comunidades mais antigas (rotativo)
        sources = stats_repo.find_oldest_updated(limit=args.limit)
        print(f"Comunidades fonte: {len(sources)}")

        if not sources:
            print("Nenhuma comunidade encontrada. Execute primeiro o seed.")
            return

        results = []
        for source in sources:
            result = process_source(
                source_name=source.subreddit_name,
                source_category=source.category,
                stats_repo=stats_repo,
                related_repo=related_repo,
                embedding_repo=embedding_repo,
                stats_service=stats_service,
                embedding_service=embedding_service,
                reddit=reddit,
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

    total_new = sum(r["new_found"] for r in results)
    total_saved = sum(r["saved"] for r in results)

    print(f"Fontes processadas: {len(results)}")
    print(f"Novas descobertas: {total_new}")
    print(f"Salvas: {total_saved}")
    print("=" * 60)


if __name__ == "__main__":
    main()
