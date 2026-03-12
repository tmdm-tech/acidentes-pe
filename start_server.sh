#!/bin/bash

# Script para iniciar o servidor do ObservaTrânsito
# Este script configura o servidor Flask para aceitar conexões externas

echo "=== ObservaTrânsito - Servidor de Acidentes ==="
echo "Iniciando servidor Flask..."

# Navegar para o diretório do projeto
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Verificar se o Flask está instalado
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Instalando Flask..."
    pip3 install flask
fi

# Obter o IP local da máquina
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}')

if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="localhost"
fi

echo "Servidor será acessível em:"
echo "  - Local: http://localhost:8000"
echo "  - Rede:  http://$LOCAL_IP:8000"
echo ""
echo "Para instalar como app no celular:"
echo "1. Abra o navegador no celular"
echo "2. Acesse http://$LOCAL_IP:8000"
echo "3. Toque em 'Adicionar à tela inicial' ou 'Instalar app'"
echo ""

# Iniciar o servidor
python3 server.py