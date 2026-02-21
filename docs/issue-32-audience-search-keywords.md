# Issue #32 — Geração Automática de Keywords de Busca por Audiência

## Motivação

Na tela de detalhes de uma audiência, as tags de busca exibidas (ex: "Search Tips", "health issues", "choice", "I hate", "Looking for") eram **mockadas no frontend** e não refletiam o contexto real das comunidades da audiência. O usuário não tinha como descobrir termos de busca relevantes para explorar o conteúdo das suas comunidades.

### Cenário do usuário

O usuário criou uma audiência "Marketing Custom" com comunidades como r/socialmediamarketing, r/digitalmarketing, r/marketing e r/marketingdigitalbr. Ele quer saber: "quais termos de busca vão me ajudar a encontrar discussões relevantes?" — por exemplo, "best tools for", "struggling with", "how do you", "budget concerns" etc.

---

## Solução Adotada

### Abordagem: Pipeline de keywords em background, mesmo padrão da Issue #29

Ao invés de gerar keywords sob demanda, o pipeline é disparado automaticamente quando as comunidades da audiência mudam. Assim, quando o frontend precisa das tags, os dados já estão prontos.

```
POST/PUT/ADD/REMOVE comunidades
    → TriggerKeywordAnalysisUseCase
        → Calcula fingerprint (SHA256 das comunidades ordenadas)
        → Já existe análise com mesmo fingerprint? → Skip
        → Cria análise (status: "processing")
        → threading.Thread(daemon=True)
            → ExtractKeywordsUseCase
                → Coleta descrições das comunidades (Reddit API)
                → Busca tópicos já extraídos (se existirem)
                → LangGraph: extract_keywords (1 nó)
                → Salva keywords no banco → status: "ready"

GET /audiences/{id}/keywords
    → Busca análise mais recente
    → "ready"      → retorna keywords categorizadas
    → "processing" → retorna {status: "processing"}
    → "failed"     → retorna erro
```

### Decisões arquiteturais

1. **Módulo isolado `audience_keywords`:** Segue o padrão DDD do projeto — domain, application, infra separados. Não mistura com o módulo `audience_topics`.

2. **Enriquecimento com tópicos:** O agente recebe os tópicos já extraídos (se existirem) para gerar keywords mais contextuais. Se os tópicos ainda não estiverem prontos, gera com base apenas nas comunidades.

3. **Categorização de keywords:** Cada keyword tem uma categoria (`pain_point`, `question`, `recommendation`, `trend`, `general`) e um score de relevância (1-10). Isso permite ao frontend filtrar e exibir por tipo.

4. **LangGraph com 1 nó:** Diferente da extração de tópicos (2 nós), keywords precisam de apenas 1 chamada ao LLM. O prompt é focado e inclui contexto das comunidades + tópicos trending.

5. **Fingerprint compartilhado:** Mesmo mecanismo SHA256 das comunidades ordenadas, evitando reprocessamento quando a composição não muda.

---

## Arquivos Criados

### `app/modules/audience_keywords/domain/entities/audience_keyword.py`
- Entidade `AudienceKeywordAnalysis` — tabela `audience_keyword_analyses` (id, audience_id, status, communities_fingerprint, total_keywords, error_message, timestamps)
- Entidade `AudienceKeyword` — tabela `audience_keywords` (id, analysis_id, keyword, category, relevance_score, rank)

### `alembic/versions/b9c0d1e2f3a4_add_audience_keywords.py`
- Migration criando as duas tabelas com FKs CASCADE para `audiences` e `audience_keyword_analyses`

### `app/modules/audience_keywords/infra/repositories/audience_keyword_repository.py`
- `generate_fingerprint()` — SHA256 das comunidades ordenadas
- `find_latest_ready()`, `find_by_fingerprint()` — queries para cache/invalidação
- `create_analysis()`, `mark_ready()`, `mark_failed()` — ciclo de vida da análise
- `save_keywords()` — salva keywords em batch
- `get_keywords()` — listagem com ordenação (rank, relevance, keyword, category)
- `delete_old_analyses()` — limpeza, mantém as 2 mais recentes

