@echo off
echo Activando entorno virtual...
call venv\Scripts\activate

echo Verificando puerto 8001...
netstat -ano | findstr ":8001"
if %errorlevel% equ 0 (
    echo El puerto 8001 está en uso. Matando proceso...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001"') do taskkill /f /pid %%a
)

echo Iniciando microservicio FastAPI...
start uvicorn app.main:app --port 8001

echo Esperando 10 segundos para que la API esté lista...
timeout /t 10 /nobreak >nul

echo Levantando Prometheus y Grafana...
cd observabilidad
docker compose down -v
docker compose up -d

echo -------------------------------------
echo API:        http://localhost:8001/docs
echo Métricas:   http://localhost:8001/metrics
echo Prometheus: http://localhost:9090
echo Grafana:    http://localhost:3001