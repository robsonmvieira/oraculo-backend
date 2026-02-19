"""
Script para popular embeddings das comunidades.

Busca comunidades dos templates e gera embeddings usando a API do Reddit.

Uso:
    python -m scripts.populate_embeddings

    # Limitar quantidade
    python -m scripts.populate_embeddings --limit 100
"""

import argparse
import time

from app.modules.shared.infra.database.database import SessionLocal
from app.modules.audience_templates.infra.repositories.audience_template_repository import (
    AudienceTemplateRepository,
)
from app.modules.similar_communities.application.services.embedding_service import (
    EmbeddingService,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


def main():
    parser = argparse.ArgumentParser(description="Popula embeddings das comunidades")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Tamanho do batch para geração de embeddings (default: 10)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("POPULADOR DE EMBEDDINGS")
    print("=" * 60)

    db = SessionLocal()
    reddit = GenericRedditProvider()

    try:
        template_repo = AudienceTemplateRepository(db)
        embedding_service = EmbeddingService(db)

        # Buscar todas as comunidades dos templates
        templates = template_repo.find_all(active_only=True)
        print(f"\nTemplates encontrados: {len(templates)}")

        all_communities = set()
        for template in templates:
            communities = template_repo.get_communities(template.id)
            for comm in communities:
                all_communities.add(comm.subreddit_name)

        print(f"Comunidades únicas: {len(all_communities)}")

        if not all_communities:
            print("Nenhuma comunidade encontrada. Execute primeiro a geração de templates.")
            return

        # Buscar dados do Reddit e gerar embeddings
        community_data = []
        for name in all_communities:
            print(f"\nBuscando dados de r/{name}...")
            try:
                reddit_data = reddit.get_community_details(name)
                data = reddit_data.get("data", {})
                community_data.append({
                    "name": name,
                    "title": data.get("title", name),
                    "description": data.get("public_description", ""),
                    "subscribers": data.get("subscribers", 0),
                })
                time.sleep(0.5)  # Rate limit
            except Exception as e:
                print(f"  Erro ao buscar r/{name}: {e}")
                community_data.append({
                    "name": name,
                    "title": name,
                    "description": "",
                    "subscribers": 0,
                })

        # Processar em batches
        total_processed = 0
        for i in range(0, len(community_data), args.batch_size):
            batch = community_data[i : i + args.batch_size]
            print(f"\nGerando embeddings para batch {i // args.batch_size + 1}...")

            try:
                results = embedding_service.batch_get_or_create_embeddings(batch)
                total_processed += len(results)
                print(f"  Gerados {len(results)} embeddings")
            except Exception as e:
                print(f"  Erro: {e}")
                continue

        print("\n" + "=" * 60)
        print(f"TOTAL PROCESSADO: {total_processed}")
        print("=" * 60)

        # Estatísticas
        stats = embedding_service.get_embedding_stats()
        print(f"\nEstatísticas:")
        print(f"  - Com embedding: {stats['total_with_embeddings']}")
        print(f"  - Sem embedding: {stats['total_without_embeddings']}")
        print(f"  - Modelo: {stats['model']}")
        print(f"  - Dimensões: {stats['dimensions']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
