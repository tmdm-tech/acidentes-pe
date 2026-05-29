#!/usr/bin/env python3
"""
SISTEMA DE RESGATE TEMPORÁRIO - VERIFICADOR
============================================

Este script verifica se o sistema de resgate está funcionando
e monitora os registros chegando em tempo real.

Uso:
  python3 verify_rescue_system.py
"""

import os
import json
from pathlib import Path
from datetime import datetime

def check_rescue_system():
    """Verifica status do sistema de resgate"""
    
    rescue_dir = Path('./resgate_temporario')
    today = datetime.now().strftime('%Y-%m-%d')
    today_dir = rescue_dir / today
    
    print("="*60)
    print("🔍 VERIFICAÇÃO DO SISTEMA DE RESGATE TEMPORÁRIO")
    print("="*60)
    print()
    
    # 1. Verificar estrutura
    print("1️⃣  ESTRUTURA DE PASTAS")
    print("-" * 60)
    
    if rescue_dir.exists():
        print(f"✅ Pasta base existe: {rescue_dir.absolute()}")
    else:
        print(f"❌ Pasta base NÃO encontrada: {rescue_dir.absolute()}")
        return
    
    if today_dir.exists():
        print(f"✅ Pasta de hoje existe: {today_dir}")
    else:
        print(f"⚠️  Pasta de hoje ainda não criada: {today_dir}")
        print("   (será criada no primeiro registro)")
    
    print()
    
    # 2. Verificar arquivos JSONL
    print("2️⃣  REGISTROS NO JSONL")
    print("-" * 60)
    
    if today_dir.exists():
        jsonl_path = today_dir / 'incoming_jsonl' / 'accidents_incoming.jsonl'
        
        if jsonl_path.exists():
            with open(jsonl_path, 'r') as f:
                lines = f.readlines()
            print(f"✅ Arquivo JSONL encontrado: {jsonl_path.name}")
            print(f"📊 Total de registros hoje: {len(lines)}")
            
            if lines:
                # Mostrar últimos registros
                print("\n📋 Últimos 3 registros:")
                for idx, line in enumerate(lines[-3:], 1):
                    try:
                        record = json.loads(line)
                        print(f"   {idx}. ID: {record.get('id', 'N/A')} | "
                              f"Município: {record.get('municipioNotificacao', 'N/A')}")
                    except:
                        pass
        else:
            print(f"⏳ Nenhum registro JSONL ainda (esperando primeiro registro)")
    
    print()
    
    # 3. Verificar outros subdiretórios
    print("3️⃣  OUTRAS INFORMAÇÕES")
    print("-" * 60)
    
    if today_dir.exists():
        subdir_check = [
            ('incoming_jsonl', 'Registros JSONL'),
            ('soltos', 'Dados soltos'),
            ('exports_snapshot', 'Snapshots de exportação')
        ]
        
        for subdir, desc in subdir_check:
            path = today_dir / subdir
            if path.exists():
                print(f"✅ {desc}: {subdir}")
            else:
                print(f"❌ {desc}: {subdir} (não encontrado)")
    
    print()
    print("="*60)
    print("📌 INSTRUÇÕES")
    print("="*60)
    print("""
1. O sistema agora salva AUTOMATICAMENTE cada registro que chega
2. Pasta: ./resgate_temporario/{DATA}/incoming_jsonl/accidents_incoming.jsonl
3. Cada linha é um registro JSON válido
4. Execute este script para monitorar

Para rastrear registros em tempo real:
  tail -f ./resgate_temporario/$(date +%Y-%m-%d)/incoming_jsonl/accidents_incoming.jsonl

Para contar registros do dia:
  wc -l ./resgate_temporario/$(date +%Y-%m-%d)/incoming_jsonl/accidents_incoming.jsonl
""")
    print("="*60)

if __name__ == '__main__':
    check_rescue_system()
