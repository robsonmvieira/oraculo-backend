# Issue #29 — Análise de Tópicos da Audiência

## Motivação

O sistema permite criar audiências com comunidades vinculadas, mas **não oferecia análise de conteúdo** sobre o que está sendo discutido nessas comunidades. O usuário não tinha como identificar quais temas estão em alta, quais estão crescendo, ou quais são discutidos em múltiplas comunidades da audiência.

### Cenário do usuário

O usuário criou uma audiência "Pet Lovers" com comunidades como r/DogAdvice, r/CatAdvice e r/birding. Ele quer saber: "quais temas estão em alta nessas comunidades?" — por exemplo, "questões de saúde" aparecendo em r/DogAdvice e r/CatAdvice com +400% de crescimento.

---

## Solução Adotada

### Abordagem: Job em background disparado na escrita

Ao invés de analisar sob demanda (quando o usuário abre a aba Topics), a análise é disparada automaticamente quando as comunidades da audiência mudam. Assim, quando o usuário abre a aba, os dados já estão prontos.

```
POST/PUT/ADD/REMOVE comunidades
    → TriggerTopicAnalysisUseCase
        → Calcula fingerprint (SHA256 das comunidades ordenadas)
        → Já existe análise com mesmo fingerprint? → Skip
        → Cria análise (status: "processing")
        → threading.Thread(daemon=True)
            → ExtractTopicsUseCase
                → Coleta posts (Reddit .json API)
                → LangGraph: extract_topics → estimate_growth
                → Salva tópicos no banco → status: "ready"

GET /audiences/{id}/topics
    → Busca análise mais recente
    → "ready"      → retorna tópicos
    → "processing" → retorna {status: "processing"}
    → "failed"     → retorna erro
```

### Decisões arquiteturais

1. **Trigger na escrita vs. na leitura:** Escolhido trigger na escrita para UX instantânea. O usuário não precisa esperar.

2. **Fingerprint para invalidação:** Hash SHA256 das comunidades ordenadas evita reprocessamento quando a composição não mudou (ex: update apenas do nome).

3. **LangGraph com 2 nós:** Nó 1 extrai tópicos dos posts, Nó 2 estima crescimento. Separados para manter cada prompt focado e dentro do limite de contexto.

4. **Reddit public JSON API:** Mantido o padrão existente sem autenticação OAuth (~10 req/min). Rate limit controlado com delay de 6s entre requests. Suficiente para background.

5. **Sem armazenamento de posts:** Posts são coletados, processados pelo agente, e descartados. Apenas os tópicos extraídos são persistidos. Isso evita crescimento excessivo do banco.

---

## Arquivos Criados

### `app/modules/audience_topics/domain/entities/audience_topic.py`
- Entidade `AudienceTopicAnalysis` — tabela `audience_topic_analyses` (id, audience_id, status, communities_fingerprint, total_topics, error_message, timestamps)
- Entidade `AudienceTopic` — tabela `audience_topics` (id, analysis_id, name, description, growth_percentage, mention_frequency, mention_period, post_count, communities JSON, rank)

### `alembic/versions/a8b9c0d1e2f3_add_audience_topics.py`
- Migration criando as duas tabelas com FKs CASCADE para `audiences` e `audience_topic_analyses`

### `app/modules/audience_topics/infra/repositories/audience_topic_repository.py`
- `generate_fingerprint()` — SHA256 das comunidades ordenadas
- `find_latest_ready()`, `find_by_fingerprint()` — queries para cache/invalidação
- `create_analysis()`, `mark_ready()`, `mark_failed()` — ciclo de vida da análise
- `save_topics()` — salva tópicos em batch
- `get_topics()` — listagem com ordenação (rank, growth, frequency, name)
- `delete_old_analyses()` — limpeza, mantém as 2 mais recentes

### `app/modules/audience_topics/application/use_cases/extract_topics_use_case/agent/`
- `state.py` — `TopicExtractionState` com `PostData` e `ExtractedTopic`
- `prompts/topic_extraction_prompts.py` — `extract_topics_prompt()` e `estimate_growth_prompt()`
- `topic_extraction_agent.py` — Agente LangGraph com 2 nós: `extract_topics` → `estimate_growth`

### `app/modules/audience_topics/application/use_cases/extract_topics_use_case/extract_topics_use_case.py`
- Orquestrador: coleta posts via Reddit provider → deduplica → roda agente → salva tópicos → marca como ready

