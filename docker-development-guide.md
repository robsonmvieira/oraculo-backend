# Guia: Docker Development sem DevContainer Travado

Este guia mostra como configurar um projeto Python para rodar via linha de comando (como este projeto NestJS), evitando o problema do Cursor/VSCode travar ao usar DevContainer.

## O Problema

O DevContainer do VSCode/Cursor:
- Abre o editor DENTRO do container
- Pode travar esperando o container ficar "ready"
- Conflitos com extensões e configurações
- Lento para inicializar

## A Solução: Docker Compose + Script Shell

Em vez de usar DevContainer, você:
1. Sobe os containers via `docker-compose up -d`
2. Executa comandos via `docker exec`
3. Edita os arquivos localmente (volume montado)

---

## DE-PARA: NestJS vs Python

### 1. Dockerfile

**NestJS (este projeto):**
```dockerfile
FROM node:22

RUN npm install -g @nestjs/cli@11

USER node

WORKDIR /home/node/app

CMD [ "tail", "-f", "/dev/null" ]
```

**Python (equivalente):**
```dockerfile
FROM python:3.12-slim

# Instalar dependências do sistema (se necessário)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root (boa prática)
RUN useradd -m -s /bin/bash appuser

USER appuser

WORKDIR /home/appuser/app

# IMPORTANTE: tail -f mantém o container rodando sem executar nada
# Isso permite que você execute comandos manualmente depois
CMD [ "tail", "-f", "/dev/null" ]
```

> **PONTO CHAVE:** O `CMD [ "tail", "-f", "/dev/null" ]` mantém o container vivo sem executar a aplicação. Você inicia a aplicação manualmente depois.

---

### 2. docker-compose.yml

**NestJS (este projeto):**
```yaml
services:
  app:
    build: .
    ports:
      - "4001:3000"
    volumes:
      - .:/home/node/app        # Monta código local no container
    container_name: magico-backend
    restart: always
    env_file:
      - .env.local
    depends_on:
      - db
      - redis
```

**Python (equivalente):**
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"             # FastAPI/Flask porta
    volumes:
      - .:/home/appuser/app     # Monta código local no container
    container_name: meu-backend-python
    restart: always
    env_file:
      - .env.local
    depends_on:
      - db
      - redis
    # NÃO coloque command: aqui! Deixe o Dockerfile definir

  db:
    image: postgres:16
    container_name: meu-postgres
    restart: always
    ports:
      - "5432:5432"
    volumes:
      - .postgres_data:/var/lib/postgresql/data/
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}

  redis:
    image: redis:7-alpine
    container_name: meu-redis
    restart: always
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

---

### 3. dev.sh (Script de Desenvolvimento)

**NestJS (este projeto):**
```bash
./dev.sh start   # Sobe containers + npm install
./dev.sh shell   # Acessa bash do container
./dev.sh dev     # Roda npm run start:dev
```

**Python (crie este arquivo):**
```bash
#!/bin/bash

# dev.sh - Script para facilitar desenvolvimento no Docker

CONTAINER_NAME="meu-backend-python"

case "$1" in
  start)
    echo "Iniciando containers..."
    docker-compose up -d
    echo "Containers iniciados!"
    echo "Instalando dependencias..."
    docker exec -it $CONTAINER_NAME pip install -r requirements.txt
    echo "Pronto! Use: ./dev.sh shell"
    ;;

  stop)
    echo "Parando containers..."
    docker-compose down
    ;;

  shell)
    echo "Acessando shell do container..."
    docker exec -it $CONTAINER_NAME bash
    ;;

  logs)
    docker-compose logs -f app
    ;;

  rebuild)
    echo "Reconstruindo containers..."
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    docker exec -it $CONTAINER_NAME pip install -r requirements.txt
    ;;

  install)
    echo "Instalando dependencias..."
    docker exec -it $CONTAINER_NAME pip install -r requirements.txt
    ;;

  dev)
    echo "Iniciando servidor de desenvolvimento..."
    # Para FastAPI:
    docker exec -it $CONTAINER_NAME uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    # Para Flask:
    # docker exec -it $CONTAINER_NAME flask run --host 0.0.0.0 --port 8000 --reload
    # Para Django:
    # docker exec -it $CONTAINER_NAME python manage.py runserver 0.0.0.0:8000
    ;;

  test)
    echo "Rodando testes..."
    docker exec -it $CONTAINER_NAME pytest
    ;;

  migrate)
    echo "Rodando migrations..."
    # Para Alembic:
    docker exec -it $CONTAINER_NAME alembic upgrade head
    # Para Django:
    # docker exec -it $CONTAINER_NAME python manage.py migrate
    ;;

  *)
    echo "Comandos disponiveis:"
    echo ""
    echo "  ./dev.sh start    - Inicia containers e instala deps"
    echo "  ./dev.sh stop     - Para os containers"
    echo "  ./dev.sh shell    - Acessa bash do container"
    echo "  ./dev.sh logs     - Mostra logs do container"
    echo "  ./dev.sh rebuild  - Reconstroi containers do zero"
    echo "  ./dev.sh install  - Instala/atualiza dependencias"
    echo "  ./dev.sh dev      - Inicia servidor de desenvolvimento"
    echo "  ./dev.sh test     - Roda testes"
    echo "  ./dev.sh migrate  - Roda migrations"
    echo ""
    ;;
esac
```

