@echo off
REM Script de diagnóstico para Windows
REM Execute este script NA SUA MÁQUINA LOCAL (não no container)

echo ============================================
echo    DIAGNOSTICO DE CONEXAO POSTGRESQL
echo ============================================
echo.

echo [1/7] Verificando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [X] Docker nao encontrado! Instale o Docker Desktop.
    pause
    exit /b 1
)
echo [OK] Docker instalado
echo.

echo [2/7] Verificando containers rodando...
docker ps --filter name=crm --format "{{.Names}}" > temp_containers.txt
findstr /C:"crm" temp_containers.txt >nul
if errorlevel 1 (
    echo [X] PROBLEMA: Nenhum container CRM esta rodando!
    echo.
    echo SOLUCAO:
    echo    cd %CD%
    echo    docker-compose -f .devcontainer/docker-compose.yaml up -d
    del temp_containers.txt
    pause
    exit /b 1
)
echo [OK] Containers rodando:
docker ps --filter name=crm --format "   - {{.Names}} ({{.Status}})"
del temp_containers.txt
echo.

echo [3/7] Verificando porta 5432 exposta...
docker port crm-db 5432 > temp_port.txt 2>&1
findstr /C:"5432" temp_port.txt >nul
if errorlevel 1 (
    echo [X] PROBLEMA: Porta 5432 NAO esta exposta!
    echo.
    echo SOLUCAO:
    echo    1. Pare os containers:
    echo       docker-compose down
    echo.
    echo    2. Inicie com o docker-compose CORRETO:
    echo       docker-compose -f .devcontainer/docker-compose.yaml up -d
    del temp_port.txt
    pause
    exit /b 1
)
echo [OK] Porta exposta:
type temp_port.txt
del temp_port.txt
echo.

echo [4/7] Verificando saude do container...
docker exec crm-db pg_isready -U postgres >nul 2>&1
if errorlevel 1 (
    echo [X] PostgreSQL nao aceita conexoes
    echo.
    echo SOLUCAO: Reinicie o container
    echo    docker restart crm-db
    pause
    exit /b 1
)
echo [OK] PostgreSQL aceita conexoes
echo.

echo [5/7] Verificando banco de dados...
docker exec crm-db psql -U postgres -lqt 2>nul | findstr /C:"crmDatabase" >nul
if errorlevel 1 (
    echo [X] PROBLEMA: Banco 'crmDatabase' nao existe!
    echo.
    echo SOLUCAO:
    echo    docker exec crm-db psql -U postgres -c "CREATE DATABASE \"crmDatabase\";"
    pause
    exit /b 1
)
echo [OK] Banco 'crmDatabase' existe
echo.

echo [6/7] Verificando porta 5432 em uso...
netstat -ano | findstr :5432 > temp_netstat.txt
if errorlevel 1 (
    echo [!] Porta 5432 nao esta em uso (pode ser problema)
) else (
    echo [OK] Porta 5432 em uso:
    type temp_netstat.txt
)
del temp_netstat.txt 2>nul
echo.

echo [7/7] Teste de conexao completo...
docker exec crm-db psql -U postgres -d crmDatabase -c "SELECT version();" >nul 2>&1
if errorlevel 1 (
    echo [X] Falha ao conectar
    pause
    exit /b 1
)
echo [OK] Conexao bem-sucedida!
docker exec crm-db psql -U postgres -d crmDatabase -tc "SELECT version();"
echo.

echo ============================================
echo         CONFIGURACAO PARA DATAGRIP
echo ============================================
echo Host:     localhost
echo Port:     5432
echo Database: crmDatabase
echo User:     postgres
echo Password: postgres
echo.
echo [OK] TUDO OK! Tente conectar novamente no DataGrip.
echo.
echo DICA: Se ainda nao funcionar, tente:
echo   1. Reiniciar Docker Desktop
echo   2. Desabilitar firewall temporariamente
echo   3. Usar IP 127.0.0.1 ao inves de localhost
echo.
pause
