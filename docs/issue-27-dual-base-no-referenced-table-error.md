# Issue #27 — NoReferencedTableError: User model usa Base diferente dos demais models de domínio

## Motivação

Ao chamar `PUT /audiences/{id}` com payload contendo `subreddit_names`, o servidor retornava **500 Internal Server Error** com o seguinte traceback:

```
sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'audiences.user_id'
could not find table 'users' with which to generate a foreign key to target column 'id'
```

### Cenário do usuário

O usuário tentou atualizar uma audiência com sync de comunidades (feature adicionada na Issue #25) e recebeu erro 500. O payload enviado:

```json
{
    "name": "Marketing Custom",
    "description": "",
    "subreddit_names": [
        "digitalmarketing",
        "marketing",
        "marketingdigitalbr",
        "socialmediamarketing"
    ]
}
```

---

## Análise

### Causa raiz: duas instâncias de Base (declarative base)

O projeto possuía duas instâncias separadas de Base do SQLAlchemy, cada uma com seu próprio registry de metadata:

| Base | Arquivo | Tipo | Models |
|------|---------|------|--------|
| Base #1 | `app/models/base.py` | `DeclarativeBase` (SQLAlchemy 2.0) | Lead, Proposta, StatusLead, etc. (legado) |
| Base #2 | `app/modules/shared/infra/database/orm/metadata.py` | `declarative_base()` (legacy API) | Audience, CommunityStats, LLMCache, etc. (domínio) |

O model `User` importava `Base` de `app.models.base` (Base #1), enquanto `Audience` e todos os outros models de domínio importavam de `app.modules.shared.infra.database.orm.metadata` (Base #2).

Quando o SQLAlchemy tentava resolver `ForeignKey("users.id")` no model `Audience`, ele procurava a tabela `users` no registry de metadata do Base #2 — mas ela estava registrada no Base #1. Resultado: `NoReferencedTableError`.

### Por que o bug surgiu agora?

O bug existia latente desde a Issue #17 (Audience User Ownership), mas só se manifestava em operações que forçavam o SQLAlchemy a resolver o FK em runtime. A feature de community sync (Issue #25) introduziu operações de bulk delete/insert que ativaram essa resolução, expondo o bug.

### Alembic também afetado

O `alembic/env.py` referenciava apenas `Base.metadata` (Base #1) como `target_metadata`, fazendo com que o Alembic só enxergasse os models legados para autogenerate. Os models de domínio não eram rastreados.

---

## Solução Adotada

### Fix 1: Unificar o Base do User com os demais models de domínio

```python
# Antes (app/modules/identity/domain/entities/user.py)
from app.models.base import Base

# Depois
from app.modules.shared.infra.database.orm.metadata import Base
```

Agora `User` e `Audience` compartilham o mesmo registry de metadata, permitindo que o SQLAlchemy resolva o FK `audiences.user_id → users.id` corretamente.

### Fix 2: Atualizar alembic/env.py para ambos metadata

```python
# Antes
from app.models.base import Base
target_metadata = Base.metadata

# Depois
from app.models.base import Base as LegacyBase
from app.modules.shared.infra.database.orm.metadata import Base
target_metadata = [LegacyBase.metadata, Base.metadata]
```

Além disso, todos os models de domínio foram importados no `env.py` para que o Alembic os registre no autogenerate:

- `audience`, `user`, `community_stats`, `llm_cache`, `related_sub`, `community_embedding`, `user_feedback`, `audience_template`

---

## Arquivos Modificados

### `app/modules/identity/domain/entities/user.py`
- Linha 9: troca do import de `app.models.base` para `app.modules.shared.infra.database.orm.metadata`

### `alembic/env.py`
- Linha 30: `Base` renomeado para `LegacyBase`
- Linhas 39-47: adicionados imports de todos os models de domínio
- Linha 49: `target_metadata` agora é lista com ambos metadata

---

## Como Testar

### Teste 1 — PUT com subreddit_names (reprodução do bug)

```http
PUT /audiences/{audience_id}
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Marketing Custom",
    "description": "",
    "subreddit_names": ["digitalmarketing", "marketing", "marketingdigitalbr", "socialmediamarketing"]
}
```

**Esperado:** 200 OK com `communities_count: 4`. Antes retornava 500.

### Teste 2 — PUT sem subreddit_names (backward compatible)

```http
PUT /audiences/{audience_id}
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Novo nome"
}
```

**Esperado:** 200 OK, nome atualizado, comunidades inalteradas.

### Teste 3 — Endpoints unitários de comunidades

```http
POST /audiences/{audience_id}/communities
{"subreddit_name": "typescript"}

DELETE /audiences/{audience_id}/communities/typescript
```

**Esperado:** Ambos funcionam normalmente.

---

## Relação com Outras Issues

| Issue | Relação |
|-------|---------|
| #25 — Sync de Comunidades no PUT | O bug se manifestou após essa feature ser mergeada |
| #17 — Audience User Ownership | FK `audiences.user_id → users.id` é o ponto de falha |

---

## Melhorias Futuras (Fora do Escopo)

- **Unificação completa de Base:** Migrar os models legados (`app/models/`) para o mesmo Base de domínio, eliminando a dualidade
- **Testes de integridade de FK:** Adicionar teste que valida que todos os ForeignKeys são resolvíveis dentro do mesmo registry de metadata
