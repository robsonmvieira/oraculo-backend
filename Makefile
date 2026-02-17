.PHONY: help install dev run test clean docker-up docker-down docker-shell docker-logs docker-rebuild docker-dev

# Variáveis
CONTAINER_NAME = crm-app
PYTHON = uv run
ALEMBIC = $(PYTHON) alembic

# Comando padrão
help:
	@echo "Comandos disponíveis:"
	@echo ""
	@echo "Docker (desenvolvimento):"
	@echo "  make docker-up        - Sobe os containers (app + db)"
	@echo "  make docker-down      - Para os containers"
	@echo "  make docker-shell     - Acessa o shell do container"
	@echo "  make docker-logs      - Mostra logs do container app"
	@echo "  make docker-rebuild   - Reconstroi os containers"
	@echo "  make docker-dev       - Inicia servidor de dev no container"
	@echo "  make docker-install   - Instala dependencias no container"
	@echo ""
	@echo "Local:"
	@echo "  make install          - Instala as dependências do projeto"
	@echo "  make dev              - Instala dependências de desenvolvimento"
	@echo "  make run              - Executa a aplicação"
	@echo ""
	@echo "Migrations (Alembic):"
	@echo "  make migration MSG='mensagem'  - Cria uma nova migration"
	@echo "  make migrate          - Aplica todas as migrations pendentes"
	@echo "  make migrate-down     - Reverte a última migration"
	@echo "  make migrate-status   - Mostra o status atual das migrations"
	@echo "  make migrate-history  - Mostra o histórico de migrations"
	@echo "  make migrate-pending  - Verifica se há migrations pendentes"
	@echo "  make migrate-reset    - Reverte todas as migrations (CUIDADO!)"
	@echo ""
	@echo "Banco de Dados:"
	@echo "  make db-upgrade       - Alias para 'make migrate'"
	@echo "  make db-downgrade     - Alias para 'make migrate-down'"
	@echo "  make db-reset         - Reseta o banco (downgrade + upgrade)"
	@echo ""
	@echo "Linting e Formatação:"
	@echo "  make lint             - Executa o linter (ruff)"
	@echo "  make format           - Formata o código (ruff)"
	@echo ""
	@echo "Limpeza:"
	@echo "  make clean            - Remove arquivos temporários e cache"

# =============================================================================
# DOCKER
# =============================================================================

docker-up:
	@echo "🐳 Subindo containers..."
	docker compose up -d
	@echo "✅ Containers iniciados!"
	@echo "💡 Use 'make docker-install' para instalar dependencias"
	@echo "💡 Use 'make docker-dev' para iniciar o servidor"

docker-down:
	@echo "🛑 Parando containers..."
	docker compose down
	@echo "✅ Containers parados!"

docker-shell:
	@echo "🐚 Acessando shell do container..."
	docker exec -it $(CONTAINER_NAME) bash

docker-logs:
	docker compose logs -f app

docker-rebuild:
	@echo "🔄 Reconstruindo containers..."
	docker compose down
	docker compose build --no-cache
	docker compose up -d
	@echo "✅ Containers reconstruidos!"

docker-install:
	@echo "📦 Instalando dependencias no container..."
	docker exec -it $(CONTAINER_NAME) uv sync
	@echo "✅ Dependencias instaladas!"

docker-add:
	@if [ -z "$(PKG)" ]; then \
		echo "❌ Erro: Especifique o pacote com PKG='nome-do-pacote'"; \
		echo "   Exemplo: make docker-add PKG=requests"; \
		exit 1; \
	fi
	@echo "📦 Adicionando pacote $(PKG)..."
	docker exec -it $(CONTAINER_NAME) uv add $(PKG)
	@echo "✅ Pacote $(PKG) adicionado!"

docker-dev:
	@echo "🚀 Iniciando servidor de desenvolvimento..."
	docker exec -it $(CONTAINER_NAME) uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-test:
	@echo "🧪 Rodando testes no container..."
	docker exec -it $(CONTAINER_NAME) uv run pytest

docker-migrate:
	@echo "🔄 Rodando migrations no container..."
	docker exec -it $(CONTAINER_NAME) uv run alembic upgrade head

# =============================================================================
# LOCAL
# =============================================================================

# Instalação
install:
	@echo "📦 Instalando dependências..."
	uv sync

dev:
	@echo "📦 Instalando dependências de desenvolvimento..."
	uv sync --dev

# Execução
run:
	@echo "🚀 Executando aplicação..."
	$(PYTHON) main.py

# Migrations
migration:
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Erro: Especifique uma mensagem com MSG='sua mensagem'"; \
		echo "   Exemplo: make migration MSG='adiciona campo email'"; \
		exit 1; \
	fi
	@echo "📝 Criando nova migration: $(MSG)"
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate:
	@echo "🔄 Aplicando migrations pendentes..."
	$(ALEMBIC) upgrade head
	@echo "✅ Migrations aplicadas com sucesso!"

migrate-down:
	@echo "⏪ Revertendo última migration..."
	$(ALEMBIC) downgrade -1
	@echo "✅ Migration revertida!"

migrate-status:
	@echo "📊 Status atual das migrations:"
	@$(ALEMBIC) current

migrate-history:
	@echo "📜 Histórico de migrations:"
	@$(ALEMBIC) history --verbose

migrate-pending:
	@echo "🔍 Verificando migrations pendentes..."
	@current=$$($(ALEMBIC) current 2>/dev/null | grep -oP '(?<=\(head\))|(?<=^[a-f0-9]{12})' | head -1); \
	head=$$($(ALEMBIC) heads 2>/dev/null | grep -oP '^[a-f0-9]{12}' | head -1); \
	if [ -z "$$current" ]; then \
		echo "⚠️  Nenhuma migration aplicada ainda"; \
		echo "💡 Execute 'make migrate' para aplicar as migrations"; \
	elif [ "$$current" = "$$head" ]; then \
		echo "✅ Banco de dados está atualizado!"; \
	else \
		echo "⚠️  Existem migrations pendentes!"; \
		echo "💡 Execute 'make migrate' para aplicar"; \
		echo ""; \
		echo "Migration atual: $$current"; \
		echo "Última migration: $$head"; \
	fi

migrate-reset:
	@echo "⚠️  ATENÇÃO: Isso irá reverter TODAS as migrations!"
	@echo "Pressione Ctrl+C para cancelar ou Enter para continuar..."
	@read confirm
	@echo "⏪ Revertendo todas as migrations..."
	$(ALEMBIC) downgrade base
	@echo "✅ Todas as migrations foram revertidas!"

# Aliases para banco de dados
db-upgrade: migrate

db-downgrade: migrate-down

db-reset:
	@echo "🔄 Resetando banco de dados (downgrade + upgrade)..."
	$(ALEMBIC) downgrade base
	$(ALEMBIC) upgrade head
	@echo "✅ Banco de dados resetado!"

# Linting e Formatação
lint:
	@echo "🔍 Executando linter..."
	$(PYTHON) ruff check .

format:
	@echo "✨ Formatando código..."
	$(PYTHON) ruff check --fix .
	$(PYTHON) ruff format .

# Limpeza
clean:
	@echo "🧹 Limpando arquivos temporários..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Limpeza concluída!"
