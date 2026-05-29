#!/bin/bash
# Monitor em Tempo Real - Registros Chegando
# Uso: bash monitor_incoming.sh

TODAY=$(date +%Y-%m-%d)
RESCUE_DIR="./resgate_temporario/$TODAY"
JSONL_FILE="$RESCUE_DIR/incoming_jsonl/accidents_incoming.jsonl"

echo "📊 MONITOR EM TEMPO REAL - Acidentes Chegando"
echo "=============================================="
echo "Data: $TODAY"
echo "Arquivo: $JSONL_FILE"
echo ""
echo "⏳ Aguardando registros... (CTRL+C para parar)"
echo ""

# Se arquivo não existe, criar
mkdir -p "$RESCUE_DIR/incoming_jsonl" 2>/dev/null

# Usar tail -f para monitorar
# Mostrar com jq para formatar melhor
if command -v jq &> /dev/null; then
    echo "📋 Registros (com pretty-print):"
    echo ""
    tail -f "$JSONL_FILE" 2>/dev/null | while read line; do
        # Mostrar timestamp + contagem
        COUNT=$(wc -l < "$JSONL_FILE" 2>/dev/null || echo "?")
        echo "[$(date '+%H:%M:%S')] Registro #$COUNT:"
        echo "$line" | jq '.' 2>/dev/null || echo "$line"
        echo ""
    done
else
    echo "⚠️  jq não disponível, mostrando raw"
    echo ""
    tail -f "$JSONL_FILE" 2>/dev/null | while read line; do
        COUNT=$(wc -l < "$JSONL_FILE" 2>/dev/null || echo "?")
        echo "[$(date '+%H:%M:%S')] Registro #$COUNT: $line"
    done
fi