### `app/modules/audience_keywords/application/use_cases/extract_keywords_use_case/agent/`
- `state.py` — `KeywordExtractionState` com `ExtractedKeyword`
- `prompts/keyword_extraction_prompts.py` — `extract_keywords_prompt()` com contexto de comunidades e tópicos
- `keyword_extraction_agent.py` — Agente LangGraph com 1 nó: `extract_keywords`

### `app/modules/audience_keywords/application/use_cases/extract_keywords_use_case/extract_keywords_use_case.py`
- Orquestrador: coleta descrições via Reddit API → busca tópicos existentes → roda agente → salva keywords → marca como ready

### `app/modules/audience_keywords/application/use_cases/trigger_keyword_analysis_use_case.py`
- Verifica fingerprint, cria análise, dispara `ExtractKeywordsUseCase` em `threading.Thread(daemon=True)` com `SessionLocal()` própria

### `app/routes/audience_keywords.py`
- `GET /audiences/{id}/keywords` — lista keywords com status e ordenação
- `POST /audiences/{id}/keywords/refresh` — força reprocessamento

---

## Arquivos Modificados

### `app/modules/audiences/application/use_cases/manage_audience_use_case.py`
- Hooks em 4 use cases: `CreateAudienceUseCase`, `UpdateAudienceUseCase`, `AddCommunityToAudienceUseCase`, `RemoveCommunityFromAudienceUseCase`
- Cada um chama `TriggerKeywordAnalysisUseCase.execute()` após mutação de comunidades (junto com o trigger de tópicos existente)

### `app/main.py`
- Registro do `audience_keywords_router`

### `app/routes/__init__.py`
- Export do `audience_keywords_router`

### `alembic/env.py`
- Import da entidade `audience_keyword` para autogenerate

---

## Como Testar

### Teste 1 — Criar audiência (dispara análise de keywords em background)

```http
POST /audiences
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Marketing Custom",
    "description": "Comunidades de marketing",
    "subreddit_names": ["socialmediamarketing", "digitalmarketing", "marketing"]
}
```

**Esperado:** Audiência criada. Nos logs, `Triggering keyword analysis for audience ...`.

### Teste 2 — Consultar keywords (em processamento)

```http
GET /audiences/{audience_id}/keywords
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", keywords: [], total_keywords: 0}`

### Teste 3 — Consultar keywords (após ~30 segundos)

```http
GET /audiences/{audience_id}/keywords
Authorization: Bearer <token>
```

**Esperado:**
```json
{
    "status": "ready",
    "total_keywords": 20,
    "keywords": [
        {
            "keyword": "best tools for",
            "category": "recommendation",
            "relevance_score": 9,
            "rank": 1
        },
        ...
    ]
}
```

### Teste 4 — Ordenar por relevância

```http
GET /audiences/{audience_id}/keywords?sort_by=relevance
Authorization: Bearer <token>
```

**Esperado:** Keywords ordenadas por `relevance_score` decrescente.

### Teste 5 — Forçar reprocessamento

```http
POST /audiences/{audience_id}/keywords/refresh
Authorization: Bearer <token>
```

**Esperado:** `{status: "processing", message: "Análise de keywords iniciada..."}`. Status 202.

### Teste 6 — Fingerprint evita reprocessamento

```http
PUT /audiences/{audience_id}
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Novo nome"
}
```

**Esperado:** Nome atualizado. Análise de keywords NÃO é disparada (comunidades não mudaram).

---

## Relação com Outras Issues

| Issue | Relação |
|-------|---------|
| #29 — Audience Topic Analysis | Mesmo padrão arquitetural (trigger + background + fingerprint + LangGraph). Keywords reutilizam tópicos extraídos para contexto |
| #25 — Audience Community Sync | Sync dispara análise de keywords quando `subreddit_names` muda |
| #17 — Audience User Ownership | Reutiliza `_check_ownership` nas rotas de keywords |

---

## Melhorias Futuras (Fora do Escopo)

- **Keywords personalizadas:** Permitir que o usuário adicione/remova keywords manualmente
- **Keywords por tópico:** Gerar keywords específicas para cada tópico extraído
- **Trending keywords:** Detectar keywords que estão ganhando tração ao longo do tempo
- **Autocomplete:** Usar keywords como sugestões de autocomplete na busca do frontend
- **Keywords multilíngue:** Gerar keywords no idioma predominante das comunidades
