"""
Script para gerar as audiências default usando LLM + Reddit search.

Baseado nas audiências da referência:
- Influencers, No-coders, Podcasters
- Cold Emailers, Homeowners, Notion Users
- Parents, AirBnB Hosts, Copywriters
- Product Managers, Startup Founders, Stock Investors
- Software Developers, Freelancers, NFT Collectors

Uso:
    python -m scripts.generate_default_audiences

    # Gerar apenas uma audiência específica
    python -m scripts.generate_default_audiences --only "Startup Founders"

    # Modo dry-run (não salva no banco)
    python -m scripts.generate_default_audiences --dry-run
"""

import argparse
import sys
import time

from app.modules.audience_templates.application.use_cases.generate_audience_template_use_case import (
    GenerateAudienceTemplateUseCase,
)
from app.modules.shared.infra.database.database import SessionLocal


# Audiências default baseadas na referência
DEFAULT_AUDIENCES = [
    {
        "name": "Influencers",
        "description": "Content creators, social media influencers, and personal brand builders",
        "icon": "📱",
        "category": "business",
    },
    {
        "name": "No-coders",
        "description": "People building products without coding using no-code tools",
        "icon": "🔧",
        "category": "tech",
    },
    {
        "name": "Podcasters",
        "description": "Podcast creators, hosts, and audio content producers",
        "icon": "🎙️",
        "category": "business",
    },
    {
        "name": "Cold Emailers",
        "description": "Sales professionals and marketers doing cold outreach",
        "icon": "📧",
        "category": "business",
    },
    {
        "name": "Homeowners",
        "description": "Home owners, DIY enthusiasts, and home improvement community",
        "icon": "🏠",
        "category": "lifestyle",
    },
    {
        "name": "Notion Users",
        "description": "Notion power users, template creators, and productivity enthusiasts",
        "icon": "📝",
        "category": "tech",
    },
    {
        "name": "Parents",
        "description": "Parents, caregivers, and family-focused communities",
        "icon": "👨‍👩‍👧‍👦",
        "category": "lifestyle",
    },
    {
        "name": "AirBnB Hosts",
        "description": "Short-term rental hosts, vacation rental owners, and hospitality entrepreneurs",
        "icon": "🏡",
        "category": "business",
    },
    {
        "name": "Copywriters",
        "description": "Copywriters, content writers, and marketing writers",
        "icon": "✍️",
        "category": "business",
    },
    {
        "name": "Product Managers",
        "description": "Product managers, product owners, and product-focused professionals",
        "icon": "📊",
        "category": "tech",
    },
    {
        "name": "Startup Founders",
        "description": "Entrepreneurs, startup founders, and business builders",
        "icon": "🚀",
        "category": "business",
    },
    {
        "name": "Stock Investors",
        "description": "Stock market investors, traders, and financial enthusiasts",
        "icon": "📈",
        "category": "business",
    },
    {
        "name": "Software Developers",
        "description": "Software engineers, programmers, and developers",
        "icon": "💻",
        "category": "tech",
    },
    {
        "name": "Freelancers",
        "description": "Freelancers, independent contractors, and self-employed professionals",
        "icon": "💼",
        "category": "business",
    },
    {
        "name": "NFT Collectors",
        "description": "NFT collectors, crypto art enthusiasts, and web3 community",
        "icon": "🎨",
        "category": "tech",
    },
]


def generate_audience(db, audience_config: dict, dry_run: bool = False) -> dict:
    """Gera uma audiência usando o use case."""
    print(f"\n{'='*60}")
    print(f"Gerando: {audience_config['name']}")
    print(f"Descrição: {audience_config['description']}")
    print(f"Categoria: {audience_config['category']}")
    print(f"{'='*60}")

    if dry_run:
        print("[DRY-RUN] Pulando geração real...")
        return {"name": audience_config["name"], "status": "skipped", "subreddits": []}

    use_case = GenerateAudienceTemplateUseCase(db)

    try:
        result = use_case.execute(
            audience_name=audience_config["name"],
            description=audience_config["description"],
            icon=audience_config["icon"],
            category=audience_config["category"],
            max_subreddits=15,
        )

        print(f"\nTemplate criado: {result.template.name} (slug: {result.template.slug})")
        print(f"Subreddits encontrados: {len(result.subreddits_found)}")
        print(f"Subreddits adicionados: {result.subreddits_added}")
        print("\nSubreddits:")
        for sub in result.subreddits_found:
            print(f"  - r/{sub.name}: {sub.title} ({sub.subscribers:,} members)")

        return {
            "name": audience_config["name"],
            "status": "success",
            "subreddits": [s.name for s in result.subreddits_found],
            "count": result.subreddits_added,
        }

    except Exception as e:
        print(f"\n[ERRO] Falha ao gerar audiência: {e}")
        return {"name": audience_config["name"], "status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Gera audiências default")
    parser.add_argument(
        "--only",
        type=str,
        help="Gerar apenas uma audiência específica",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo dry-run (não salva no banco)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=2,
        help="Delay entre requisições (segundos)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("GERADOR DE AUDIÊNCIAS DEFAULT")
    print("=" * 60)

    if args.dry_run:
        print("[MODO DRY-RUN ATIVADO]")

    # Filtrar audiências se --only foi passado
    audiences_to_generate = DEFAULT_AUDIENCES
    if args.only:
        audiences_to_generate = [
            a for a in DEFAULT_AUDIENCES if a["name"].lower() == args.only.lower()
        ]
        if not audiences_to_generate:
            print(f"\n[ERRO] Audiência '{args.only}' não encontrada.")
            print("Audiências disponíveis:")
            for a in DEFAULT_AUDIENCES:
                print(f"  - {a['name']}")
            sys.exit(1)

    print(f"\nAudiências a gerar: {len(audiences_to_generate)}")

    # Conectar ao banco
    db = SessionLocal()
    results = []

    try:
        for i, audience_config in enumerate(audiences_to_generate):
            result = generate_audience(db, audience_config, dry_run=args.dry_run)
            results.append(result)

            # Delay entre requisições para não sobrecarregar a API
            if i < len(audiences_to_generate) - 1 and not args.dry_run:
                print(f"\nAguardando {args.delay}s antes da próxima...")
                time.sleep(args.delay)

    finally:
        db.close()

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)

    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped"]

    print(f"Sucesso: {len(success)}")
    print(f"Erros: {len(errors)}")
    print(f"Pulados: {len(skipped)}")

    if errors:
        print("\nAudiências com erro:")
        for r in errors:
            print(f"  - {r['name']}: {r.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
