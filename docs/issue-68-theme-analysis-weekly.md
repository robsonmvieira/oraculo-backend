# Issue #68 — Analise Temporal de Temas (Hot Discussions & Top Content)

## Motivacao

O sistema ja possui extracao de topicos por audiencia (Issue #29), deep dive (Issue #38), patterns (Issue #39) e sentiment (Issue #59). Todas essas analises trabalham com o **retrato atemporal** da audiencia — ou seja, analisam "o que existe agora" sem diferenciar o que aconteceu **esta semana** do que aconteceu **este mes**.

Na aba **Temas** do frontend, o usuario espera duas visoes temporais distintas:

- **Hot Discussions** — "O que esta sendo discutido esta semana?" (janela de 7 dias)
- **Top Content** — "O que teve melhor desempenho este mes?" (janela de 30 dias)

### Cenario do usuario

O usuario tem uma audiencia "Pet Lovers" com comunidades como r/DogAdvice, r/cockatiel e r/turtle. Na segunda-feira, ele abre a aba Temas e quer saber o que foi mais discutido nas suas comunidades esta semana. Ele ve que "terapia com cachorros" explodiu esta semana (Hot Discussions), e que o post sobre "adocao de filhotes" foi o conteudo mais engajado do mes (Top Content).

### Diferencial em relacao a aba Topicos

| Aspecto | Aba Topicos (Issue #29) | Aba Temas (Issue #68) |
|---------|------------------------|------------------------|
| Janela temporal | Sem filtro — usa posts hot + top/month | Definida: 7 dias (hot) ou 30 dias (top) |
| Trigger | Quando comunidades mudam (fingerprint) | Periodico + sob demanda (independe de mudanca) |
| Granularidade | Topico individual (Dog, Rat, Friendship) | Tema agregado com resumo narrativo |
| Objetivo | "Quais assuntos existem?" | "O que esta em alta agora?" |

---

## Solucao Adotada

### Abordagem: Modulo independente `theme_analysis` com janela temporal

Modulo dedicado que coleta posts **filtrados por data** e gera temas temporais. Independente de `audience_topics`, com suas proprias entidades, agente e repositorio.

```
POST /audiences/{id}/themes/refresh?window=week
    → TriggerThemeAnalysisUseCase
        → Gera fingerprint (SHA256 do audience_id + comunidades + window + period_key)
        → Ja existe analise com mesmo fingerprint? → Retorna status
        → Cria analise (status: "processing", window: "week")
        → threading.Thread(daemon=True)
            → ExtractThemesUseCase
                → Coleta posts via Reddit API (hot + new para week; top/month para month)
                → Filtra posts por created_utc dentro da janela temporal
                → LangGraph: extract_themes → generate_summary
                → Salva temas no banco → status: "ready"
                → Notifica usuario via SSE

GET /audiences/{id}/themes?window=week
    → Busca analise mais recente para a janela
    → "ready"      → retorna temas com resumo
    → "processing" → retorna {status: "processing"}
    → "failed"     → retorna erro
    → nenhuma      → retorna {status: "no_analysis"}
```

### Decisoes arquiteturais

1. **Modulo separado de audience_topics:** Os topicos (Issue #29) sao atemporais e disparados por mudanca de comunidades. Os temas sao temporais e disparados periodicamente ou sob demanda. Misturar responsabilidades tornaria ambos mais complexos.

2. **Fingerprint inclui window + periodo:** O fingerprint inclui `audience_id + comunidades + window + calendar_week` (ou `calendar_month`). Assim, a mesma audiencia pode ter analises de semana e mes simultaneamente, e a analise so e reprocessada quando o periodo muda.

3. **Coleta de posts com filtro de data:** Diferente do `collect_posts_for_communities` existente (que coleta hot + top/month indistintamente), o novo use case filtra posts por `created_utc`:
   - **Week:** posts dos ultimos 7 dias (`created_utc >= now - 7d`)
   - **Month:** posts dos ultimos 30 dias (`created_utc >= now - 30d`)

4. **Sorts do Reddit por janela:**
   - **Week (Hot Discussions):** `hot` + `new` — captura o que esta quente agora e o que acabou de surgir
   - **Month (Top Content):** `top?t=month` — captura o melhor conteudo do mes por score

5. **LangGraph com 2 nos:** No 1 (`extract_themes`) identifica temas agregados a partir dos posts filtrados. No 2 (`generate_summary`) gera o resumo narrativo de cada tema.

6. **Reutilizacao do GenericRedditProvider:** O metodo `get_subreddit_posts` ja aceita `sort` e `time_filter`. Para a janela semanal, usamos `sort=hot` + `sort=new` e filtramos por `created_utc` no Python. Para a janela mensal, usamos `sort=top, time_filter=month`.

7. **Engagement score composto:** Score que combina metricas para rankear temas:
   ```
   engagement_score = (avg_score * 0.4) + (avg_comments * 0.3) + (post_count * 0.2) + (subreddit_diversity * 0.1)
   ```

---

## Entidades

### `ThemeAnalysis` — tabela `theme_analyses`

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | UUID PK | |
| audience_id | UUID FK → audiences | |
| status | String(20) | processing, ready, failed |
| time_window | String(10) | week, month |
| period_start | Date | Inicio do periodo |
| period_end | Date | Fim do periodo |
| communities_fingerprint | String(64) | SHA256 para cache |
| total_themes | Integer | |
| error_message | Text | |
| created_at | DateTime | |
| updated_at | DateTime | |
| completed_at | DateTime | |

### `Theme` — tabela `themes`

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | UUID PK | |
| analysis_id | UUID FK → theme_analyses | |
| name | String(200) | Nome do tema |
| summary | Text | Resumo narrativo gerado por IA |
| post_count | Integer | Total de posts no periodo |
| avg_score | Float | Score medio dos posts |
| avg_comments | Float | Media de comentarios |
| engagement_score | Float | Score composto de engajamento |
| top_subreddits | JSON | [{name, post_count, avg_score}] |
| top_keywords | JSON | [{keyword, frequency}] |
| representative_posts | JSON | [{title, subreddit, score, permalink}] |
| rank | Integer | Posicao por engagement_score |
| created_at | DateTime | |

---

## Estrutura de Arquivos

### Arquivos criados

```
app/modules/theme_analysis/
├── domain/
│   └── entities/
│       └── theme.py                          # ThemeAnalysis + Theme
├── application/
│   └── use_cases/
│       ├── trigger_theme_analysis_use_case.py
│       └── extract_themes_use_case/
│           ├── extract_themes_use_case.py     # Orquestrador
│           └── agent/
│               ├── state.py                   # ThemeExtractionState
│               ├── theme_extraction_agent.py  # LangGraph 2 nos
│               └── prompts/
│                   └── theme_prompts.py       # Prompts por janela
└── infra/
    └── repositories/
        └── theme_analysis_repository.py

app/routes/theme_analysis.py                   # GET + POST endpoints
```

### Arquivos modificados

| Arquivo | Mudanca |
|---------|---------|
| `app/main.py` | Registro do `theme_analysis_router` |
| `app/routes/__init__.py` | Import e export do `theme_analysis_router` |
| `alembic/env.py` | Import da entidade `theme` para autogenerate |

---

## Endpoints

### POST `/audiences/{id}/themes/refresh?window=week|month`

Dispara analise temporal de temas. Retorna 202.

**Request:**
```http
POST /audiences/{audience_id}/themes/refresh?window=week
Authorization: Bearer <token>
```

**Responses:**
- `202` — Analise iniciada: `{status: "processing", analysis_id: "uuid"}`
- `200` — Ja existe: `{status: "already_exists", analysis_id: "uuid"}`
- `400` — Audiencia sem comunidades
- `404` — Audiencia nao encontrada

### GET `/audiences/{id}/themes?window=week|month`

Consulta resultado da analise mais recente.

**Request:**
```http
GET /audiences/{audience_id}/themes?window=week&sort_by=rank
Authorization: Bearer <token>
```

**Responses:**
- `status: "ready"` — Temas com resumo, metricas e posts representativos
- `status: "processing"` — Analise em andamento
- `status: "failed"` — Erro na analise
- `status: "no_analysis"` — Nenhuma analise encontrada

---

## Agente LangGraph

### No 1 — `extract_themes`

Identifica temas temporais a partir dos posts filtrados. Foco em **relevancia temporal** — o que faz este periodo unico. Retorna entre 3 e 8 temas rankeados por engajamento.

### No 2 — `generate_summary`

Gera resumo narrativo estilo newsletter para cada tema. O resumo menciona subreddits e topicos naturalmente, captura o mood das discussoes e explica por que o tema foi relevante neste periodo.

### Suporte multi-idioma

Ambos os nos usam `get_language_directive()` para gerar conteudo no idioma preferido do usuario. JSON keys permanecem em ingles.

---

## Notificacoes

Integrado com `NotificationEventService`:
- `theme_analysis_complete` — Analise concluida com sucesso
- `theme_analysis_failed` — Analise falhou

---

## Relacao com Outras Issues

| Issue | Relacao |
|-------|---------|
| #29 — Audience Topic Analysis | Inspiracao arquitetural. Independente: temas sao temporais, topicos sao atemporais |
| Theme 02 — Intent Classification | Proximo passo: os temas serao classificados por intencao |
| Theme 03 — Narrative Summary | Integrado: resumo narrativo e gerado como parte deste modulo (no 2) |
| Theme 04 — Structured Panel Data | Futuro: dados estruturados para dashboards |

---

## Migracao

**Revision ID:** `71731c50ceea`
**Tabelas criadas:** `theme_analyses`, `themes`
**Indices:** audience_id, status, time_window, communities_fingerprint, analysis_id

---

## PR

- **Issue:** [#68](https://github.com/robsonmvieira/oraculo-backend/issues/68)
- **PR:** [#69](https://github.com/robsonmvieira/oraculo-backend/pull/69)
- **Branch:** `feat/theme-analysis-weekly`
