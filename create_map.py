#!/usr/bin/env python3
import json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Ler dados
with open('/workspaces/Acidentes_PE/resgate_temporario/2026-05-05/soltos/accidents.json', 'r') as f:
    data = json.load(f)

# Preparar dados por município
municipios = {}
for record in data:
    mun = record.get('municipioNotificacao', 'Desconhecido')
    lat = float(record.get('latitude', 0) or 0)
    lon = float(record.get('longitude', 0) or 0)
    veiculo = record.get('veiculoUsuario', 'Desconhecido')
    
    if mun not in municipios:
        municipios[mun] = {
            'total': 0,
            'coordenadas': [],
            'veiculos': {},
            'vitimas': 0
        }
    
    municipios[mun]['total'] += 1
    municipios[mun]['coordenadas'].append((lat, lon))
    municipios[mun]['veiculos'][veiculo] = municipios[mun]['veiculos'].get(veiculo, 0) + 1
    
    if record.get('sinistroComVitimas') == 'Sim':
        try:
            municipios[mun]['vitimas'] += int(record.get('quantidadeVitimas', 0) or 0)
        except:
            pass

# Criar figura com múltiplas subplots
fig = plt.figure(figsize=(14, 10))
fig.suptitle('📍 Distribuição de Acidentes - Pernambuco (05/Mai/2026)', 
             fontsize=18, fontweight='bold', y=0.98)

# 1. Mapa com pontos de acidentes
ax1 = plt.subplot(2, 2, 1)
cores = {'Recife': '#e74c3c', 'Garanhuns': '#3498db'}

for mun, dados in municipios.items():
    coords = np.array(dados['coordenadas'])
    cor = cores.get(mun, '#95a5a6')
    ax1.scatter(coords[:, 1], coords[:, 0], s=300, alpha=0.7, 
                label=f"{mun} ({dados['total']})", color=cor, edgecolors='black', linewidth=2)
    
    # Adicionar números aos pontos
    for idx, (lat, lon) in enumerate(dados['coordenadas'], 1):
        ax1.annotate(str(idx), (lon, lat), fontsize=8, ha='center', va='center', 
                    fontweight='bold', color='white')

ax1.set_xlabel('Longitude', fontsize=11, fontweight='bold')
ax1.set_ylabel('Latitude', fontsize=11, fontweight='bold')
ax1.set_title('Localização dos Acidentes', fontsize=12, fontweight='bold')
ax1.legend(fontsize=10, loc='upper right')
ax1.grid(True, alpha=0.3)
ax1.set_xlim(-35.2, -34.7)
ax1.set_ylim(-9.0, -7.8)

# 2. Gráfico de barras - Total por município
ax2 = plt.subplot(2, 2, 2)
mun_nomes = list(municipios.keys())
totais = [municipios[m]['total'] for m in mun_nomes]
cores_lista = [cores.get(m, '#95a5a6') for m in mun_nomes]

bars = ax2.bar(mun_nomes, totais, color=cores_lista, edgecolor='black', linewidth=2)
ax2.set_ylabel('Quantidade de Registros', fontsize=11, fontweight='bold')
ax2.set_title('Total de Acidentes por Município', fontsize=12, fontweight='bold')
ax2.set_ylim(0, max(totais) + 2)

# Adicionar números nas barras
for bar, total in zip(bars, totais):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(total)}',
            ha='center', va='bottom', fontweight='bold', fontsize=12)

ax2.grid(True, alpha=0.3, axis='y')

# 3. Resumo de veículos
ax3 = plt.subplot(2, 2, 3)
ax3.axis('off')

resumo_text = "📊 RESUMO POR MUNICÍPIO\n" + "="*40 + "\n\n"

for mun in sorted(municipios.keys()):
    dados = municipios[mun]
    resumo_text += f"🚗 {mun.upper()}\n"
    resumo_text += f"   Registros: {dados['total']}\n"
    resumo_text += f"   Vítimas: {dados['vitimas']}\n"
    resumo_text += f"   Tipos de veículo:\n"
    for veiculo, qtd in sorted(dados['veiculos'].items(), key=lambda x: x[1], reverse=True):
        resumo_text += f"      • {veiculo}: {qtd}\n"
    resumo_text += "\n"

ax3.text(0.05, 0.95, resumo_text, transform=ax3.transAxes, 
         fontsize=10, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

# 4. Estatísticas gerais
ax4 = plt.subplot(2, 2, 4)
ax4.axis('off')

total_geral = sum(m['total'] for m in municipios.values())
total_vitimas = sum(m['vitimas'] for m in municipios.values())

stats_text = f"""
ESTATÍSTICAS GERAIS
{'='*30}

Total de Registros: {total_geral}
Total de Vítimas: {total_vitimas}
Municípios Afetados: {len(municipios)}

Data da Coleta: 05/05/2026
Gerado em: {datetime.now().strftime('%H:%M:%S')}
"""

ax4.text(0.05, 0.95, stats_text, transform=ax4.transAxes,
         fontsize=11, verticalalignment='top', family='monospace',
         fontweight='bold',
         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

plt.tight_layout()
plt.savefig('/workspaces/Acidentes_PE/mapa_distribuicao_acidentes.png', dpi=150, bbox_inches='tight')
print("✅ Mapa salvo: /workspaces/Acidentes_PE/mapa_distribuicao_acidentes.png")
print(f"✅ Total de registros: {total_geral}")
plt.close()
