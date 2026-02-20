# Issue #17 — Vincular Audiência ao Usuário Autenticado (Ownership)

## Motivação

Com a implementação do módulo de identidade (#15), todas as rotas de audiences passaram a exigir autenticação JWT via `get_current_user`. Porém, o `current_user` não era repassado à camada de negócio — as audiências eram criadas com `user_id = None`, listagens retornavam todas as audiências do banco sem filtro, e qualquer usuário autenticado podia editar/deletar qualquer audiência.

### Estado anterior

| Ponto | Estado |
|-------|--------|
| `audiences.user_id` | UUID nullable, sem FK, nunca populado |
| Criação | `user_id` não era passado ao `CreateAudienceInput` |
| Listagem | `GET /audiences` retornava todas, sem filtro por usuário |
| Edição/Deleção | Sem verificação de ownership |
| Criação com comunidades | Não suportada — era necessário criar a audiência vazia e adicionar comunidades uma a uma |

### Contexto de negócio

O modal de criação de audiência no frontend lista comunidades para o usuário selecionar. Faz sentido que o endpoint aceite essas comunidades na criação, evitando N+1 chamadas. Além disso, com a preparação para multi-tenancy (Fase 2), o ownership é fundamental para isolamento de dados entre usuários.

---

## Questões Levantadas

### 1. O endpoint deve aceitar comunidades na criação ou manter o fluxo separado?

Ambos. O `POST /audiences` agora aceita `community_ids` opcionalmente, e o endpoint `POST /audiences/{id}/communities` continua existindo para edição posterior. Isso reflete o fluxo real do frontend: no modal de criação o usuário seleciona comunidades, e depois pode adicionar mais na tela de edição.

### 2. Quem pode acessar audiências de outros usuários?

Apenas superusers (`is_superuser = True`). A validação verifica `audience.user_id == current_user.id OR current_user.is_superuser`. Isso prepara o terreno para futuras roles (admin do SaaS, company, etc.).

### 3. O campo user_id deve ter FK para users?

Sim. A FK garante integridade referencial no banco — não é possível ter uma audiência apontando para um usuário inexistente. A migration deleta audiências órfãs (`user_id IS NULL`) antes de aplicar o NOT NULL.

---

## Solução Adotada

### Migration: FK + NOT NULL

A migration `e4f5a6b7c8d9` faz 3 operações na tabela `audiences`:

1. **Limpa dados órfãos** — `DELETE FROM audiences WHERE user_id IS NULL`
2. **Torna NOT NULL** — `ALTER COLUMN user_id SET NOT NULL`
3. **Adiciona FK** — `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`

O CASCADE garante que ao deletar um usuário, suas audiências são removidas automaticamente.

### Entidade Audience

```python
# Antes
user_id = Column(UUID(as_uuid=True), nullable=True, index=True)

# Depois
user_id = Column(
    UUID(as_uuid=True),
    ForeignKey("users.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
```

### Criação com comunidades

`CreateAudienceInput` agora tem dois campos novos:

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `user_id` | `UUID` | Sim | ID do usuário autenticado (vem do token) |
| `community_ids` | `list[str]` | Não (default `[]`) | Nomes dos subreddits para vincular |

`CreateAudienceUseCase.execute()` cria a audiência e itera sobre `community_ids`, adicionando cada comunidade via repositório.

### Ownership check

Função `_check_ownership()` aplicada em todas as rotas que operam sobre uma audiência específica:

```python
def _check_ownership(audience, current_user: User) -> None:
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")
```

**Rotas protegidas:**
- `GET /audiences/{id}` — só retorna se for dono ou superuser
- `PUT /audiences/{id}` — 403 se não autorizado
- `DELETE /audiences/{id}` — 403 se não autorizado
- `POST /audiences/{id}/communities` — 403 se não autorizado
- `DELETE /audiences/{id}/communities/{name}` — 403 se não autorizado

### Listagem filtrada

```python
user_id = None if current_user.is_superuser else current_user.id
cards = use_case.execute(user_id)
```

- Usuário normal: vê apenas suas audiências
- Superuser: vê todas (user_id=None faz o repositório não filtrar)

---

## Arquivos Criados

### `alembic/versions/e4f5a6b7c8d9_add_fk_audiences_user_id.py`

Migration que limpa audiências órfãs, torna `user_id` NOT NULL, e adiciona FK com CASCADE para `users.id`.

## Arquivos Modificados

### `app/modules/audiences/domain/entities/audience.py`

- `user_id`: adicionado `ForeignKey("users.id", ondelete="CASCADE")`, alterado para `nullable=False`

### `app/modules/audiences/application/use_cases/manage_audience_use_case.py`

- `AudienceDTO.user_id`: de `UUID | None` para `UUID`
- `CreateAudienceInput`: `user_id` obrigatório (`UUID`), novo campo `community_ids: list[str]`
- `CreateAudienceUseCase.execute()`: itera sobre `community_ids` adicionando comunidades após criação

### `app/routes/audiences.py`

- `CreateAudienceRequest`: novo campo `community_ids: list[str] = []`
- `create_audience`: passa `current_user.id` e `community_ids` ao input; status code alterado para 201
- Todas as rotas de operação sobre audiência específica: busca audiência no repositório → `_check_ownership()` → executa operação
- `list_audiences`: filtra por `current_user.id` (superuser vê todas)

---

## Tratamento de Erros

| Cenário | Resposta HTTP | Body |
|---------|--------------|------|
| Audiência não encontrada | 404 Not Found | `{"detail": "Audience not found"}` |
| Usuário não é dono nem superuser | 403 Forbidden | `{"detail": "Acesso negado"}` |
| Sem token | 403 Forbidden | `{"detail": "Not authenticated"}` |
| Token expirado | 401 Unauthorized | `{"detail": "Token expirado"}` |

---

## Como Testar

### Teste 1 — Criar audiência com comunidades

```http
POST /audiences
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "Tech Communities",
  "description": "Comunidades de tecnologia",
  "community_ids": ["python", "javascript", "rust"]
}
```

**Esperado:** 201 com `{ id, name, description, user_id: "<id-do-token>", communities_count: 3 }`.

### Teste 2 — Criar audiência sem comunidades

```http
POST /audiences
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "Empty Audience"
}
```

**Esperado:** 201 com `communities_count: 0`.

### Teste 3 — Listar audiências (usuário normal)

```http
GET /audiences
Authorization: Bearer <access_token_user_a>
```

**Esperado:** Retorna apenas audiências do user A.

### Teste 4 — Listar audiências (superuser)

```http
GET /audiences
Authorization: Bearer <access_token_superuser>
```

**Esperado:** Retorna todas as audiências de todos os usuários.

### Teste 5 — Editar audiência de outro usuário

```http
PUT /audiences/<audience_id_do_user_a>
Authorization: Bearer <access_token_user_b>
Content-Type: application/json

{
  "name": "Tentativa de edição"
}
```

**Esperado:** 403 com `{"detail": "Acesso negado"}`.

### Teste 6 — Superuser edita audiência de qualquer usuário

```http
PUT /audiences/<audience_id_do_user_a>
Authorization: Bearer <access_token_superuser>
Content-Type: application/json

{
  "name": "Editado pelo admin"
}
```

**Esperado:** 200 com audiência atualizada.

### Teste 7 — Verificar FK no banco

```sql
SELECT a.id, a.name, a.user_id, u.email
FROM audiences a
JOIN users u ON u.id = a.user_id;
```

**Esperado:** Todas as audiências têm `user_id` válido vinculado a um usuário existente.

---

## Relação com Outras Issues

| Issue | Relação |
|-------|---------|
| #15 — Identity/Auth JWT | Base para esta issue. `get_current_user` já existia nas rotas mas não era usado na lógica |
| #8 — Busca Híbrida | Não afetada. Comunidades do browse são independentes de audiências |
| Futuro — Multi-tenancy | Ownership por `user_id` é o primeiro passo. Tenant virá como camada acima |
| Futuro — RBAC | `is_superuser` é o primeiro nível. Roles granulares substituirão a flag booleana |

---

## Melhorias Futuras (Fora do Escopo)

- **Bulk add/remove communities:** endpoint para adicionar/remover múltiplas comunidades em uma única chamada (atualmente `community_ids` só funciona na criação)
- **Compartilhamento de audiências:** permitir que um usuário compartilhe uma audiência com outro (read-only ou read-write)
- **Soft delete:** ao invés de deletar audiências, marcar como `is_deleted` para possível recuperação
- **Audit log:** registrar quem criou, editou e deletou cada audiência
