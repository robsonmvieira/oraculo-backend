# Issue #16 — Sistema de Notificacoes com SSE (Server-Sent Events)

## Motivacao

A aplicacao possui multiplos processos assincronos (behavioral patterns, deep dive, topic patterns, keywords, topics) que rodam em background threads. Ate entao, o frontend precisava fazer **polling** periodico nos endpoints GET para descobrir se um processo terminou. Isso gera requests desnecessarios e atraso na experiencia do usuario.

### Cenario do usuario

O usuario dispara uma analise de "Deep Dive" para um topico. Em vez de ficar recarregando a pagina ou aguardando um spinner indefinidamente, ele recebe uma **notificacao em tempo real** quando a analise termina (sucesso ou falha). Alem disso, pode ver o historico de notificacoes, marcar como lidas, e ter um badge de "nao lidas" na interface.

---

## Solucao Adotada

### Abordagem: SSE + Persistencia no PostgreSQL + Redis pub/sub

```
Background Thread (use case finaliza)
    |
    v
NotificationEventService.notify()
    |-- 1. Persiste notificacao no PostgreSQL (is_read=false)
    |-- 2. Publica JSON no Redis pub/sub (canal: notifications:{user_id})
            |
            v
SSE Endpoint (GET /notifications/stream?token=jwt)
    |
    v (StreamingResponse text/event-stream)
Frontend (EventSource) -> exibe notificacao em tempo real
    |
    v
Usuario marca como lida -> PATCH /notifications/{id}/read
```

### Decisoes arquiteturais

1. **SSE em vez de WebSocket:** Comunicacao e unidirecional (servidor -> cliente). SSE e mais simples, nativo do HTTP, tem reconexao automatica no browser, e nao requer protocolo de handshake especial.

2. **Redis pub/sub por usuario:** Canal `notifications:{user_id}` — cada conexao SSE subscreve apenas ao seu canal. Mais eficiente e simples que um canal global com filtragem client-side.

3. **Autenticacao via query param:** `EventSource` do browser nao suporta headers customizados. O JWT e enviado como `?token=` na URL. A logica de validacao replica a de `get_current_user` de `identity/dependencies.py`.

4. **Persistencia no banco:** Notificacoes ficam salvas para controle de lida/nao lida, historico, e reconexao sem perda. O SSE e apenas o canal de entrega em tempo real; o banco e a fonte da verdade.

5. **Notificacao nunca bloqueia analise:** Todas as chamadas ao `NotificationEventService` nos use cases ficam em `try/except` silencioso. Se Redis ou banco falhar ao publicar, a analise continua normalmente.

6. **Cleanup automatico:** Notificacoes lidas com mais de 30 dias sao removidas de forma probabilistica (1% das chamadas de listagem).

---

## Estrutura do Modulo

```
app/modules/notifications/
|-- domain/entities/notification.py          # Entidade SQLAlchemy (tabela notifications)
|-- application/services/
|   |-- notification_event_service.py        # Bridge: persiste + publica Redis pub/sub
|-- infra/repositories/
    |-- notification_repository.py           # CRUD + mark_read + count_unread + cleanup
```

### Tabela `notifications`

| Coluna     | Tipo         | Descricao                                      |
|------------|--------------|-------------------------------------------------|
| id         | UUID PK      | Identificador unico                             |
| user_id    | UUID FK      | Referencia ao usuario (CASCADE delete)          |
| type       | VARCHAR(60)  | Tipo da notificacao (ex: deep_dive_complete)    |
| title      | VARCHAR(255) | Titulo legivel (ex: "Deep Dive Ready")          |
| message    | TEXT         | Mensagem descritiva                             |
| metadata   | JSONB        | Contexto: audience_id, topic_id, analysis_id... |
| is_read    | BOOLEAN      | Status de lida (default: false)                 |
| created_at | TIMESTAMPTZ  | Data de criacao                                 |
| read_at    | TIMESTAMPTZ  | Data em que foi marcada como lida               |

Indices: `ix_notifications_user_id`, partial index `ix_notifications_user_unread` (WHERE is_read=false).

---

## Endpoints

### SSE (Server-Sent Events)

```
GET /notifications/stream?token=<jwt>
```

Conexao persistente. Eventos chegam no formato:
```
id: <notification_id>
event: notification
data: {"id":"...","type":"deep_dive_complete","title":"Deep Dive Ready",...}
```

Heartbeat a cada ~30s: `: heartbeat`

### REST

| Metodo | Endpoint                        | Descricao                    |
|--------|---------------------------------|------------------------------|
| GET    | /notifications                  | Lista paginada (limit/offset/unread_only) |
| GET    | /notifications/unread-count     | Contagem de nao lidas        |
| PATCH  | /notifications/{id}/read        | Marca uma como lida          |
| PATCH  | /notifications/read-all         | Marca todas como lidas       |

---

## Tipos de Notificacao (10 tipos)

| Tipo                           | Quando                               |
|--------------------------------|--------------------------------------|
| behavioral_pattern_complete    | Padroes comportamentais prontos      |
| behavioral_pattern_failed      | Padroes comportamentais falharam     |
| deep_dive_complete             | Deep dive pronto                     |
| deep_dive_failed               | Deep dive falhou                     |
| pattern_analysis_complete      | Padroes cross-topic prontos          |
| pattern_analysis_failed        | Padroes cross-topic falharam         |
| keyword_analysis_complete      | Keywords prontas                     |
| keyword_analysis_failed        | Keywords falharam                    |
| topic_analysis_complete        | Topicos prontos                      |
| topic_analysis_failed          | Topicos falharam                     |

---

## Integracao nos Use Cases

Os 5 use cases de deteccao/extracao foram modificados para publicar notificacoes apos `mark_ready()` (sucesso) e `mark_failed()` (falha):

1. `DetectBehavioralPatternsUseCase` — com topic_id e topic_name
2. `ExtractDeepDiveUseCase` — com topic_id e topic_name
3. `DetectPatternsUseCase` — nivel de audience (sem topic_id)
4. `ExtractKeywordsUseCase` — nivel de audience (sem topic_id)
5. `ExtractTopicsUseCase` — nivel de audience (sem topic_id)

Todos usam `audience.user_id` (ja disponivel no fluxo) para identificar o destinatario da notificacao.

---

## Migration

`9e2a609b8ef4_add_notifications_table` — cria tabela `notifications` com indices.
