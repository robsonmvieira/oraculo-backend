# Issue #77 — YouTube Intelligence Module (Cross-Platform Validation)

## Motivacao

Toda a inteligencia do sistema vinha exclusivamente do Reddit. O Topic Analysis (#29) identifica topicos, o Deep Dive (#38) aprofunda cada um, o Sentiment (#59) analisa sentimento, e os Alerts (#74) detectam mudancas. Porem, nenhuma dessas analises respondia: **esse topico tem tracao fora do Reddit?**

Um topico pode explodir no Reddit mas nao ter audiencia no YouTube — ou vice-versa. Sem validacao cross-platform, o usuario corre o risco de investir em conteudo baseado apenas em uma fonte, perdendo oportunidades ou superestimando demanda.

### Cenario do usuario

O usuario tem uma audiencia "Python Developers" com 15 topicos extraidos. O topico "FastAPI vs Django" cresceu 120% nas ultimas semanas. Antes de criar conteudo sobre isso, ele quer saber:
- Esse assunto tem tracao no YouTube tambem?
- Quais canais ja cobrem esse tema? Qual o engajamento?
- Existe gap de conteudo (alta demanda no Reddit, pouca oferta no YouTube)?
- O sentimento nas duas plataformas e consistente?

Ao clicar em **YouTube Validation**, o sistema coleta videos, comentarios e transcricoes do YouTube, cruza com os dados Reddit e responde todas essas perguntas via analise LLM.

---

## Solucao Adotada

### Abordagem: Coleta multi-fonte + analise LLM unificada

O modulo combina 3 fontes de dados YouTube (API v3 para busca, yt-dlp para metadados/comentarios, youtube-transcript-api para transcricoes) com os dados Reddit ja existentes nos topicos, e alimenta um agente LangGraph que faz a analise cross-platform.

```
POST /audiences/{id}/youtube-validation
    → TriggerYouTubeValidationUseCase
        → Gera fingerprint (SHA256 do audience_id + topic_names ordenados)
        → Ja existe validacao com mesmo fingerprint? → Retorna status
        → Cria validacao (status: "processing")
        → threading.Thread(daemon=True)
            → ExtractYouTubeValidationUseCase
                → Para cada topico:
                    → YouTubeProvider.collect_for_topic()
                        → API v3 search (videos relevantes)
                        → yt-dlp (metadados: views, likes, tags)
                        → yt-dlp (comentarios com 2 fallbacks)
                        → youtube-transcript-api (transcricao com fallback de idioma)
                    → Persiste videos coletados no banco
                → Prepara dados Reddit dos topicos (nome, descricao, comunidades, post_count)
                → LangGraph agent:
                    → Gemini: analise unificada (todos os topicos em 1 chamada, 2M tokens)
                    → OpenAI: analise por topico (1 chamada por topico, 128K tokens)
                → generate_summary (resumo executivo)
                → Salva resultado → status: "ready"
                → Avalia alertas cross-platform
                → Notifica usuario via SSE

GET /audiences/{id}/youtube-validation
    → Busca validacao mais recente
    → "ready"      → retorna analysis_data + summary
    → "processing" → retorna {status: "processing"}
    → "failed"     → retorna erro
    → nenhuma      → retorna {status: "no_analysis"}

GET /audiences/{id}/youtube-validation/{topic_name}/videos
    → Retorna videos coletados para um topico especifico
```

### Decisoes arquiteturais

1. **Custo zero de coleta (quase):** A YouTube Data API v3 so e usada para search (100 units/request). Metadados, comentarios e transcricoes sao coletados via yt-dlp e youtube-transcript-api — ambos gratuitos e sem quota. Isso permite coleta agressiva sem estourar a quota diaria de 10.000 units.

2. **Dual analysis mode:** O agente detecta automaticamente o provider do LLM configurado. Com Gemini (2M tokens), envia todos os topicos em uma unica chamada para analise unificada. Com OpenAI (128K tokens), analisa topico por topico e agrega os resultados. Isso maximiza a qualidade da analise dentro dos limites de cada provider.

3. **Context limits por provider:** Um dataclass `YouTubeContextLimits` define limites especificos:
   - Gemini: 20 videos/topico, 100 comentarios/video, 50K chars de transcricao, analise unificada
   - OpenAI: 5 videos/topico, 30 comentarios/video, 10K chars de transcricao, analise por topico

4. **Persistencia de videos coletados:** Alem do resultado da analise LLM, os videos coletados sao persistidos em tabela propria (`youtube_collected_videos`). Isso permite re-analise futura sem nova coleta, browse de videos por topico no frontend, e auditoria dos dados usados na analise.

5. **Degradacao graceful:** Cada etapa de coleta (search, metadata, comments, transcript) trata erros individualmente e retorna None/[] em caso de falha. Se a API key nao estiver configurada, o search retorna lista vazia mas o modulo nao quebra. Rate limiting de 1.5s entre requests yt-dlp evita bloqueios.

6. **Alertas cross-platform:** Topicos com traction_score >= 7 geram alerta `warning`. Topicos com traction_score > 8 E content gap detectado geram alerta `critical`. Os alertas usam o mesmo sistema de `EvaluateAlertsUseCase` e aparecem via SSE no frontend.

---

## Arquivos Criados

### `app/modules/youtube_validation/domain/entities/youtube_validation.py`
- Entidade `YouTubeValidation` — tabela `youtube_validations` (id, audience_id FK, user_id FK, status, fingerprint, analysis_data JSON, summary JSON, total_videos, total_comments, model_used, error_message, timestamps)
- Entidade `YouTubeCollectedVideo` — tabela `youtube_collected_videos` (id, validation_id FK, topic_name, video_id, title, channel_name, views, likes, duration_seconds, tags JSON, description, comments JSON, transcript, transcript_lang, published_at)
- Index unico em (validation_id, video_id) para evitar duplicatas

### `alembic/versions/b2c3d4e5f6a7_add_youtube_validation_tables.py`
- Migration criando as duas tabelas com indices em audience_id, user_id, status, fingerprint, validation_id, e composite (validation_id + topic_name)

### `app/modules/youtube_validation/infra/providers/youtube_provider.py`
- `YouTubeProvider` — facade unificada com 5 metodos:
  - `search_videos()` — YouTube API v3 search/list (100 units/req)
  - `get_video_metadata()` — yt-dlp extract_info (gratis)
  - `get_video_comments()` — yt-dlp com 2 fallback strategies (gratis)
  - `get_transcript()` — youtube-transcript-api com fallback de idioma pt-BR → pt → en → qualquer (gratis)
  - `collect_for_topic()` — orquestra os 4 acima para um topico completo
- Rate limiting: 1.5s entre requests yt-dlp

### `app/modules/youtube_validation/infra/repositories/youtube_validation_repository.py`
- `generate_fingerprint()` — SHA256 do audience_id + sorted topic_names
- `find_latest_by_audience()`, `find_by_fingerprint()` — queries para cache/deduplicacao
- `create_validation()`, `mark_ready()`, `mark_failed()` — ciclo de vida
- `save_collected_videos()` — bulk insert com parse de published_at
- `get_collected_videos_by_topic()` — browse por topico
- `delete_old_validations()` — limpeza, mantem as 2 mais recentes

### `app/modules/youtube_validation/application/helpers/youtube_context_limits.py`
- `YouTubeContextLimits` dataclass com limites por provider
- `get_youtube_context_limits()` — detecta provider via env var e retorna limites apropriados

### `app/modules/youtube_validation/application/use_cases/extract_youtube_validation_use_case/agent/`
- `state.py` — `YouTubeValidationState` com `TopicVideoData` e `TopicRedditData`
- `prompts/youtube_validation_prompts.py` — 3 prompts: `unified_validation_prompt` (Gemini), `per_topic_validation_prompt` (OpenAI), `summary_prompt`
- `youtube_validation_agent.py` — Agente LangGraph: START → `analyze_cross_platform` → `generate_summary` → END. Roteia para unified ou per_topic baseado em `limits.analysis_mode`

### `app/modules/youtube_validation/application/use_cases/extract_youtube_validation_use_case/extract_youtube_validation_use_case.py`
- Orquestrador: busca topicos → coleta YouTube por topico → persiste videos → prepara dados Reddit → roda agente → salva resultado → limpa antigos → avalia alertas → notifica usuario

### `app/modules/youtube_validation/application/use_cases/trigger_youtube_validation_use_case.py`
- Verifica fingerprint, cria validacao, dispara `ExtractYouTubeValidationUseCase` em `threading.Thread(daemon=True)` com `SessionLocal()` propria

### `app/routes/youtube_validation.py`
- `POST /audiences/{id}/youtube-validation` — dispara validacao (202)
- `GET /audiences/{id}/youtube-validation` — resultado mais recente
- `GET /audiences/{id}/youtube-validation/{topic_name}/videos` — videos por topico

---

## Arquivos Modificados

### `pyproject.toml`
- Adicionadas dependencias `yt-dlp>=2024.12.0` e `youtube-transcript-api>=0.6.0`

### `alembic/env.py`
- Import da entidade `youtube_validation` para autogenerate

### `app/routes/__init__.py`
- Import e export do `youtube_validation_router`

### `app/main.py`
- Registro do `youtube_validation_router`

### `app/modules/notifications/application/services/notification_event_service.py`
- Adicionado `"youtube_validation": "YouTube Validation"` ao `_TYPE_LABELS`
- Gera automaticamente eventos `youtube_validation_complete` e `youtube_validation_failed`

### `app/modules/topic_alerts/application/helpers/alert_rules.py`
- Adicionados thresholds `CROSS_PLATFORM_WARNING_TRACTION` (7) e `CROSS_PLATFORM_CRITICAL_TRACTION` (8)
- Nova funcao `classify_cross_platform_severity(traction_score, has_content_gap)`

### `app/modules/topic_alerts/application/use_cases/evaluate_alerts_use_case.py`
- Novo metodo `evaluate_youtube_validation()` que itera topicos do resultado e cria alertas `cross_platform_validated`

---

## Estrutura de Dados Retornada

### GET /audiences/{id}/youtube-validation (status: ready)

```json
{
  "status": "ready",
  "validation_id": "uuid",
  "audience_id": "uuid",
  "completed_at": "2026-03-04T18:30:00Z",
  "model_used": "gemini-2.0-flash",
  "total_videos": 45,
  "total_comments": 1230,
  "analysis_data": {
    "topics": [
      {
        "topic_name": "FastAPI vs Django",
        "traction_score": 8.5,
        "sentiment_comparison": {
          "reddit": "positive",
          "youtube": "positive",
          "alignment": "high"
        },
        "content_gap": true,
        "content_saturated": false,
        "product_mentions": ["FastAPI", "Django REST Framework"],
        "audience_overlap_score": 7.2,
        "opportunity_insights": "High demand on Reddit with limited YouTube coverage..."
      }
    ],
    "cross_platform_summary": {
      "total_topics_with_traction": 8,
      "avg_traction_score": 6.4,
      "content_gaps_found": 3,
      "key_findings": ["..."],
      "best_opportunity": "FastAPI vs Django",
      "biggest_divergence": "..."
    }
  },
  "summary": {
    "topics_analyzed": 15,
    "topics_with_youtube_traction": 8,
    "content_gaps_found": 3,
    "avg_traction_score": 6.4,
    "total_videos_analyzed": 45,
    "total_comments_analyzed": 1230
  }
}
```

### GET /audiences/{id}/youtube-validation/{topic_name}/videos

```json
{
  "status": "ready",
  "validation_id": "uuid",
  "topic_name": "FastAPI vs Django",
  "videos_count": 12,
  "videos": [
    {
      "id": "uuid",
      "video_id": "dQw4w9WgXcQ",
      "title": "FastAPI vs Django in 2026 — Which One Should You Choose?",
      "channel_name": "Tech With Tim",
      "views": 125000,
      "likes": 4200,
      "duration_seconds": 1820,
      "tags": ["python", "fastapi", "django"],
      "description": "In this video we compare...",
      "comments_count": 89,
      "has_transcript": true,
      "transcript_lang": "en",
      "published_at": "2026-02-15T14:00:00Z"
    }
  ]
}
```

---

## Como Testar

### Teste 1 — Consultar validacao (nenhuma existe)

```http
GET /audiences/{audience_id}/youtube-validation
Authorization: Bearer <token>
```

**Esperado:** `{status: "no_analysis", message: "No YouTube validation found..."}`

### Teste 2 — Disparar validacao

```http
POST /audiences/{audience_id}/youtube-validation
Authorization: Bearer <token>
```

**Esperado:** Status 202. `{status: "processing", message: "YouTube validation started...", validation_id: "uuid", topics_count: 15}`

### Teste 3 — Consultar durante processamento

```http
GET /audiences/{audience_id}/youtube-validation
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", message: "YouTube validation in progress..."}`

### Teste 4 — Consultar apos ~3-5 minutos

```http
GET /audiences/{audience_id}/youtube-validation
Authorization: Bearer <token>
```

**Esperado:** `{status: "ready", analysis_data: {...}, summary: {...}, total_videos: N}`

### Teste 5 — Browse videos por topico

```http
GET /audiences/{audience_id}/youtube-validation/FastAPI%20vs%20Django/videos
Authorization: Bearer <token>
```

**Esperado:** `{status: "ready", videos_count: N, videos: [{title, channel_name, views, ...}]}`

### Teste 6 — Forcar reprocessamento

```http
POST /audiences/{audience_id}/youtube-validation?force=true
Authorization: Bearer <token>
```

**Esperado:** Status 202. Ignora fingerprint e cria nova validacao.

### Teste 7 — Sem YOUTUBE_API_KEY

Remova a variavel `YOUTUBE_API_KEY` do `.env` e dispare a validacao.

**Esperado:** Validacao completa sem crash. `total_videos: 0` (search nao retorna resultados, mas o modulo nao quebra).

### Teste 8 — Verificar alertas

Apos validacao com topicos de alta tracao, consulte:

```http
GET /audiences/{audience_id}/alerts
Authorization: Bearer <token>
```

**Esperado:** Alertas `cross_platform_validated` com severity `warning` (traction >= 7) ou `critical` (traction > 8 + content gap).

---

## Relacao com Outras Issues

| Issue | Relacao |
|-------|---------|
| #29 — Audience Topic Analysis | Base: validacao YouTube usa os topicos extraidos pela Issue #29 como input |
| #31 — Melhorias da analise de topicos | Esta issue implementa o item #9 (Cross-platform YouTube) da lista de melhorias |
| #38 — Topic Deep Dive | Mesmo padrao arquitetural: trigger + extract + background thread + LangGraph |
| #74 — Topic Alerts | Integra com alertas: novos tipos `cross_platform_validated` com severidade warning/critical |
| #16 — SSE Notifications | Integra com notificacoes em tempo real: `youtube_validation_complete` e `youtube_validation_failed` |
| #76 — Gemini Multi-Provider | Usa `create_llm()` e `extract_response_text()` do `llm_factory.py` para suporte multi-provider |

---

## Melhorias Futuras (Fora do Escopo)

- **Cache de videos:** Reutilizar videos ja coletados quando o fingerprint de topicos nao mudou mas o usuario quer re-analisar
- **Scheduler automatico:** Rodar validacao YouTube automaticamente apos cada nova analise de topicos
- **YouTube Shorts:** Filtrar e analisar Shorts separadamente (formato diferente, metricas diferentes)
- **Channel analysis:** Identificar canais-chave por topico e analisar seu historico de conteudo
- **Comparative timeline:** Comparar evolucao de um topico no Reddit vs YouTube ao longo do tempo
- **Export:** Permitir exportar a validacao cross-platform como PDF ou markdown
