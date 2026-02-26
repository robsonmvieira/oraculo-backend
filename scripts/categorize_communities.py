"""
Script para categorizar comunidades com category=NULL usando LLM.

Comunidades sem categoria vêm do fallback para Reddit API na busca híbrida
(Issue #8). Este script classifica cada uma em uma das categorias existentes
usando gpt-5-nano-2025-08-07 em batch.

Uso:
    python -m scripts.categorize_communities

    # Processar apenas 50 comunidades
    python -m scripts.categorize_communities --limit 50

    # Batch menor
    python -m scripts.categorize_communities --batch-size 10

    # Modo dry-run
    python -m scripts.categorize_communities --dry-run
"""

import argparse
import json
import os
import time

from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.shared.infra.database.database import SessionLocal
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)

VALID_CATEGORIES = [
    "tech",
    "finance",
    "health",
    "gaming",
    "marketing",
    "lifestyle",
    "education",
    "business",
    "science",
    "entertainment",
]


def build_categorization_prompt(communities: list[dict]) -> str:
    """Monta o prompt de categorização para o LLM."""
    community_lines = []
    for c in communities:
        line = f"- name: {c['name']}"
        if c.get("title"):
            line += f', title: "{c["title"]}"'
        if c.get("description"):
            desc = c["description"][:200]
            line += f', description: "{desc}"'
        community_lines.append(line)

    communities_text = "\n".join(community_lines)
    categories_text = ", ".join(VALID_CATEGORIES)

    return f"""You are an expert at classifying Reddit communities into categories.

Given the following Reddit communities, classify each one into exactly ONE of these categories:
{categories_text}

If a community does not clearly fit any category, use "other".

Communities to classify:
{communities_text}

Respond with a JSON object mapping each community name to its category.
Example: {{"python": "tech", "fitness": "health"}}

IMPORTANT:
- Use only the exact category names listed above, or "other"
- Include ALL communities from the input
- Use lowercase for all category values
- Return ONLY valid JSON, no extra text"""


def categorize_batch(
    llm: ChatOpenAI,
    cache_service: LLMCacheService,
    communities: list[dict],
) -> dict[str, str]:
    """
    Categoriza um batch de comunidades via LLM com cache.

    Returns:
        Dict mapeando nome da comunidade -> categoria.
    """
    cache_key = "|".join(sorted(c["name"] for c in communities))

    def compute_fn():
        prompt = build_categorization_prompt(communities)
        response = llm.invoke(prompt)
        content = response.content.strip()

        # Remove code fences se o LLM adicionar
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        return json.loads(content)

    result = cache_service.get_or_compute(
        input_text=cache_key,
        task_type=TaskType.COMMUNITY_CATEGORIZATION,
        compute_fn=compute_fn,
    )

    # Valida categorias retornadas
    validated = {}
    for name, category in result.items():
        cat = category.lower().strip()
        name_clean = name.lower().strip().replace("r/", "")
        if cat in VALID_CATEGORIES or cat == "other":
            validated[name_clean] = cat
        else:
            print(
                f"    AVISO: Categoria inválida '{cat}' para r/{name}, usando 'other'"
            )
            validated[name_clean] = "other"

    return validated


def process_batch(
    batch: list,
    llm: ChatOpenAI,
    cache_service: LLMCacheService,
    stats_repo: CommunityStatsRepository,
    dry_run: bool,
) -> dict:
    """Processa um batch de comunidades sem categoria."""
    communities_data = [
        {
            "name": c.subreddit_name,
            "title": c.title,
            "description": c.description,
        }
        for c in batch
    ]

    try:
        categorizations = categorize_batch(llm, cache_service, communities_data)
    except json.JSONDecodeError as e:
        print(f"    ERRO: Resposta do LLM não é JSON válido: {e}")
        return {"processed": 0, "failed": len(batch), "skipped": 0}
    except Exception as e:
        print(f"    ERRO: Chamada ao LLM falhou: {e}")
        return {"processed": 0, "failed": len(batch), "skipped": 0}

    processed = 0
    skipped = 0

    for community in batch:
        name = community.subreddit_name.lower()
        category = categorizations.get(name)

        if not category:
            print(f"    AVISO: Sem categoria retornada para r/{name}, pulando")
            skipped += 1
            continue

        if category == "other":
            print(f"    r/{name} -> other (mantendo NULL para revisão futura)")
            skipped += 1
            continue

        if dry_run:
            print(f"    [DRY-RUN] r/{name} -> {category}")
            processed += 1
            continue

        try:
            stats_repo.upsert(
                subreddit_name=name,
                category=category,
            )
            print(f"    r/{name} -> {category}")
            processed += 1
        except Exception as e:
            print(f"    ERRO ao atualizar r/{name}: {e}")
            skipped += 1

    return {"processed": processed, "failed": 0, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(
        description="Categoriza comunidades com category=NULL usando LLM"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Máximo de comunidades a processar (default: 200)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Comunidades por chamada ao LLM (default: 20)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=2,
        help="Delay entre batches em segundos (default: 2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria feito sem salvar",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("CATEGORIZAÇÃO DE COMUNIDADES")
    print("=" * 60)

    if args.dry_run:
        print("[MODO DRY-RUN ATIVADO]")

    db = SessionLocal()
    llm = ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        temperature=0,
    )

    try:
        stats_repo = CommunityStatsRepository(db)
        cache_service = LLMCacheService(db)

        # 1. Buscar comunidades sem categoria
        uncategorized = stats_repo.find_uncategorized(limit=args.limit)
        print(f"\nComunidades sem categoria encontradas: {len(uncategorized)}")

        if not uncategorized:
            print("Nenhuma comunidade sem categoria. Nada a fazer.")
            return

        # 2. Processar em batches
        total_processed = 0
        total_failed = 0
        total_skipped = 0

        for i in range(0, len(uncategorized), args.batch_size):
            batch = uncategorized[i : i + args.batch_size]
            batch_num = i // args.batch_size + 1
            total_batches = (
                len(uncategorized) + args.batch_size - 1
            ) // args.batch_size

            print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} comunidades)")

            result = process_batch(
                batch=batch,
                llm=llm,
                cache_service=cache_service,
                stats_repo=stats_repo,
                dry_run=args.dry_run,
            )

            total_processed += result["processed"]
            total_failed += result["failed"]
            total_skipped += result["skipped"]

            # Delay entre batches (exceto o último)
            if i + args.batch_size < len(uncategorized):
                time.sleep(args.delay)

    finally:
        db.close()

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Total sem categoria: {len(uncategorized)}")
    print(f"Categorizadas: {total_processed}")
    print(f"Puladas (other/sem resposta): {total_skipped}")
    print(f"Falhas: {total_failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
