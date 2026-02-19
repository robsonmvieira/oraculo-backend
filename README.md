# Oraculo Backend

API para descoberta e análise de comunidades do Reddit. Permite criar audiências segmentadas, explorar comunidades por categoria, encontrar comunidades similares via busca semântica, e gerar templates de audiência com IA.

## Visao Geral

O Oraculo ajuda a responder: **"Onde meu público-alvo está no Reddit?"**

O sistema combina dados do Reddit, busca semântica com embeddings e geração por LLM para oferecer:

- **Browse de comunidades** — base pré-populada com ~280 comunidades em 10 categorias, com filtros, ordenação e paginação
- **Audiências** — agrupamento personalizado de comunidades com stats agregados
- **Templates de audiência** — sugestões geradas por IA para nichos específicos
- **Comunidades similares** — busca semântica via pgvector para descobrir comunidades relacionadas
- **Stats e growth** — dados de subscribers, crescimento semanal/mensal com cache inteligente

## Tech Stack

| Camada | Tecnologia |
|--------|------------|
| Framework | FastAPI 0.129+ |
| ORM | SQLAlchemy 2.0+ |
| Banco | PostgreSQL + pgvector |
| Migrations | Alembic |
| Cache | Redis 5.0 |
| IA/LLM | LangChain + OpenAI (GPT-4o-mini) |
| Embeddings | OpenAI text-embedding-3-small |
| Package Manager | UV |

## Arquitetura

O projeto segue **Domain-Driven Design** com módulos isolados:

```
app/
├── main.py                        # FastAPI app + error handler global
├── config.py                      # Settings via pydantic-settings (.env)
├── routes/                        # Endpoints da API
│   ├── topics.py                  # Busca de comunidades no Reddit
│   ├── audiences.py               # CRUD de audiências
│   ├── audience_templates.py      # Templates gerados por IA
│   ├── similar_communities.py     # Similaridade semântica + feedback
│   └── communities.py             # Browse e categorias
└── modules/
    ├── topics/                    # Busca no Reddit
    │   ├── domain/                #   Entidades e erros
    │   ├── application/           #   Use cases (search, details, related)
    │   └── infra/                 #   Providers (Reddit API, SubredditStats)
    ├── audiences/                 # Gestão de audiências
    │   ├── domain/                #   Audience, AudienceCommunity
    │   ├── application/           #   Use cases (CRUD)
    │   └── infra/                 #   AudienceRepository
    ├── audience_templates/        # Templates por IA
    │   ├── domain/                #   AudienceTemplate
    │   ├── application/           #   GenerateAudienceTemplateUseCase
    │   └── infra/                 #   AudienceTemplateRepository
    ├── similar_communities/       # Embeddings e similaridade
    │   ├── domain/                #   Embedding, UserFeedback
    │   ├── application/           #   SimilarCommunitiesService
    │   └── infra/                 #   Repositories
    └── shared/                    # Infraestrutura compartilhada
        ├── domain/entities/       #   CommunityStats
        ├── application/services/  #   CommunityStatsService
        └── infra/                 #   Database, repositories, cache

scripts/
├── seed_communities.py            # Seed por categoria via LLM + Reddit API
└── expand_communities.py          # Expansão por similaridade
```

## Endpoints

### Communities

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/communities/browse` | Browse com filtros (sort, category, search, paginação) |
| GET | `/communities/categories` | Lista categorias disponíveis |
| GET | `/communities/search/{name}` | Busca comunidade no Reddit por nome |
| GET | `/communities/{name}/details` | Detalhes de uma comunidade |
| GET | `/communities/{name}/related` | Comunidades relacionadas |

### Audiences

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/audiences` | Lista audiências do usuário |
| POST | `/audiences` | Cria nova audiência |
| GET | `/audiences/{id}` | Detalhes de uma audiência |
| PUT | `/audiences/{id}` | Atualiza audiência |
| DELETE | `/audiences/{id}` | Remove audiência |

### Audience Templates

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/audience-templates` | Lista templates disponíveis |
| POST | `/audience-templates/generate` | Gera template via IA |
| GET | `/audience-templates/{id}` | Detalhes de um template |

### Similar Communities

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/similar-communities/{name}` | Busca similares via embeddings |
| POST | `/similar-communities/feedback` | Envia feedback de relevância |

## Setup

### Pre-requisitos

- Python 3.12+
- PostgreSQL com extensão pgvector
- Redis
- UV (package manager)

### Instalação

```bash
# Clonar e instalar dependências
uv sync

# Copiar variáveis de ambiente
cp .env.example .env
```

### Variáveis de Ambiente

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/crm_db
OPENAI_API_KEY=sk-...
APP_ENV=development
DEBUG=0
```

### Banco de Dados

```bash
# Subir PostgreSQL + Redis
docker-compose up -d

# Aplicar migrations
alembic upgrade head
```

### Seed de Comunidades

```bash
# Popular base com ~280 comunidades em 10 categorias
python -m scripts.seed_communities

# Apenas uma categoria
python -m scripts.seed_communities --category tech

# Dry-run (mostra sem salvar)
python -m scripts.seed_communities --dry-run
```

### Rodar

```bash
make run
# ou
uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`. Docs em `http://localhost:8000/docs`.

## Categorias de Comunidades

| Categoria | Descrição |
|-----------|-----------|
| tech | Technology, programming, software development, gadgets |
| finance | Personal finance, investing, cryptocurrency |
| health | Fitness, mental health, nutrition, wellness |
| gaming | Video games, board games, esports, game dev |
| marketing | Digital marketing, SEO, social media, advertising |
| lifestyle | Home improvement, fashion, food, travel |
| education | Learning, online courses, career development |
| business | Entrepreneurship, startups, freelancing, remote work |
| science | Research, space, biology, physics, environment |
| entertainment | Movies, TV, music, books, art, podcasts |

## Banco de Dados

### Tabelas Principais

| Tabela | Descrição |
|--------|-----------|
| `community_stats` | Cache de stats (subscribers, growth, category) com TTL 24h |
| `community_embeddings` | Vetores semânticos (pgvector) para busca por similaridade |
| `related_subs` | Cache de comunidades relacionadas (TTL 7 dias) |
| `audiences` | Audiências criadas pelo usuário |
| `audience_communities` | Comunidades associadas a uma audiência |
| `audience_templates` | Templates pré-gerados por IA |
| `user_feedback` | Feedback de relevância para refinamento |

## Documentação Adicional

- [Community Discovery & Browse](docs/community-discovery-and-browse.md) — design do sistema de seed e browse
- [Semantic Suggestion Communities](docs/semantic-suggestion-communities.md) — busca por similaridade com embeddings
- [Backlog](docs/backlog.md) — tracking de entregas e próximos itens
