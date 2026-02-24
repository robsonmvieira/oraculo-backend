# Issue #65 — Topic Chat — Conversa com IA por Topico com Historico

## Motivacao

O sistema ja possuia o Q&A de topicos (Issue #63) que permite perguntas livres sobre um topico. Porem, cada pergunta e **independente** — nao ha memoria de conversa. O usuario precisa repetir contexto a cada nova pergunta e nao consegue fazer follow-ups naturais como "e sobre isso?" ou "pode detalhar mais o ponto anterior?".

### Cenario do usuario

O usuario tem uma audiencia "Marketing" e ve o topico "AI in Marketing". Ele ja rodou o Deep Dive e usou o Ask Q&A. Agora quer ter uma **conversa continua**: primeiro pergunta "Quais sao as principais dores?", depois "E quais ferramentas estao sendo recomendadas para resolver essas dores?", e depois "Qual dessas ferramentas tem melhor sentimento?". Cada resposta da IA considera toda a conversa anterior, como um chat real.

### Diferencial em relacao ao Ask Q&A

| Modulo | Tipo | Estado | Historico |
|--------|------|--------|-----------|
| **Ask Q&A** (Issue #63) | Pergunta isolada | Stateless | Nao — cada pergunta e independente |
| **Topic Chat** (Issue #65) | Conversa continua | Stateful | Sim — IA lembra de toda a conversa |

---

## Solucao Adotada

### Abordagem: Chat sincrono com historico persistido

Diferente do Ask Q&A que usa cache LLM (mesma pergunta = mesma resposta), o Topic Chat **nao usa cache** — cada resposta e unica considerando o historico acumulado. A resposta continua sincrona (~3-5 segundos) pois reutiliza dados do Deep Dive sem coletar dados do Reddit.

```
POST /audiences/{id}/topics/{topic_id}/chat
    → StartConversationUseCase
        → Verifica deep dive disponivel → Define context_quality
        → Cria registro TopicConversation
        → Retorna conversation_id

POST /audiences/{id}/topics/{topic_id}/chat/{conv_id}/messages
    → SendMessageUseCase
        → Persiste mensagem do usuario
        → Carrega historico da conversa (ultimas 40 mensagens)
        → Busca deep dive context (se disponivel)
        → LangGraph: build_context → answer_with_history
            → SystemMessage (contexto + instrucoes)
            → HumanMessage/AIMessage alternados (historico)
        → Persiste resposta da IA
        → Auto-gera titulo da conversa (primeira pergunta)
        → Retorna resposta
```

### Decisoes arquiteturais

1. **Modulo separado do Ask Q&A:** O Topic Chat tem entidades, repositorios e agent proprios. O Ask Q&A continua existindo para perguntas rapidas sem estado — os dois coexistem com propositos diferentes.

2. **Historico como mensagens do LLM:** Em vez de concatenar o historico no prompt (como texto plano), o agent usa `SystemMessage` + `HumanMessage`/`AIMessage` — o formato nativo da API do LLM para conversas multi-turn. Isso permite que o modelo entenda melhor a estrutura da conversa.

3. **Limite de 40 mensagens:** Para evitar estourar o contexto do LLM, o historico e limitado a 40 mensagens (20 turnos user/assistant). Mensagens mais antigas sao descartadas do prompt mas permanecem persistidas no banco.

4. **Sem cache LLM:** Diferente do Ask Q&A (cache 48h), o chat nao cacheia respostas — cada resposta e unica dado o historico acumulado. O cache nao faz sentido em conversas multi-turn.

5. **Titulo auto-gerado:** O titulo da conversa e gerado automaticamente a partir da primeira pergunta (primeiros 100 caracteres). Isso permite que o usuario identifique conversas na listagem sem esforco.

6. **Soft delete (archive):** Conversas nao sao deletadas — sao desativadas (`is_active=False`). O historico e preservado para analytics futuros.

7. **Deep Dive como fonte de contexto:** Mesmo padrao do Ask Q&A — serializa dados do deep dive em texto plano para o system prompt. Se nao houver deep dive, `context_quality = "limited"`.

8. **`max_completion_tokens=16384`:** Mesmo padrao do Ask Q&A para suportar reasoning models.

---

## Arquivos Criados

### `app/modules/topic_chat/domain/entities/topic_conversation.py`
- Entidade `TopicConversation` — tabela `topic_conversations` (id, topic_id, audience_id, user_id, title, context_quality, is_active, created_at, updated_at)
- FKs CASCADE para `audience_topics`, `audiences` e `users`
- Relationship com `TopicConversationMessage` (cascade delete-orphan)

### `app/modules/topic_chat/domain/entities/topic_conversation_message.py`
- Entidade `TopicConversationMessage` — tabela `topic_conversation_messages` (id, conversation_id, role, content, context_quality, created_at)
- FK CASCADE para `topic_conversations`
- Relationship back_populates com `TopicConversation`

### `alembic/versions/e7f8a9b0c1d2_add_topic_chat_tables.py`
- Migration criando tabelas `topic_conversations` e `topic_conversation_messages` com todas as colunas, indices e FKs

### `app/modules/topic_chat/infra/repositories/topic_conversation_repository.py`
- `create()` — cria nova conversa
- `find_by_id()` — busca conversa por ID
- `list_by_topic_and_user()` — lista conversas de um usuario em um topico
- `update_title()` — atualiza titulo
- `update_context_quality()` — atualiza qualidade do contexto
- `touch()` — atualiza updated_at
- `deactivate()` — soft delete

### `app/modules/topic_chat/infra/repositories/topic_conversation_message_repository.py`
- `create()` — cria nova mensagem
- `list_by_conversation()` — lista mensagens em ordem cronologica
- `count_by_conversation()` — conta mensagens

### `app/modules/topic_chat/application/use_cases/send_message_use_case/agent/`
- `state.py` — `TopicChatState` (TypedDict) com: topic_name, topic_description, audience_name, community_names, language, deep_dive_context, context_quality, messages (historico), answer
- `prompts/chat_prompts.py` — `topic_chat_system_prompt()` com instrucoes para conversa multi-turn, referencia a historico, maximo 4 paragrafos
- `chat_agent.py` — Agente LangGraph com 2 nos: `build_context` → `answer_with_history`. Usa `SystemMessage` + `HumanMessage`/`AIMessage` para historico nativo do LLM

### `app/modules/topic_chat/application/use_cases/send_message_use_case/send_message_use_case.py`
- `execute()` — orquestra: persiste msg user → carrega historico → deep dive → agent → persiste msg assistant → auto-titulo → resposta
- `_build_deep_dive_context()` — serializa dados do deep dive em texto plano (mesmo padrao do Ask Q&A)

### `app/modules/topic_chat/application/use_cases/start_conversation_use_case/start_conversation_use_case.py`
- `execute()` — valida topic/audience → determina context_quality → cria conversa → retorna conversation_id

### `app/routes/topic_chat.py`
- `POST /audiences/{audience_id}/topics/{topic_id}/chat` — criar conversa
- `POST /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages` — enviar mensagem
- `GET /audiences/{audience_id}/topics/{topic_id}/chat` — listar conversas
- `GET /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages` — listar mensagens
- `DELETE /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}` — arquivar conversa
- Validacoes: ownership de audiencia + ownership de conversa
- `SendMessageRequest` — Pydantic model com `question: str` (min 3, max 500 chars)

---

## Arquivos Modificados

| Arquivo | Mudanca |
|---------|---------|
| `alembic/env.py` | Import das entidades `topic_conversation` e `topic_conversation_message` |
| `app/routes/__init__.py` | Import e export do `topic_chat_router` |
| `app/main.py` | Registro do `topic_chat_router` |

---

## Estrutura de Dados Retornada

### Criar conversa

```json
{
  "conversation_id": "uuid",
  "topic_name": "AI in Marketing",
  "context_quality": "rich",
  "suggestion": null
}
```

### Enviar mensagem

```json
{
  "answer": "Segundo as discussoes nas comunidades...",
  "context_quality": "rich",
  "message_id": "uuid",
  "conversation_id": "uuid",
  "suggestion": null
}
```

### Listar conversas

```json
{
  "conversations": [
    {
      "conversation_id": "uuid",
      "title": "Quais sao as principais dores das pessoas nesse topico?",
      "context_quality": "rich",
      "is_active": true,
      "created_at": "2026-02-24T10:00:00+00:00",
      "updated_at": "2026-02-24T10:05:00+00:00"
    }
  ]
}
```

### Listar mensagens

```json
{
  "conversation_id": "uuid",
  "title": "Quais sao as principais dores...",
  "context_quality": "rich",
  "is_active": true,
  "messages": [
    {
      "message_id": "uuid",
      "role": "user",
      "content": "Quais sao as principais dores das pessoas nesse topico?",
      "context_quality": null,
      "created_at": "2026-02-24T10:00:00+00:00"
    },
    {
      "message_id": "uuid",
      "role": "assistant",
      "content": "Segundo as discussoes nas comunidades r/digital_marketing...",
      "context_quality": "rich",
      "created_at": "2026-02-24T10:00:04+00:00"
    }
  ]
}
```

### Arquivar conversa

```json
{
  "status": "archived",
  "conversation_id": "uuid"
}
```

---

## Como Testar

### Teste 1 — Criar conversa e enviar primeira mensagem

```http
POST /audiences/{audience_id}/topics/{topic_id}/chat
Authorization: Bearer <token>
```

**Esperado:** `{conversation_id: "uuid", context_quality: "rich"}`

```http
POST /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages
Authorization: Bearer <token>
Content-Type: application/json

{"question": "Quais sao as principais dores das pessoas nesse topico?"}
```

**Esperado:** `{answer: "...", context_quality: "rich", message_id: "uuid"}`

### Teste 2 — Follow-up (IA lembra do contexto)

```http
POST /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages
Authorization: Bearer <token>
Content-Type: application/json

{"question": "E quais ferramentas estao sendo recomendadas para resolver essas dores?"}
```

**Esperado:** Resposta que referencia "dores" da mensagem anterior, mostrando que a IA tem contexto da conversa.

### Teste 3 — Listar conversas

```http
GET /audiences/{audience_id}/topics/{topic_id}/chat
Authorization: Bearer <token>
```

**Esperado:** `{conversations: [{title: "Quais sao as principais dores...", ...}]}` — titulo auto-gerado.

### Teste 4 — Listar mensagens

```http
GET /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages
Authorization: Bearer <token>
```

**Esperado:** Mensagens em ordem cronologica, alternando user/assistant.

### Teste 5 — Arquivar conversa

```http
DELETE /audiences/{audience_id}/topics/{topic_id}/chat/{conversation_id}
Authorization: Bearer <token>
```

**Esperado:** `{status: "archived"}`. Apos isso, enviar mensagem retorna 400 "Conversation is archived".

### Teste 6 — Validacoes

- Pergunta com menos de 3 chars → 422
- Conversa inexistente → 404
- Audiencia de outro usuario → 403
- Sem autenticacao → 401

---

## Relacao com Outras Issues

| Issue | Relacao |
|-------|---------|
| #63 — Topic Ask Q&A | Evolucao: Chat adiciona historico ao conceito de Q&A. Ask continua como pergunta isolada, Chat e conversa continua |
| #38 — Topic Deep Dive | Fonte de contexto: dados do deep dive sao serializados em texto plano para o system prompt do chat |
| #17 — Audience User Ownership | Reutiliza `_check_ownership` nas rotas |
| #54 — Multi-Language | Reutiliza `get_language_directive()` para respostas no idioma do usuario |

---

## Melhorias Futuras

- **SSE Streaming:** Retornar resposta token-a-token via Server-Sent Events para UX de chat real-time, aproveitando o padrao SSE ja existente no modulo de notificacoes
- **Sugestoes de perguntas:** Baseado nos dados do deep dive, sugerir follow-ups relevantes ao usuario apos cada resposta
- **Contexto expandido:** Incluir dados de sentiment analysis (Issue #59) e patterns (Issue #39) como contexto adicional para respostas mais ricas
- **Titulo inteligente:** Gerar titulo da conversa automaticamente via LLM ao inves de truncar a primeira pergunta
- **Limite de mensagens por conversa:** Definir um teto (ex: 50 mensagens) e sugerir nova conversa quando atingido
- **Exportar conversa:** Permitir download do historico em markdown ou PDF
- **Resumo de contexto:** Quando o historico ultrapassar o limite, gerar um resumo das mensagens antigas para manter contexto sem estourar tokens
- **Rate limiting:** Limitar numero de mensagens por usuario/conversa por hora
