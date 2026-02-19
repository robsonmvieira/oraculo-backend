# Sistema de Sugestão Semântica de Comunidades

## Motivação

O sistema de audiências do CRM permite agrupar comunidades do Reddit por temas (ex: "Stock Investors", "Software Developers"). No entanto, encontrar novas comunidades relevantes para adicionar a uma audiência era um processo manual e demorado.

**Problema principal**: Como descobrir automaticamente comunidades similares às que já fazem parte de uma audiência?

**Requisitos identificados**:
1. Sugestões devem ser semânticas, não aleatórias
2. Sistema deve aprender com o feedback do usuário
3. Deve funcionar tanto para comunidades individuais quanto para audiências completas
4. Performance deve ser adequada para uso em tempo real

---

## Problemas Enfrentados

### 1. Como representar semanticamente uma comunidade?

**Desafio**: Uma comunidade tem nome, título e descrição. Como transformar isso em algo comparável matematicamente?

**Opções consideradas**:
- Busca por palavras-chave (muito rígido, perde contexto)
- LLM para classificar (lento e caro para cada requisição)
- Embeddings vetoriais (rápido após geração inicial)

### 2. Como armazenar e buscar vetores eficientemente?

**Desafio**: Embeddings são vetores de 1536 dimensões. Como buscar os mais similares rapidamente?

**Opções consideradas**:
- Pinecone/Weaviate (complexidade adicional de infraestrutura)
- PostgreSQL + pgvector (aproveita banco existente)

### 3. Como personalizar para cada usuário?

**Desafio**: Diferentes usuários têm diferentes interesses. Uma comunidade pode ser relevante para um e irrelevante para outro.

**Opções consideradas**:
- Treinar modelo por usuário (muito complexo)
- Filtrar baseado em feedback explícito (simples e efetivo)

---

## Decisões Tomadas

### Decisão 1: Usar OpenAI Embeddings

**Escolha**: `text-embedding-3-small` (1536 dimensões)

**Justificativas**:
- Custo baixo (~$0.02 por 1M tokens)
- Qualidade alta para textos curtos
- API simples e confiável
- Suporta batch para eficiência

### Decisão 2: PostgreSQL + pgvector

**Escolha**: Extensão pgvector no PostgreSQL existente

**Justificativas**:
- Não adiciona nova dependência de infraestrutura
- Performance adequada para nosso volume (milhares de comunidades)
- Índice IVFFlat para busca aproximada rápida
- Suporte nativo a distância cosseno

### Decisão 3: Feedback Explícito com Persistência

**Escolha**: Tabela de feedback por usuário/comunidade

**Justificativas**:
- Simples de implementar
- Transparente para o usuário
- Funciona imediatamente (sem cold start)
- Permite desfazer decisões

**Tipos de feedback**:
| Tipo | Efeito |
|------|--------|
| `interested` | Boost de +10% no score de similaridade |
| `not_relevant` | Exclui das sugestões futuras |
| `already_member` | Exclui das sugestões futuras |

---

## Solução Implementada

### Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Similar Communities System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. EMBEDDING LAYER                                              │
│     └── OpenAI text-embedding-3-small (1536 dims)               │
│                                                                  │
│  2. STORAGE LAYER (PostgreSQL + pgvector)                       │
│     ├── community_embeddings (name, embedding, metadata)        │
│     └── user_community_feedback (user_id, subreddit, feedback)  │
│                                                                  │
│  3. SERVICE LAYER                                                │
│     ├── EmbeddingService (generate, batch, cache)               │
│     └── SimilarCommunitiesService (find similar + feedback)     │
│                                                                  │
│  4. API LAYER                                                    │
│     ├── GET /communities/{name}/similar                         │
│     ├── GET /audiences/{id}/suggestions                         │
│     ├── GET /audience-templates/{id}/suggestions                │
│     ├── POST /feedback/community                                │
│     └── DELETE /feedback/community/{name}                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Fluxo de Busca

```
1. Usuário solicita sugestões para audiência
2. Sistema obtém comunidades da audiência
3. Para cada comunidade, busca embedding (cache ou gera)
4. Calcula embedding médio da audiência
5. Busca N comunidades mais similares via pgvector
6. Filtra comunidades com feedback negativo do usuário
7. Aplica boost para comunidades com feedback positivo
8. Retorna top K ordenado por score
```

