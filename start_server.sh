#!/usr/bin/env bash

set -e

# Script de inicializacao local do Rede Vítima

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"
PORT="${PORT:-8000}"

echo "=== Rede Vítima - Servidor de Acidentes ==="
echo "Diretorio do projeto: $ROOT_DIR"

cd "$ROOT_DIR"

if [ ! -x "$VENV_PY" ]; then
    echo "Ambiente virtual nao encontrado em .venv."
    echo "Crie com: python3 -m venv .venv"
    exit 1
fi

# Garante dependencias minimas antes de iniciar
if ! "$VENV_PY" -c "import flask" 2>/dev/null; then
    echo "Instalando dependencias do requirements.txt..."
    "$VENV_PY" -m pip install -r requirements.txt
fi

# Obter IP local da maquina (Linux/macOS)
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -z "$LOCAL_IP" ] && command -v ipconfig >/dev/null 2>&1; then
    LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
fi
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="localhost"
fi

echo "Servidor acessivel em:"
echo "  - Local: http://localhost:$PORT"
echo "  - Rede:  http://$LOCAL_IP:$PORT"
echo ""
echo "Comando utilizado: $VENV_PY server.py"
echo "Pressione Ctrl+C para parar."
echo ""

exec "$VENV_PY" server.py