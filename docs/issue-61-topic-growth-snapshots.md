# Issue #61 — Historico de Crescimento por Topico (Snapshots Oportunisticos)

## Motivacao

O sistema ja possuia extracao de topicos por audiencia (Issue #29), que identifica temas recorrentes nos posts das comunidades. O crescimento de cada topico (ex: "+100%") era **estimado pelo LLM** no momento da extracao, sem base de comparacao anterior e sem reprodutibilidade — duas execucoes com os mesmos posts podiam gerar estimativas diferentes.

### Cenario do usuario

O usuario tem a audiencia "Marketing" e ve o topico "AI in Marketing" com +100% de crescimento. Ele quer saber: isso e real? Ha um mes era quanto? A tendencia e de alta ou ja estabilizou? Sem dados historicos, nao conseguimos responder.

---

## Solucao Adotada

### Abordagem: Snapshots oportunisticos (sem scheduler)

Ao inves de criar um job periodico que consome rate limit extra do Reddit, aproveitamos o momento em que uma analise de topicos ja vai rodar. **Antes de sobrescrever**, fotografamos o estado atual.

```
POST /audiences/{id}/topics/refresh (ou trigger automatico por mudanca de comunidades)
    -> TriggerTopicAnalysisUseCase
        -> CaptureSnapshotUseCase (NOVO: fotografa analise "ready" anterior)
            -> Busca analise ready mais recente
            -> Para cada topico: salva snapshot com mention_frequency, post_count, growth_percentage
        -> Cria nova analise (processing)
        -> ExtractTopicsUseCase (fluxo existente)
        -> Marca ready

GET /audiences/{id}/topics
    -> Resposta existente + NOVO: growth_source + growth_trend por topico
    -> 2+ snapshots: crescimento real calculado
    -> 1 snapshot: sem dados suficientes
    -> 0 snapshots: estimativa do LLM (comportamento original)

GET /audiences/{id}/topics/{topic_id}/growth-history (NOVO)
    -> Retorna todos os snapshots do topico ao longo do tempo
    -> Permite ao frontend plotar grafico de tendencia
```

### Decisoes arquiteturais

1. **Oportunistico vs. scheduler:** A abordagem oportunistica nao gera requests extras ao Reddit, nao requer infraestrutura nova (APScheduler/Celery) e funciona com a API publica (rate limit ~10 req/min). A frequencia dos snapshots depende do uso, mas o primeiro valor real aparece ja na segunda analise.

2. **Snapshot por nome normalizado:** Cada analise cria novos registros em `audience_topics` com novos UUIDs. Para rastrear o mesmo topico entre analises, usamos o `topic_name_normalized` (lowercase, trimmed) como chave de correlacao.

3. **Captura antes da extracao:** O snapshot e tirado ANTES da nova extracao rodar. Se a nova extracao falhar, o snapshot ja foi salvo e os dados nao se perdem.

4. **Modulo separado (`topic_snapshots`):** Segue o padrao DDD do projeto. O modulo de snapshots nao conhece o fluxo de extracao — apenas recebe um comando "capture".

5. **Calculo de crescimento real:** Quando existem 2+ snapshots, o `growth_percentage` e calculado:
   ```
   growth = ((current.mention_frequency - previous.mention_frequency) / previous.mention_frequency) * 100
   ```
   Trend: `up` (>5%), `stable` (-5% a +5%), `down` (<-5%).

6. **Retencao:** Mantemos os ultimos 12 snapshots por topico (~3 meses se o usuario roda analise semanalmente).

---

## Arquivos Criados

### `app/modules/topic_snapshots/domain/entities/topic_snapshot.py`
- Entidade `TopicSnapshot` — tabela `topic_snapshots` (id, audience_id, analysis_id, topic_name, topic_name_normalized, mention_frequency, mention_period, post_count, growth_percentage, communities, snapshot_date, created_at)
- Indices compostos: `(audience_id, topic_name_normalized, snapshot_date)` e `(audience_id, snapshot_date)`

### `app/modules/topic_snapshots/infra/repositories/topic_snapshot_repository.py`
- `normalize_topic_name(name)` — normaliza nome para matching
- `capture_snapshot(audience_id, analysis_id, topics)` — salva snapshot de todos os topicos
- `get_history_by_topic(audience_id, topic_name_normalized, limit)` — historico ordenado por data
- `get_latest_snapshot(audience_id, topic_name_normalized)` — snapshot mais recente
- `calculate_real_growth(audience_id, topic_name_normalized)` — crescimento real entre 2 mais recentes
- `delete_old_snapshots(audience_id, keep_latest)` — retencao

### `app/modules/topic_snapshots/application/use_cases/capture_snapshot_use_case.py`
- Busca analise "ready" mais recente da audiencia
- Para cada topico: normaliza nome e cria registro em `topic_snapshots`
- Limpa snapshots antigos (retencao de 12)

### `app/modules/topic_snapshots/application/use_cases/get_growth_history_use_case.py`
- Busca topico atual por ID
- Busca snapshots historicos por nome normalizado
- Calcula crescimento real entre snapshots consecutivos
- Retorna serie temporal com trend

### `app/routes/topic_snapshots.py`
- `GET /audiences/{audience_id}/topics/{topic_id}/growth-history` — historico de crescimento

### `alembic/versions/c5d6e7f8a9b0_add_topic_snapshots.py`
- Migration criando tabela `topic_snapshots` com FKs CASCADE e indices compostos

---

## Arquivos Modificados

### `app/modules/audience_topics/application/use_cases/trigger_topic_analysis_use_case.py`
- Adicionado chamada a `CaptureSnapshotUseCase.execute(audience_id)` ANTES de criar nova analise
- Lazy import para evitar dependencia circular
- Try/except para nao bloquear a analise se snapshot falhar

### `app/routes/audience_topics.py`
- `GET /audiences/{id}/topics` — enriquecido com campos `growth_source` e `growth_trend` calculados a partir dos snapshots
- `POST /audiences/{id}/topics/refresh` — captura snapshot antes de criar nova analise

### `app/routes/__init__.py`
- Import e export do `topic_snapshots_router`

### `app/main.py`
- Registro do `topic_snapshots_router`

### `alembic/env.py`
- Import da entidade `topic_snapshot` para autogenerate

---

## Endpoints

### GET /audiences/{audience_id}/topics (enriquecido)

Campos novos por topico:
- `growth_source`: `"calculated"` (baseado em snapshots reais) ou `"estimated"` (estimativa do LLM)
- `growth_trend`: `"up"`, `"stable"`, `"down"` ou `null` (sem dados suficientes)

### GET /audiences/{audience_id}/topics/{topic_id}/growth-history

Resposta:
```json
{
  "topic_id": "uuid",
  "topic_name": "AI in Marketing",
  "current": {
    "mention_frequency": 20.0,
    "post_count": 45,
    "growth_percentage": 66.7,
    "growth_source": "calculated",
    "snapshot_date": "2026-02-24"
  },
  "history": [
    {
      "mention_frequency": 12.0,
      "post_count": 28,
      "growth_percentage": 140.0,
      "growth_source": "calculated",
      "snapshot_date": "2026-02-17"
    }
  ],
  "trend": "up",
  "total_snapshots": 2
}
```

---

## Fluxo

```
1a execucao (sem snapshot anterior):
    trigger -> nenhuma analise ready -> pula captura -> roda extracao -> ready
    Resultado: growth_percentage = estimativa LLM, growth_source = "estimated"

2a execucao (1 snapshot):
    trigger -> captura snapshot da 1a analise -> roda extracao -> ready
    Resultado: growth = calculado (2a vs 1a), growth_source = "calculated"

3a execucao (2 snapshots):
    trigger -> captura snapshot da 2a analise -> roda extracao -> ready
    Resultado: growth = calculado, trend = up/stable/down
```

---

## Relacao com Issues

| Issue | Relacao |
|-------|---------|
| #29 — Audience Topic Analysis | Base: snapshots capturam dados da analise de topicos |
| #31 — Melhorias da analise de topicos | Este doc implementa o item 6 (Historico de crescimento) |
| #38 — Topic Deep Dive | Independente: deep dive nao e afetado |
| #39 — Topic Patterns | Independente: patterns nao e afetado |
