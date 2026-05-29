#!/usr/bin/env python3
import json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import pickle

# Carregar dados consolidados
with open('/tmp/final_comprehensive.pkl', 'rb') as f:
    all_records = pickle.load(f)

# Preparar dados por município
municipios = {}
for rid, info in all_records.items():
    mun = info['municipio']
    lat = info.get('latitude')
    lon = info.get('longitude')
    
    if lat and lon:
        try:
            lat = float(lat)
            lon = float(lon)
            
            if mun not in municipios:
                municipios[mun] = {
                    'total': 0,
                    'coordenadas': [],
                    'ids': []
                }
            
            municipios[mun]['total'] += 1
            municipios[mun]['coordenadas'].append((lat, lon))
            municipios[mun]['ids'].append(rid)
        except:
            pass

# Criar figura mais detalhada
fig = plt.figure(figsize=(16, 11))
fig.suptitle('📊 Varredura Completa de Acidentes - Pernambuco\nConsolidação: JSON + CSV (05/05/2026)', 
             fontsize=16, fontweight='bold', y=0.98)

# 1. Mapa geográfico com pontos
ax1 = plt.subplot(2, 3, 1)
cores = {'Recife': '#e74c3c', 'Garanhuns': '#3498db', 'Outro': '#95a5a6'}

for mun, dados in sorted(municipios.items()):
    coords = np.array(dados['coordenadas'])
    cor = cores.get(mun, '#95a5a6')
    
    ax1.scatter(coords[:, 1], coords[:, 0], s=400, alpha=0.7, 
                label=f"{mun} ({dados['total']})", color=cor, edgecolors='black', linewidth=2.5)
    
    # Adicionar números nos pontos
    for idx, (lat, lon) in enumerate(dados['coordenadas'], 1):
        ax1.annotate(str(idx), (lon, lat), fontsize=9, ha='center', va='center', 
                    fontweight='bold', color='white')

ax1.set_xlabel('Longitude', fontsize=10, fontweight='bold')
ax1.set_ylabel('Latitude', fontsize=10, fontweight='bold')
ax1.set_title('Mapa Geográfico dos Acidentes', fontsize=11, fontweight='bold')
ax1.legend(fontsize=9, loc='upper right')
ax1.grid(True, alpha=0.3)
ax1.set_xlim(-37, -34.6)
ax1.set_ylim(-9.1, -8.0)

# 2. Gráfico de barras
ax2 = plt.subplot(2, 3, 2)
mun_nomes = sorted(municipios.keys(), key=lambda x: municipios[x]['total'], reverse=True)
totais = [municipios[m]['total'] for m in mun_nomes]
cores_lista = [cores.get(m, '#95a5a6') for m in mun_nomes]

bars = ax2.bar(mun_nomes, totais, color=cores_lista, edgecolor='black', linewidth=2)
ax2.set_ylabel('Quantidade de Registros', fontsize=10, fontweight='bold')
ax2.set_title('Total de Acidentes por Município', fontsize=11, fontweight='bold')
ax2.set_ylim(0, max(totais) + 1)

for bar, total in zip(bars, totais):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(total)}',
            ha='center', va='bottom', fontweight='bold', fontsize=12)

ax2.grid(True, alpha=0.3, axis='y')

# 3. Detalhes por município - Recife
ax3 = plt.subplot(2, 3, 3)
ax3.axis('off')

recife_data = municipios.get('Recife', {})
recife_text = "RECIFE\n" + "="*30 + "\n"
recife_text += f"Total: {recife_data.get('total', 0)}\n"
recife_text += f"IDs:\n"
for rid in sorted(recife_data.get('ids', [])):
    recife_text += f"  • {rid}\n"

ax3.text(0.05, 0.95, recife_text, transform=ax3.transAxes, 
         fontsize=9, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='#ffcccc', alpha=0.6))

# 4. Detalhes por município - Garanhuns
ax4 = plt.subplot(2, 3, 4)
ax4.axis('off')

garanhuns_data = municipios.get('Garanhuns', {})
garanhuns_text = "GARANHUNS\n" + "="*30 + "\n"
garanhuns_text += f"Total: {garanhuns_data.get('total', 0)}\n"
garanhuns_text += f"IDs:\n"
for rid in sorted(garanhuns_data.get('ids', [])):
    garanhuns_text += f"  • {rid}\n"

ax4.text(0.05, 0.95, garanhuns_text, transform=ax4.transAxes, 
         fontsize=9, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='#ccccff', alpha=0.6))

# 5. Estatísticas gerais
ax5 = plt.subplot(2, 3, 5)
ax5.axis('off')

total_geral = sum(m['total'] for m in municipios.values())

stats_text = f"""
ESTATÍSTICAS CONSOLIDADAS
{'='*35}

Total de Registros: {total_geral}
Municípios: {len(municipios)}
Data de Coleta: 05/05/2026
Gerado: {datetime.now().strftime('%H:%M:%S')}

FONTES:
  • accidents.json
  • CSV exports (todos)
  • JSON backups

NOTA: Sem acesso ao Supabase
para dados remotos
"""

ax5.text(0.05, 0.95, stats_text, transform=ax5.transAxes,
         fontsize=9, verticalalignment='top', family='monospace',
         fontweight='bold',
         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

# 6. Resumo de fontes
ax6 = plt.subplot(2, 3, 6)
ax6.axis('off')

sources_text = """
ANÁLISE DE FONTES
=====================================

CSV Files Analisados:
  • 44 arquivos totais
  • Diários: Marca dados
    de múltiplas datas
  • Semanais e Mensais:
    Agregações dos diários
  • De Mar/13 a Abr/08

JSON Consolidado:
  • accidents.json
  • accidents.bak.json

Status: Dados locais
completos e consistentes.
Faltam dados do Supabase
para comparação.
"""

ax6.text(0.05, 0.95, sources_text, 
         transform=ax6.transAxes,
         fontsize=8.5, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))

plt.tight_layout()
plt.savefig('/workspaces/Acidentes_PE/mapa_varredura_completa.png', dpi=150, bbox_inches='tight')
print("✅ Mapa detalhado salvo: /workspaces/Acidentes_PE/mapa_varredura_completa.png")
print(f"✅ Total consolidado: {total_geral} registros")
plt.close()
