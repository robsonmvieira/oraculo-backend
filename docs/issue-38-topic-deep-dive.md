# Issue #38 — Topic Deep Dive (Browse All)

## Motivacao

O sistema ja possuia extracao de topicos por audiencia (Issue #29), que identifica temas recorrentes nos posts das comunidades com nome, descricao, frequencia e crescimento estimado. Porem, essa analise era **superficial** — equivalente a ler manchetes sem ler as materias. O usuario sabia *quais* temas existiam, mas nao entendia *o que* estava sendo discutido dentro deles.

### Cenario do usuario

O usuario tem uma audiencia "Marketing" com comunidades como r/digital_marketing e r/DigitalMarketing. Na aba Topics, ele ve o topico "AI in Marketing" com +100% de crescimento. Ao clicar em **Browse All**, ele quer entender: quais sao as facetas desse tema? Quais perguntas as pessoas fazem? Qual o sentimento geral? Quais ferramentas sao mencionadas? O que posso fazer com essa informacao?

---

## Solucao Adotada

### Abordagem: Analise sob demanda com background thread

Diferente dos topicos (que sao extraidos automaticamente quando as comunidades mudam), o deep dive e disparado **sob demanda** — apenas quando o usuario clica em "Browse All". Isso evita custo desnecessario de LLM, ja que nem todo topico sera explorado.

```
POST /audiences/{id}/topics/{topic_id}/deep-dive/refresh
    → TriggerDeepDiveUseCase
        → Gera fingerprint (SHA256 do topic_id + comunidades)
        → Ja existe analise com mesmo fingerprint? → Retorna status
        → Cria analise (status: "processing")
        → threading.Thread(daemon=True)
            → ExtractDeepDiveUseCase
                → Coleta posts das comunidades do topico (Reddit API)
                → Filtra posts relevantes por keywords do topico
                → Busca top comentarios dos 10 posts mais relevantes
                → LangGraph: analyze_deep_dive → extract_representative_posts
                → Salva resultado no banco → status: "ready"

GET /audiences/{id}/topics/{topic_id}/deep-dive
    → Busca analise mais recente
    → "ready"      → retorna dados completos
    → "processing" → retorna {status: "processing"}
    → "failed"     → retorna erro
    → nenhuma      → retorna {status: "no_analysis"}
```

### Decisoes arquiteturais

1. **Sob demanda vs. automatico:** O deep dive so roda quando o usuario solicita. Com 200 topicos possiveis, rodar automaticamente seria caro (200 x 2 chamadas LLM + 200 x 10 requests de comentarios ao Reddit).

2. **Coleta de comentarios:** Alem dos posts, o deep dive busca os top 20 comentarios dos 10 posts mais engajados. Os comentarios sao onde as pessoas revelam dores reais, recomendam produtos e discordam — informacoes que nao aparecem nos titulos.

3. **Filtragem por relevancia:** Posts sao filtrados por keywords extraidas do nome e descricao do topico antes de enviar ao LLM. Isso reduz ruido e melhora a qualidade da analise.

4. **LangGraph com 2 nos:** No 1 faz a analise profunda (summary, subtopics, FAQs, sentiment, products, insights). No 2 seleciona posts representativos. Separados para manter cada prompt focado.

5. **JSON estruturado:** O LLM retorna JSON puro, parseado e persistido em colunas JSON no PostgreSQL. Isso permite ao frontend consumir cada secao independentemente.

6. **Prefixo r/ nas comunidades:** Os nomes das comunidades armazenados nos topicos incluem "r/" (ex: "r/digital_marketing"). O use case faz `removeprefix("r/")` antes de chamar a Reddit API.

---

## Arquivos Criados

### `app/modules/topic_deep_dive/domain/entities/topic_deep_dive.py`
- Entidade `TopicDeepDiveAnalysis` — tabela `topic_deep_dive_analyses` (id, topic_id, audience_id, status, topic_fingerprint, error_message, timestamps)
- Entidade `TopicDeepDive` — tabela `topic_deep_dives` (id, analysis_id, summary, subtopics JSON, common_questions JSON, sentiment JSON, mentioned_products JSON, representative_posts JSON, actionable_insights JSON)

### `alembic/versions/d0e1f2a3b4c5_add_topic_deep_dive.py`
- Migration criando as duas tabelas com FKs CASCADE para `audience_topics` e `audiences`

### `app/modules/topic_deep_dive/infra/repositories/topic_deep_dive_repository.py`
- `generate_fingerprint()` — SHA256 do topic_id + comunidades ordenadas
- `find_latest_by_topic()`, `find_by_fingerprint()` — queries para cache/invalidacao
- `create_analysis()`, `mark_ready()`, `mark_failed()` — ciclo de vida da analise
- `save_deep_dive()` — salva resultado do deep dive
- `get_deep_dive()` — busca resultado por analysis_id
- `delete_old_analyses()` — limpeza, mantem as 2 mais recentes

### `app/modules/topic_deep_dive/application/use_cases/extract_deep_dive_use_case/agent/`
- `state.py` — `DeepDiveState` com `PostWithComments` e `DeepDiveResult`
- `prompts/deep_dive_prompts.py` — `deep_dive_analysis_prompt()` e `select_representative_posts_prompt()`
- `deep_dive_agent.py` — Agente LangGraph com 2 nos: `analyze_deep_dive` → `extract_representative_posts`

### `app/modules/topic_deep_dive/application/use_cases/extract_deep_dive_use_case/extract_deep_dive_use_case.py`
- Orquestrador: coleta posts → filtra por relevancia → busca comentarios → roda agente → salva → marca ready
- `_extract_topic_keywords()` — extrai keywords do nome e descricao do topico
- `_filter_relevant_posts()` — filtra posts que contem keywords

### `app/modules/topic_deep_dive/application/use_cases/trigger_deep_dive_use_case.py`
- Verifica fingerprint, cria analise, dispara `ExtractDeepDiveUseCase` em `threading.Thread(daemon=True)` com `SessionLocal()` propria

### `app/routes/topic_deep_dive.py`
- `GET /audiences/{id}/topics/{topic_id}/deep-dive` — consulta deep dive
- `POST /audiences/{id}/topics/{topic_id}/deep-dive/refresh` — dispara analise (202)

### `topic-deep-dive.rest`
- Arquivo REST Client com todos os endpoints documentados, exemplos de resposta e cenarios de erro

---

## Arquivos Modificados

### `app/main.py`
- Registro do `topic_deep_dive_router`

### `app/routes/__init__.py`
- Import e export do `topic_deep_dive_router`

### `alembic/env.py`
- Import da entidade `topic_deep_dive` para autogenerate

---

## Estrutura de Dados Retornada

Quando `status = "ready"`, o endpoint retorna:

```json
{
  "status": "ready",
  "analysis_id": "uuid",
  "topic_id": "uuid",
  "topic_name": "AI in Marketing",
  "completed_at": "2026-02-22T13:26:54Z",
  "summary": "The topic of AI in Marketing has gained significant traction...",
  "subtopics": [
    {"name": "AI Tools and Automation", "description": "Exploration of...", "post_count": 12},
    {"name": "Job Security Concerns", "description": "Discussions around...", "post_count": 8}
  ],
  "common_questions": [
    {"question": "Is AI taking our jobs?", "frequency": "high", "example_context": "..."},
    {"question": "What AI tools should I learn?", "frequency": "medium", "example_context": "..."}
  ],
  "sentiment": {
    "overall": "mixed",
    "positive_ratio": 0.45,
    "negative_ratio": 0.25,
    "neutral_ratio": 0.30,
    "highlights": [
      {"text": "AI changes how we work, not why the work exists.", "sentiment": "positive", "source": "r/digital_marketing"}
    ]
  },
  "mentioned_products": [
    {"name": "Blobr AI", "category": "tool", "sentiment": "positive", "mention_count": 3, "context": "..."}
  ],
  "representative_posts": [
    {"title": "AI is NOT taking our jobs.", "subreddit": "digital_marketing", "score": 94, "permalink": "...", "excerpt": "..."}
  ],
  "actionable_insights": [
    {"insight": "Marketers should embrace AI tools...", "type": "opportunity", "confidence": "high"},
    {"insight": "There is a growing need for educational resources...", "type": "gap", "confidence": "medium"}
  ]
}
```

---

## Como Testar

### Teste 1 — Consultar deep dive (nenhuma analise existe)

```http
GET /audiences/{audience_id}/topics/{topic_id}/deep-dive
Authorization: Bearer <token>
```

**Esperado:** `{status: "no_analysis", message: "Nenhuma análise de deep dive encontrada..."}`

### Teste 2 — Disparar deep dive

```http
POST /audiences/{audience_id}/topics/{topic_id}/deep-dive/refresh
Authorization: Bearer <token>
```

**Esperado:** Status 202. `{status: "processing", message: "Análise de deep dive iniciada...", analysis_id: "uuid"}`

### Teste 3 — Consultar durante processamento

```http
GET /audiences/{audience_id}/topics/{topic_id}/deep-dive
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", message: "Análise em andamento..."}`

### Teste 4 — Consultar apos ~2-3 minutos

```http
GET /audiences/{audience_id}/topics/{topic_id}/deep-dive
Authorization: Bearer <token>
```

**Esperado:** `{status: "ready", summary: "...", subtopics: [...], ...}` com todos os campos preenchidos.

### Teste 5 — Topico inexistente

```http
GET /audiences/{audience_id}/topics/00000000-0000-0000-0000-000000000000/deep-dive
Authorization: Bearer <token>
```

**Esperado:** Status 404. `{detail: "Topic not found"}`

---

## Relacao com Outras Issues

| Issue | Relacao |
|-------|---------|
| #29 — Audience Topic Analysis | Base: deep dive analisa um topico extraido pela Issue #29 |
| #32 — Search Keywords | Mesmo padrao de modulo DDD + LangGraph + background thread |
| #17 — Audience User Ownership | Reutiliza `_check_ownership` nas rotas |

---

## Melhorias Futuras (Fora do Escopo)

- **Cache de posts:** Armazenar posts coletados para evitar re-coleta ao rodar deep dive em multiplos topicos
- **Modelo mais poderoso:** Usar gpt-4o ao inves de gpt-4o-mini para analises mais sofisticadas
- **Historico de deep dives:** Comparar deep dives ao longo do tempo para detectar evolucao
- **Deep dive automatico:** Disparar automaticamente para os top 5 topicos por crescimento
- **Export:** Permitir exportar o deep dive como PDF ou markdown
