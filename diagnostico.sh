#!/bin/bash
# Script de diagnóstico para conexão PostgreSQL
# Execute este script NA SUA MÁQUINA LOCAL (não no container)

echo "🔍 DIAGNÓSTICO DE CONEXÃO POSTGRESQL"
echo "===================================="
echo ""

echo "📦 1. Verificando containers rodando..."
echo "----------------------------------------"
if ! command -v docker &> /dev/null; then
    echo "❌ Docker não encontrado! Instale o Docker primeiro."
    exit 1
fi

CONTAINERS=$(docker ps --format "{{.Names}}" | grep crm)
if [ -z "$CONTAINERS" ]; then
    echo "❌ PROBLEMA: Nenhum container CRM está rodando!"
    echo ""
    echo "📝 SOLUÇÃO:"
    echo "   cd $(pwd)"
    echo "   docker-compose -f .devcontainer/docker-compose.yaml up -d"
    exit 1
else
    echo "✅ Containers rodando:"
    docker ps --filter name=crm --format "   - {{.Names}} ({{.Status}})"
fi
echo ""

echo "🔌 2. Verificando porta 5432 exposta..."
echo "----------------------------------------"
PORT_MAPPING=$(docker port crm-db 5432 2>/dev/null)
if [ -z "$PORT_MAPPING" ]; then
    echo "❌ PROBLEMA: Porta 5432 NÃO está exposta!"
    echo ""
    echo "📝 SOLUÇÃO:"
    echo "   1. Pare os containers atuais:"
    echo "      docker-compose down"
    echo ""
    echo "   2. Inicie com o docker-compose CORRETO:"
    echo "      docker-compose -f .devcontainer/docker-compose.yaml up -d"
    echo ""
    echo "   ⚠️  Você pode estar usando o docker-compose.yaml da raiz,"
    echo "      que NÃO expõe a porta do banco!"
    exit 1
else
    echo "✅ Porta exposta: $PORT_MAPPING"
fi
echo ""

echo "🏥 3. Verificando saúde do container..."
echo "----------------------------------------"
HEALTH=$(docker inspect crm-db --format='{{.State.Health.Status}}' 2>/dev/null)
if [ "$HEALTH" != "healthy" ]; then
    echo "⚠️  Container não está healthy: $HEALTH"
    echo "   Aguarde alguns segundos e tente novamente..."
else
    echo "✅ Container healthy"
fi
echo ""

echo "🔐 4. Testando conexão ao banco..."
echo "----------------------------------------"
if docker exec crm-db pg_isready -U postgres &>/dev/null; then
    echo "✅ PostgreSQL aceita conexões"
else
    echo "❌ PostgreSQL não aceita conexões"
    echo ""
    echo "📝 SOLUÇÃO: Reinicie o container do banco"
    echo "   docker restart crm-db"
    exit 1
fi
echo ""

echo "💾 5. Verificando banco de dados..."
echo "----------------------------------------"
DB_EXISTS=$(docker exec crm-db psql -U postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -w crmDatabase | wc -l)
if [ "$DB_EXISTS" -eq 0 ]; then
    echo "❌ PROBLEMA: Banco 'crmDatabase' não existe!"
    echo ""
    echo "📝 SOLUÇÃO: Criar o banco"
    echo '   docker exec crm-db psql -U postgres -c "CREATE DATABASE \"crmDatabase\";"'
    exit 1
else
    echo "✅ Banco 'crmDatabase' existe"
fi
echo ""

echo "🌐 6. Testando conectividade da máquina local..."
echo "----------------------------------------"
# Verificar se netcat está disponível
if command -v nc &> /dev/null; then
    if nc -zv localhost 5432 2>&1 | grep -q succeeded; then
        echo "✅ Porta 5432 acessível em localhost"
    else
        echo "❌ PROBLEMA: Porta 5432 não acessível!"
        echo ""
        echo "📝 Possíveis causas:"
        echo "   - Firewall bloqueando"
        echo "   - Porta já em uso por outro serviço"
        echo ""
        echo "   Verificar porta em uso:"
        echo "   - Windows: netstat -ano | findstr :5432"
        echo "   - Mac/Linux: lsof -i :5432"
    fi
elif command -v telnet &> /dev/null; then
    timeout 2 telnet localhost 5432 &>/dev/null && echo "✅ Porta 5432 acessível" || echo "⚠️  Não consegui verificar (instale netcat)"
else
    echo "⚠️  Não consegui verificar (instale netcat ou telnet)"
fi
echo ""

echo "🧪 7. Teste de conexão completo..."
echo "----------------------------------------"
if docker exec crm-db psql -U postgres -d crmDatabase -c "SELECT version();" &>/dev/null; then
    VERSION=$(docker exec crm-db psql -U postgres -d crmDatabase -tc "SELECT version();" 2>/dev/null)
    echo "✅ Conexão bem-sucedida!"
    echo "   PostgreSQL: $(echo $VERSION | cut -d',' -f1)"
else
    echo "❌ Falha ao conectar"
fi
echo ""

echo "📋 RESUMO PARA DATAGRIP"
echo "----------------------------------------"
echo "Host:     localhost"
echo "Port:     5432"
echo "Database: crmDatabase"
echo "User:     postgres"
echo "Password: postgres"
echo ""

echo "✅ TUDO OK! Tente conectar novamente no DataGrip."
echo ""
echo "💡 DICA: Se ainda não funcionar, tente:"
echo "   1. Reiniciar Docker Desktop"
echo "   2. Desabilitar firewall temporariamente"
echo "   3. Usar IP 127.0.0.1 ao invés de localhost"
