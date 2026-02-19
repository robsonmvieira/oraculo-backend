# Sistema de Discovery e Browse de Comunidades

## A Dor

O modal de "Nova Audiência" precisa listar comunidades para o usuário explorar e adicionar. Até então, a única forma de encontrar comunidades era digitando no campo de busca (`GET /communities/search/{name}`), que depende de o usuário já saber o que procurar.

**Problemas concretos:**

1. **Sem browsing**: Não existia endpoint para listar comunidades sem digitar nada. O usuário abria o modal e via apenas os templates, sem opções de comunidades individuais para explorar.

2. **Base reativa**: A tabela `community_stats` (cache de stats) só era populada quando alguém abria um template ou fazia search. Se ninguém interagisse, a base ficava vazia.

3. **Sem categorização**: As comunidades não tinham categoria. Não era possível filtrar por "tech", "finance", "gaming", etc.

4. **Sem crescimento orgânico**: Não existia mecanismo para descobrir novas comunidades automaticamente. A base dependia 100% de ações manuais.

---

## Análise

### O que já tínhamos

| Recurso | Onde | O que faz |
|---------|------|-----------|
| `community_stats` | Tabela PostgreSQL | Cache de stats (subscribers, growth, icon) com TTL de 24h |
| `community_embeddings` | Tabela pgvector | Embeddings semânticos para busca por similaridade |
| `related_subs` | Tabela PostgreSQL | Cache de comunidades relacionadas (TTL 7 dias) |
| `GenericRedditProvider` | Provider | Busca dados de comunidade no Reddit API |
| `SubredditStatsProvider` | Provider | Busca growth (week/month) no SubredditStats API |
| `EmbeddingService` | Service | Gera embeddings via OpenAI text-embedding-3-small |
| `CommunityStatsService` | Service | Orquestra cache + APIs externas |
| `GenerateAudienceTemplateUseCase` | Use Case | Usa LLM para gerar keywords e buscar subreddits |

### O que faltava

1. **Coluna `category`** em `community_stats` — para categorizar comunidades
2. **Script de seed** — para popular a base inicial com comunidades curadas por categoria
3. **Script de expansão** — para descobrir novas comunidades a partir das existentes
4. **Endpoint de browse** — para o frontend listar e filtrar comunidades

### Opções consideradas para popular a base

| Opção | Descrição | Prós | Contras |
|-------|-----------|------|---------|
| Scraper periódico simples | Job buscando popular/trending do Reddit | Simples | Só descobre o que o Reddit já mostra como popular |
| Crescimento orgânico | Base cresce conforme uso | Zero esforço | Lento, depende de usuários |
| **Seed curado + scraper** | Base inicial via LLM + expansão por similaridade | Nichos desde o dia 1, cresce de forma inteligente | Mais complexo |
| Sob demanda do Reddit | Cada request consulta Reddit em tempo real | Sempre fresco | Lento, depende do Reddit |

---

## Solução: Seed Curado + Scraper de Expansão

### Fluxo Geral

```
Fase 1: SEED (roda uma vez)
    │
    │  Para cada categoria (tech, finance, health, gaming, ...):
    │    1. LLM gera 25-30 nomes de subreddits
    │    2. Reddit API valida e busca stats de cada um
    │    3. Salva em community_stats com categoria
    │    4. Gera embeddings em batch
    │
    │  Resultado: ~250 comunidades categorizadas
    │
    ▼
Fase 2: EXPANSÃO (roda periodicamente)
    │
    │  Para cada comunidade (mais antigas primeiro):
    │    1. Busca related_subs já descobertos
    │    2. Busca comunidades similares via embeddings
    │    3. Filtra as que já existem na base
    │    4. Novas: busca stats + gera embedding
    │
    │  Resultado: base cresce a cada execução
    │
    ▼
Fase 3: BROWSE (endpoint para o frontend)
    │
    │  GET /communities/browse?sort=subscribers&category=tech&limit=20
    │    → Consulta local (community_stats)
    │    → Resposta rápida, sem chamadas externas
    │
    └── Resultado: modal populado com comunidades para explorar
```

### Categorias Definidas

```
tech          Technology, programming, software development, gadgets, and IT
finance       Personal finance, investing, cryptocurrency, financial planning
health        Fitness, mental health, nutrition, medical topics, wellness
gaming        Video games, board games, esports, game development
marketing     Digital marketing, SEO, social media marketing, advertising
lifestyle     Home improvement, fashion, food, travel, relationships
education     Learning, online courses, academic subjects, career development
business      Entrepreneurship, startups, freelancing, remote work, management
science       Research, space, biology, physics, environment
entertainment Movies, TV shows, music, books, art, podcasts
```

---

## Arquivos Alterados/Criados

### Migration

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `alembic/versions/b2c3d4e5f6a7_add_category_to_community_stats.py` | Criado | Adiciona coluna `category` (String 50, nullable) + índice |

### Entidade + Repositório + Service

