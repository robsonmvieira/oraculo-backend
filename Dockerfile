FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

# Configura venv fora do /app para evitar conflito com volume
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

EXPOSE 8000

# Mantém o container vivo sem executar nada
# A aplicação é iniciada manualmente via make dev
CMD ["tail", "-f", "/dev/null"]