### Modelo de Dados

#### Tabela: community_embeddings

```sql
CREATE TABLE community_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subreddit_name VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500),
    description TEXT,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    subscribers INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índice para busca por nome
CREATE INDEX idx_community_embeddings_name ON community_embeddings(subreddit_name);

-- Índice vetorial para similaridade (IVFFlat com 100 listas)
CREATE INDEX idx_community_embeddings_vector ON community_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### Tabela: user_community_feedback

```sql
CREATE TABLE user_community_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100),           -- session_id ou user_id futuro
    subreddit_name VARCHAR(100) NOT NULL,
    context_type VARCHAR(50) NOT NULL,  -- 'audience', 'template', 'search', 'similar'
    context_id UUID,                     -- audience_id, template_id, etc.
    feedback VARCHAR(20) NOT NULL,       -- 'interested', 'not_relevant', 'already_member'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(user_id, subreddit_name, context_type, context_id)
);

CREATE INDEX idx_feedback_user ON user_community_feedback(user_id);
CREATE INDEX idx_feedback_subreddit ON user_community_feedback(subreddit_name);
```

---

## Arquivos Criados/Alterados

### Infraestrutura

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `docker-compose.yaml` | Alterado | Mudou imagem PostgreSQL para `pgvector/pgvector:pg16` |
| `pyproject.toml` | Alterado | Adicionou dependências `openai>=1.0.0` e `pgvector>=0.3.0` |

### Migrations

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `alembic/versions/a1b2c3d4e5f6_add_pgvector_and_embeddings.py` | Criado | Habilita pgvector, cria tabelas e índices |

### Módulo similar_communities

| Arquivo | Descrição |
|---------|-----------|
| `app/modules/similar_communities/__init__.py` | Inicialização do módulo |
| `app/modules/similar_communities/domain/__init__.py` | Inicialização do domínio |
| `app/modules/similar_communities/domain/entities/__init__.py` | Inicialização das entidades |
| `app/modules/similar_communities/domain/entities/community_embedding.py` | Entidade CommunityEmbedding com suporte a pgvector |
| `app/modules/similar_communities/domain/entities/user_feedback.py` | Entidade UserFeedback com enums de tipo |
| `app/modules/similar_communities/infra/__init__.py` | Inicialização da infraestrutura |
| `app/modules/similar_communities/infra/repositories/__init__.py` | Inicialização dos repositórios |
| `app/modules/similar_communities/infra/repositories/community_embedding_repository.py` | Repositório com busca vetorial |
| `app/modules/similar_communities/infra/repositories/user_feedback_repository.py` | Repositório de feedback |
| `app/modules/similar_communities/application/__init__.py` | Inicialização da camada de aplicação |
| `app/modules/similar_communities/application/services/__init__.py` | Inicialização dos serviços |
| `app/modules/similar_communities/application/services/embedding_service.py` | Serviço de geração de embeddings |
| `app/modules/similar_communities/application/services/similar_communities_service.py` | Serviço principal de sugestões |

### Rotas

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `app/routes/similar_communities.py` | Criado | Endpoints da API |
| `app/routes/__init__.py` | Alterado | Incluído novo router |
| `app/main.py` | Alterado | Registrado router no FastAPI |

### Scripts

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `scripts/populate_embeddings.py` | Criado | Script para gerar embeddings em batch |

---

## Como Testar

### Pré-requisitos

1. Garantir que o PostgreSQL está rodando com pgvector:
```bash
docker compose up -d db
```

2. Verificar se a extensão está habilitada:
```bash
docker exec -it crm-db psql -U postgres -d crm -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

3. Rodar migrations:
```bash
alembic upgrade head
```

4. Instalar dependências no container:
```bash
docker exec crm-app uv sync
```

### Gerar Embeddings

Primeiro, popule os templates de audiência:
```bash
python -m scripts.generate_default_audiences
```

Depois, gere os embeddings:
```bash
python -m scripts.populate_embeddings
```

Ou com limite de batch:
```bash
python -m scripts.populate_embeddings --batch-size 5
```