**Torne executavel:**
```bash
chmod +x dev.sh
```

---

### 4. Estrutura de Arquivos

```
meu-projeto-python/
├── Dockerfile
├── docker-compose.yml
├── dev.sh                    # Script de desenvolvimento
├── .env.local                # Variaveis de ambiente
├── .env.example              # Template das variaveis
├── requirements.txt          # Dependencias Python
├── .gitignore
├── .postgres_data/           # Volume do Postgres (ignorar no git)
├── src/
│   ├── main.py
│   └── ...
└── tests/
    └── ...
```

---

## Fluxo de Trabalho

### Primeira vez:
```bash
# 1. Clone o projeto
git clone <repo>
cd meu-projeto

# 2. Configure o ambiente
cp .env.example .env.local

# 3. Inicie tudo
./dev.sh start

# 4. Inicie o servidor de desenvolvimento
./dev.sh dev
```

### Dia a dia:
```bash
# Subir containers (se nao estiverem rodando)
./dev.sh start

# Iniciar servidor de dev (em um terminal)
./dev.sh dev

# Em outro terminal, acessar shell para comandos
./dev.sh shell
```

### Parar tudo:
```bash
./dev.sh stop
```

---

## Dicas Importantes

### 1. Hot Reload Funciona
Como o volume monta o codigo local no container, qualquer alteracao no seu editor (Cursor/VSCode) e refletida imediatamente. O `--reload` do uvicorn/flask detecta as mudancas.

### 2. Extensoes do VSCode/Cursor
Configure o Python interpreter para o sistema local OU use a extensao "Remote - Containers" apenas quando necessario (nao como padrao).

### 3. .gitignore
Adicione:
```gitignore
.postgres_data/
.env.local
__pycache__/
*.pyc
.pytest_cache/
```

### 4. requirements.txt no Container
Se adicionar novas dependencias:
```bash
./dev.sh install
# ou
docker exec -it meu-backend-python pip install nova-lib
docker exec -it meu-backend-python pip freeze > requirements.txt
```

### 5. Debugger
Para usar debugger, adicione ao docker-compose.yml:
```yaml
services:
  app:
    ports:
      - "8000:8000"
      - "5678:5678"  # Porta do debugpy
```

E no codigo Python:
```python
import debugpy
debugpy.listen(("0.0.0.0", 5678))
debugpy.wait_for_client()  # Opcional: pausa ate conectar
```

---

## Comparacao: DevContainer vs Docker Compose Manual

| Aspecto | DevContainer | Docker Compose + Script |
|---------|--------------|-------------------------|
| Onde o editor roda | Dentro do container | Na maquina local |
| Velocidade de inicio | Lento (pode travar) | Rapido |
| Hot reload | Sim | Sim (via volume) |
| Extensoes | Precisam ser instaladas no container | Funcionam normalmente |
| Controle | VSCode gerencia | Voce controla tudo |
| Git | Pode ter problemas | Funciona normal |
| Terminal | Integrado | `./dev.sh shell` |

---

## Troubleshooting

### Container nao sobe
```bash
docker-compose logs app
```

### Porta em uso
```bash
# Ver o que esta usando a porta
lsof -i :8000

# Ou mude a porta no docker-compose.yml
ports:
  - "8001:8000"
```

### Permissao de arquivos
Se arquivos criados no container ficarem com permissao errada:
```dockerfile
# No Dockerfile, use o mesmo UID do seu usuario
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appgroup && useradd -m -u $UID -g $GID appuser
```

### Container para de rodar
Verifique se o CMD esta correto:
```dockerfile
CMD [ "tail", "-f", "/dev/null" ]
```
Isso mantem o container vivo indefinidamente.
