# Topic Patterns — Deteccao de Padroes Cross-topic

## Motivacao

O sistema ja possuia analise de topicos por audiencia (Issue #29) e deep dive por topico individual (Issue #38). Porem, ambas analisam topicos **isoladamente**. Quando um usuario tem 20+ topicos extraidos, e muito dificil identificar manualmente:

- Quais topicos aparecem juntos nas mesmas discussoes?
- Quais perguntas sao feitas repetidamente sem respostas satisfatorias?
- Quais opinioes minoritarias estao ganhando tracao?
- Quais temas sao discutidos em uma comunidade mas ignorados em outra?
- Quais oportunidades de conteudo/produto emergem desses padroes?

### Cenario do usuario

O usuario tem a audiencia "Marketing" com comunidades como r/digital_marketing, r/marketing e r/socialmediamarketing. Na aba Topics, ele ve 20+ topicos. Ao clicar em **Patterns**, ele quer uma visao panoramica: quais conexoes existem entre os topicos? Onde estao as oportunidades que so aparecem quando se olha o conjunto?

---

## Solucao Adotada

### Abordagem: Analise sob demanda com background thread

Mesmo padrao da Fase 1 (deep dive): sob demanda, background thread, fingerprint cache.

```
POST /audiences/{id}/topics/patterns/refresh
    -> TriggerPatternAnalysisUseCase
        -> Gera fingerprint (SHA256 do audience_id + comunidades)
        -> Ja existe analise com mesmo fingerprint? -> Retorna status
        -> Cria analise (status: "processing")
        -> threading.Thread(daemon=True)
            -> DetectPatternsUseCase
                -> Busca todos os topicos da audiencia (analise mais recente ready)
                -> Coleta posts de todas as comunidades (Reddit API)
                -> Busca top comentarios dos 10 posts mais relevantes
                -> LangGraph: collect_context -> detect_patterns
                -> Salva resultado no banco -> status: "ready"

GET /audiences/{id}/topics/patterns
    -> Busca analise mais recente
    -> "ready"      -> retorna dados completos
    -> "processing" -> retorna {status: "processing"}
    -> "failed"     -> retorna erro
    -> nenhuma      -> retorna {status: "no_analysis"}
```

### Decisoes arquiteturais

1. **Cross-topic vs. per-topic:** Diferente do deep dive (que analisa 1 topico), patterns analisa TODOS os topicos da audiencia de uma vez. O LLM recebe a lista de topicos + posts + comentarios e busca conexoes.

2. **Dependencia de topicos:** A analise de patterns requer que exista uma analise de topicos com status "ready". Sem topicos extraidos, nao ha o que cruzar.

3. **Coleta de posts de todas as comunidades:** Como patterns e cross-topic, coletamos posts de TODAS as comunidades da audiencia (nao apenas de um topico especifico).

4. **LangGraph com 2 nos:** No 1 (`collect_context`) valida que os dados estao presentes. No 2 (`detect_patterns`) faz a analise via LLM com prompt especializado em deteccao de padroes.

5. **Registro de router antes do audience_topics:** O router de patterns (`/audiences/{id}/topics/patterns`) precisa ser registrado ANTES do router de audience_topics (`/audiences/{id}/topics/{topic_id}`) no `main.py`, para que FastAPI resolva `/patterns` como rota literal antes de tentar parsear como UUID.

---

## Arquivos Criados

### `app/modules/topic_patterns/domain/entities/topic_pattern.py`
- Entidade `TopicPatternAnalysis` — tabela `topic_pattern_analyses` (id, audience_id, status, communities_fingerprint, error_message, timestamps)
- Entidade `TopicPattern` — tabela `topic_patterns` (id, analysis_id, summary, co_occurrences JSON, unanswered_questions JSON, emerging_opinions JSON, cross_community_gaps JSON, content_opportunities JSON)

### `alembic/versions/e1f2a3b4c5d6_add_topic_patterns.py`
- Migration criando as duas tabelas com FKs CASCADE para `audiences`
- Revises: `d0e1f2a3b4c5` (topic deep dive)

### `app/modules/topic_patterns/infra/repositories/topic_pattern_repository.py`
- `generate_fingerprint()` — SHA256 do audience_id + comunidades ordenadas
- `find_latest_by_audience()`, `find_by_fingerprint()` — queries para cache/invalidacao
- `create_analysis()`, `mark_ready()`, `mark_failed()` — ciclo de vida da analise
- `save_pattern()` — salva resultado dos padroes
- `get_pattern()` — busca resultado por analysis_id
- `delete_old_analyses()` — limpeza, mantem as 2 mais recentes

### `app/modules/topic_patterns/application/use_cases/detect_patterns_use_case/agent/`
- `state.py` — `TopicSummary`, `PostWithComments`, `PatternResult`, `PatternDetectionState`
- `prompts/pattern_detection_prompts.py` — `pattern_detection_prompt()` com instrucoes para 6 secoes
- `pattern_detection_agent.py` — Agente LangGraph com 2 nos: `collect_context` -> `detect_patterns`

### `app/modules/topic_patterns/application/use_cases/detect_patterns_use_case/detect_patterns_use_case.py`
- Orquestrador: busca topicos -> coleta posts -> deduplicacao -> busca comentarios -> roda agente -> salva -> marca ready

### `app/modules/topic_patterns/application/use_cases/trigger_pattern_analysis_use_case.py`
- Verifica fingerprint, cria analise, dispara `DetectPatternsUseCase` em `threading.Thread(daemon=True)` com `SessionLocal()` propria

### `app/routes/topic_patterns.py`
- `GET /audiences/{id}/topics/patterns` — consulta padroes
- `POST /audiences/{id}/topics/patterns/refresh` — dispara analise (202)

### `topic-patterns.rest`
- Arquivo REST Client com todos os endpoints documentados, exemplos de resposta e cenarios de erro

---

## Arquivos Modificados

### `app/main.py`
- Registro do `topic_patterns_router` ANTES do `audience_topics_router` (para resolver conflito de rotas)

### `app/routes/__init__.py`
- Import e export do `topic_patterns_router`

### `alembic/env.py`
- Import da entidade `topic_pattern` para autogenerate

---

## Estrutura de Dados Retornada

Quando `status = "ready"`, o endpoint retorna:

```json
{
  "status": "ready",
  "analysis_id": "uuid",
  "audience_id": "uuid",
  "completed_at": "2026-02-22T14:02:09Z",
  "summary": "The analysis reveals strong interconnection between topics...",
  "co_occurrences": [
    {
      "topics": ["AI in Marketing", "Content Creation", "User-Generated Content"],
      "frequency": "high",
      "context": "Discussions often revolve around how AI tools can assist in content creation..."
    }
  ],
  "unanswered_questions": [
    {
      "question": "What are the best practices for leveraging AI without losing authenticity?",
      "frequency": "high",
      "communities": ["r/socialmediamarketing", "r/digital_marketing"],
      "opportunity": "A comprehensive guide on balancing AI tools with authentic content..."
    }
  ],
  "emerging_opinions": [
    {
      "opinion": "AI-generated content is perceived as low-quality and inauthentic.",
      "support_level": "growing",
      "evidence": "Comments expressing frustration with AI content quality are increasing.",
      "communities": ["r/marketing", "r/digital_marketing"]
    }
  ],
  "cross_community_gaps": [
    {
      "topic": "AI in Marketing",
      "discussed_in": ["r/socialmediamarketing", "r/digital_marketing"],
      "missing_in": ["r/marketing"],
      "opportunity": "The absence of AI discussions in r/marketing suggests a need..."
    }
  ],
  "content_opportunities": [
    {
      "opportunity": "Create a guide on balancing AI tools with authentic content.",
      "type": "content",
      "confidence": "high",
      "based_on": "High frequency of questions about AI's impact on authenticity."
    }
  ]
}
```

---

## Como Testar

### Teste 1 — Consultar padroes (nenhuma analise existe)

```http
GET /audiences/{audience_id}/topics/patterns
Authorization: Bearer <token>
```

**Esperado:** `{status: "no_analysis", message: "Nenhuma analise de padroes encontrada..."}`

### Teste 2 — Disparar deteccao de padroes

```http
POST /audiences/{audience_id}/topics/patterns/refresh
Authorization: Bearer <token>
```

**Esperado:** Status 202. `{status: "processing", message: "Analise de padroes iniciada...", analysis_id: "uuid"}`

### Teste 3 — Consultar durante processamento

```http
GET /audiences/{audience_id}/topics/patterns
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", message: "Analise em andamento..."}`

### Teste 4 — Consultar apos ~3-4 minutos

```http
GET /audiences/{audience_id}/topics/patterns
Authorization: Bearer <token>
```

**Esperado:** `{status: "ready", summary: "...", co_occurrences: [...], ...}` com todos os campos preenchidos.

### Teste 5 — Audiencia inexistente

```http
GET /audiences/00000000-0000-0000-0000-000000000000/topics/patterns
Authorization: Bearer <token>
```

**Esperado:** Status 404. `{detail: "Audience not found"}`

---

## Relacao com Outras Issues

| Issue | Relacao |
|-------|---------|
| #29 — Audience Topic Analysis | Dependencia: patterns requer topicos extraidos (status "ready") |
| #38 — Topic Deep Dive | Mesmo padrao arquitetural: modulo DDD + LangGraph + background thread |
| #32 — Search Keywords | Mesmo padrao de modulo DDD + LangGraph + background thread |
| #17 — Audience User Ownership | Reutiliza `_check_ownership` nas rotas |

---

## Melhorias Futuras (Fora do Escopo)

- **Temporal patterns:** Comparar padroes ao longo do tempo para detectar evolucao
- **Cross-audience patterns:** Comparar padroes entre audiencias diferentes
- **Auto-refresh:** Disparar automaticamente quando os topicos sao atualizados
- **Export:** Permitir exportar os padroes como PDF ou markdown
- **Weighted analysis:** Ponderar topicos por engajamento ou crescimento