### Testar via API

#### 1. Buscar comunidades similares a uma específica

```bash
curl "http://localhost:8000/communities/python/similar?limit=5&min_similarity=0.3"
```

Resposta esperada:
```json
{
  "source": "python",
  "suggestions": [
    {
      "name": "learnpython",
      "title": "Learn Python",
      "description": "Subreddit for posting questions...",
      "subscribers": 850000,
      "similarity_score": 0.8234,
      "reason": "Similar to r/python"
    }
  ],
  "total_found": 5,
  "filtered_by_feedback": 0
}
```

#### 2. Buscar sugestões para uma audiência

```bash
# Primeiro, obter ID de uma audiência
curl "http://localhost:8000/audiences"

# Depois, buscar sugestões
curl "http://localhost:8000/audiences/{audience_id}/suggestions?limit=10"
```

#### 3. Buscar sugestões para um template

```bash
# Listar templates
curl "http://localhost:8000/audience-templates"

# Buscar sugestões
curl "http://localhost:8000/audience-templates/{template_id}/suggestions?limit=10&min_similarity=0.3"
```

#### 4. Salvar feedback de comunidade

```bash
curl -X POST "http://localhost:8000/feedback/community" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user123" \
  -d '{
    "subreddit_name": "learnpython",
    "feedback": "not_relevant",
    "context_type": "similar",
    "context_id": null
  }'
```

#### 5. Verificar que feedback filtra sugestões

Após marcar como `not_relevant`, a comunidade não aparece mais:
```bash
curl "http://localhost:8000/communities/python/similar?limit=5" \
  -H "X-User-Id: user123"
```

#### 6. Remover feedback

```bash
curl -X DELETE "http://localhost:8000/feedback/community/learnpython" \
  -H "X-User-Id: user123"
```

### Testar Diretamente no Banco

```sql
-- Ver embeddings gerados
SELECT subreddit_name, title, subscribers,
       CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding
FROM community_embeddings
ORDER BY subscribers DESC;

-- Ver feedbacks salvos
SELECT * FROM user_community_feedback;

-- Buscar comunidades similares via SQL (exemplo)
SELECT subreddit_name, title,
       1 - (embedding <=> (SELECT embedding FROM community_embeddings WHERE subreddit_name = 'python')) as similarity
FROM community_embeddings
WHERE subreddit_name != 'python'
  AND embedding IS NOT NULL
ORDER BY embedding <=> (SELECT embedding FROM community_embeddings WHERE subreddit_name = 'python')
LIMIT 5;
```

---

## Configurações Importantes

### Variáveis de Ambiente

```bash
OPENAI_API_KEY=sk-...  # Obrigatório para gerar embeddings
```

### Parâmetros de Busca

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `limit` | 10 | Máximo de sugestões retornadas |
| `min_similarity` | 0.5 | Score mínimo (0.0 a 1.0) |

**Nota**: Para comunidades mais diversas, use `min_similarity=0.3`

### Constantes do Sistema

```python
# EmbeddingService
MODEL = "text-embedding-3-small"
DIMENSIONS = 1536

# SimilarCommunitiesService
POSITIVE_FEEDBACK_BOOST = 0.1  # +10% para feedback positivo
```

---

## Considerações de Performance

1. **Cache de Embeddings**: Embeddings são gerados uma vez e salvos no banco. Só são regenerados se título/descrição mudar.

2. **Batch Processing**: O script `populate_embeddings.py` processa em batches de 10 para otimizar chamadas à API.

3. **Índice IVFFlat**: O índice vetorial usa 100 listas para busca aproximada. Para datasets maiores, considerar aumentar.

4. **Rate Limiting Reddit**: O script aguarda 0.5s entre requisições ao Reddit para evitar bloqueio.

---

## Próximos Passos (Sugestões)

1. **Atualização Automática**: Job para atualizar embeddings quando comunidades mudam
2. **Categorização**: Usar embeddings para categorizar automaticamente comunidades
3. **Explicabilidade**: Mostrar por que uma comunidade foi sugerida (palavras em comum)
4. **A/B Testing**: Testar diferentes thresholds de similaridade
5. **Métricas**: Dashboard com taxa de aceitação de sugestões