### `app/modules/audience_topics/application/use_cases/trigger_topic_analysis_use_case.py`
- Verifica fingerprint, cria análise, dispara `ExtractTopicsUseCase` em `threading.Thread(daemon=True)` com `SessionLocal()` própria

### `app/routes/audience_topics.py`
- `GET /audiences/{id}/topics` — lista tópicos com status e ordenação
- `GET /audiences/{id}/topics/{topic_id}` — detalhe de um tópico
- `POST /audiences/{id}/topics/refresh` — força reprocessamento

---

## Arquivos Modificados

### `app/modules/topics/infra/providers/reddit_provider/generic_reddit_provider.py`
- Novos dataclasses: `RedditPost`, `RedditComment`, `SubredditPostsResult`
- `_respect_rate_limit()` — delay de 6s entre requests
- `get_subreddit_posts(subreddit, sort, limit, time_filter)` — busca posts via `/r/{sub}/{sort}.json`
- `get_post_comments(subreddit, post_id, limit)` — busca comentários via `/r/{sub}/comments/{id}.json`
- `collect_posts_for_communities(names, posts_per_sort)` — coleta hot + top de múltiplas comunidades

### `app/modules/audiences/application/use_cases/manage_audience_use_case.py`
- Hooks em 4 use cases: `CreateAudienceUseCase`, `UpdateAudienceUseCase`, `AddCommunityToAudienceUseCase`, `RemoveCommunityFromAudienceUseCase`
- Cada um chama `TriggerTopicAnalysisUseCase.execute()` após mutação de comunidades

### `app/main.py`
- Registro do `audience_topics_router`

### `app/routes/__init__.py`
- Export do `audience_topics_router`

### `alembic/env.py`
- Import da entidade `audience_topic` para autogenerate

---

## Como Testar

### Teste 1 — Criar audiência (dispara análise em background)

```http
POST /audiences
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Pet Lovers",
    "description": "Comunidades de pets",
    "subreddit_names": ["DogAdvice", "CatAdvice", "birding"]
}
```

**Esperado:** Audiência criada. Nos logs, `Triggering topic analysis for audience ...`.

### Teste 2 — Consultar tópicos (em processamento)

```http
GET /audiences/{audience_id}/topics
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", topics: [], total_topics: 0}`

### Teste 3 — Consultar tópicos (após ~2 minutos)

```http
GET /audiences/{audience_id}/topics
Authorization: Bearer <token>
```

**Esperado:** `{status: "ready", total_topics: N, topics: [{name, description, growth_percentage, ...}]}`

### Teste 4 — Ordenar por crescimento

```http
GET /audiences/{audience_id}/topics?sort_by=growth
Authorization: Bearer <token>
```

**Esperado:** Tópicos ordenados por `growth_percentage` decrescente.

### Teste 5 — Forçar reprocessamento

```http
POST /audiences/{audience_id}/topics/refresh
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", message: "Análise de tópicos iniciada..."}`. Status 202.

### Teste 6 — Fingerprint evita reprocessamento

```http
PUT /audiences/{audience_id}
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Novo nome"
}
```

**Esperado:** Nome atualizado. Análise de tópicos NÃO é disparada (comunidades não mudaram).

---

## Relação com Outras Issues

| Issue | Relação |
|-------|---------|
| #25 — Audience Community Sync | Sync dispara análise de tópicos quando `subreddit_names` muda |
| #23 — Audience Expansion Agent | Mesmo padrão de LangGraph agent e background thread |
| #17 — Audience User Ownership | Reutiliza `_check_ownership` nas rotas de tópicos |

---

## Melhorias Futuras (Fora do Escopo)

- **Browse all:** Listar todos os posts relacionados a um tópico específico
- **Patterns:** Detectar padrões recorrentes nos posts de um tópico (ex: perguntas frequentes)
- **Sentiment:** Análise de sentimento das discussões por tópico
- **Ask:** Q&A com IA sobre o contexto de um tópico específico
- **OAuth Reddit:** Migrar para API autenticada (100 req/min) para coleta mais rápida
- **Histórico de crescimento:** Snapshots periódicos para calcular tendência real ao longo do tempo
- **Coleta de comentários:** Incluir comentários na análise para tópicos mais ricos