| Arquivo | Ação | O que mudou |
|---------|------|-------------|
| `app/modules/shared/domain/entities/community_stats.py` | Editado | +campo `category` |
| `app/modules/shared/infra/repositories/community_stats_repository.py` | Editado | +`category` no `upsert()`, +`browse()`, +`get_categories()`, +`find_oldest_updated()` |
| `app/modules/shared/application/services/community_stats_service.py` | Editado | +`category` no DTO e `get_stats()` |

### Scripts

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `scripts/seed_communities.py` | Criado | Seed de comunidades por categoria via LLM + Reddit API |
| `scripts/expand_communities.py` | Criado | Expansão via related_subs + embeddings |

### Rotas

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `app/routes/communities.py` | Criado | Endpoints `GET /communities/browse` e `GET /communities/categories` |
| `app/routes/__init__.py` | Editado | +`communities_router` |
| `app/main.py` | Editado | +`app.include_router(communities_router)` |

---

## API: Endpoints Criados

### GET /communities/browse

Browse comunidades pré-populadas com filtros e paginação.

**Query params:**

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `sort` | string | `subscribers` | `subscribers`, `growth_week` ou `growth_month` |
| `category` | string | null | Filtrar por categoria |
| `search` | string | null | Busca por nome ou título (ILIKE) |
| `limit` | int | 20 | Resultados por página (1-100) |
| `offset` | int | 0 | Offset para paginação |

**Resposta:**
```json
{
  "communities": [
    {
      "name": "python",
      "title": "Python",
      "description": "The official Python community",
      "subscribers": 1500000,
      "icon_url": "https://...",
      "growth_week": 0.85,
      "growth_month": 3.2,
      "category": "tech"
    }
  ],
  "total": 250,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### GET /communities/categories

Retorna categorias existentes na base.

**Resposta:**
```json
{
  "categories": ["business", "education", "entertainment", "finance", "gaming", "health", "lifestyle", "marketing", "science", "tech"]
}
```

---

## Resultado Esperado

### Após rodar o Seed (10 categorias)

- ~200-250 comunidades na base (25-30 por categoria, menos falhas)
- Cada uma com: nome, título, descrição, subscribers, growth, ícone, categoria
- Embeddings gerados para todas

### Após rodar a Expansão (20 fontes)

- +30-80 novas comunidades descobertas por execução
- Herdam categoria da fonte
- Taxa de descoberta diminui conforme satura (menos novidades a cada ciclo)

### No Frontend

- Modal de "Nova Audiência" mostra comunidades para browsing
- Filtro por categoria funciona
- Busca por nome/título funciona
- Paginação funciona
- Ordenação por subscribers/growth funciona

---

## Como Testar

### 1. Aplicar Migration

```bash
alembic upgrade head
```

Verificar coluna:
```bash
docker exec -it crm-db psql -U postgres -d crm -c "\d community_stats"
```

### 2. Rodar Seed (uma categoria para teste rápido)

```bash
python -m scripts.seed_communities --category tech
```

Modo dry-run (só mostra o que faria):
```bash
python -m scripts.seed_communities --category tech --dry-run
```

Todas as categorias:
```bash
python -m scripts.seed_communities
```

### 3. Testar Browse

```bash
# Top por subscribers
curl "http://localhost:8000/communities/browse?sort=subscribers&limit=5"

# Filtrar por categoria
curl "http://localhost:8000/communities/browse?category=tech&limit=5"

# Buscar por nome
curl "http://localhost:8000/communities/browse?search=python"

# Top por crescimento semanal
curl "http://localhost:8000/communities/browse?sort=growth_week&limit=10"

# Paginação
curl "http://localhost:8000/communities/browse?limit=10&offset=10"

# Listar categorias
curl "http://localhost:8000/communities/categories"
```

### 4. Rodar Expansão

```bash
# Processar 5 fontes
python -m scripts.expand_communities --limit 5

# Dry-run
python -m scripts.expand_communities --limit 5 --dry-run
```

### 5. Verificar Direto no Banco

```sql
-- Comunidades por categoria
SELECT category, COUNT(*) as total
FROM community_stats
WHERE category IS NOT NULL
GROUP BY category
ORDER BY total DESC;

-- Top 10 por subscribers na categoria tech
SELECT subreddit_name, title, subscribers, growth_week
FROM community_stats
WHERE category = 'tech'
ORDER BY subscribers DESC NULLS LAST
LIMIT 10;

-- Total geral
SELECT COUNT(*) as total,
       COUNT(category) as with_category,
       COUNT(subscribers) as with_subscribers
FROM community_stats;
```

---

## Dependências dos Scripts

| Componente | Seed | Expansão |
|------------|------|----------|
| `CommunityStatsService` | Sim | Sim |
| `EmbeddingService` | Sim | Sim |
| `GenericRedditProvider` | Sim | Sim |
| `ChatOpenAI` (LLM) | Sim | Nao |
| `RelatedSubsRepository` | Nao | Sim |
| `CommunityEmbeddingRepository` | Nao | Sim |

**Variáveis de ambiente necessárias:**
- `OPENAI_API_KEY` — para LLM (seed) e embeddings (ambos)
- `MODEL_NAME` — modelo do LLM (default: `gpt-4o-mini`)
- `DATABASE_URL` — conexão PostgreSQL
