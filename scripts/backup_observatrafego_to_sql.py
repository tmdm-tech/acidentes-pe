#!/usr/bin/env python3
"""Converte os registros do ObservaTrafego em um dump SQL diário."""
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

CONTAINER_KEYS = ('records', 'data', 'accidents', 'items', 'results', 'ocorrencias', 'acidentes')

def sql_value(value):
    if value is None or value == "": return "NULL"
    if isinstance(value, bool): return "TRUE" if value else "FALSE"
    return "'" + str(value).replace("'", "''") + "'"

def parse_datetime(raw):
    raw = str(raw or "").strip()
    if not raw: return None
    candidates=[raw, raw.replace('Z','+00:00')]
    for value in candidates:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(raw[:19], fmt)
        except ValueError: pass
    return None

def fetch_json(url):
    req = Request(url, headers={"User-Agent": "acidentes-pe-github-backup/1.1", "Accept": "application/json"})
    with urlopen(req, timeout=45) as response: return json.load(response)

def normalize(payload):
    if isinstance(payload, list): return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict): return []
    for key in CONTAINER_KEYS:
        value=payload.get(key)
        if isinstance(value,list): return [r for r in value if isinstance(r,dict)]
        if isinstance(value,dict):
            nested=normalize(value)
            if nested: return nested
    if any(k in payload for k in ('id','municipioNotificacao','dataHora','endereco')): return [payload]
    return []

def build_dump(records, day):
    table = f"acidentes_observatrafego_{day.replace('-', '')}"
    columns = ["id","municipio_notificacao","nome_notificante","endereco","veiculo_usuario","sinistro_com_vitimas","quantidade_vitimas","sinistro_vitimas","equipamentos_seguranca","latitude","longitude","descricao","registro_no_local_sinistro","registro_fora_local_descricao","tempo_registro_segundos","data_hora","photo_count"]
    lines = [f'DROP TABLE IF EXISTS "{table}";', f'CREATE TABLE "{table}" (', '  "id" TEXT, "municipio_notificacao" TEXT, "nome_notificante" TEXT,', '  "endereco" TEXT, "veiculo_usuario" TEXT, "sinistro_com_vitimas" TEXT,', '  "quantidade_vitimas" TEXT, "sinistro_vitimas" TEXT, "equipamentos_seguranca" TEXT,', '  "latitude" TEXT, "longitude" TEXT, "descricao" TEXT,', '  "registro_no_local_sinistro" TEXT, "registro_fora_local_descricao" TEXT,', '  "tempo_registro_segundos" INTEGER, "data_hora" TEXT, "photo_count" INTEGER', ');','']
    col_sql=', '.join('"'+c+'"' for c in columns)
    seen=set()
    for item in records:
        key=str(item.get('id','')).strip()
        if key and key in seen: continue
        if key: seen.add(key)
        vals=[item.get('id'),item.get('municipioNotificacao'),item.get('nomeNotificante'),item.get('endereco'),item.get('veiculoUsuario'),item.get('sinistroComVitimas'),item.get('quantidadeVitimas'),item.get('sinistroVitimas'),item.get('equipamentosSeguranca'),item.get('latitude'),item.get('longitude'),item.get('descricao'),item.get('registroNoLocalSinistro'),item.get('registroForaLocalDescricao'),item.get('tempoRegistroSegundos',0),item.get('dataHora'),item.get('photoCount',len(item.get('fotos',[])) if isinstance(item.get('fotos'),list) else 0)]
        lines.append(f'INSERT INTO "{table}" ({col_sql}) VALUES ({", ".join(sql_value(v) for v in vals)});')
    lines.append('COMMIT;')
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(); p.add_argument('--url'); p.add_argument('--input'); p.add_argument('--day',required=True); p.add_argument('--output',required=True); a=p.parse_args()
    if not a.url and not a.input: p.error('informe --url ou --input')
    payload=json.loads(Path(a.input).read_text(encoding='utf-8')) if a.input else fetch_json(a.url)
    records=normalize(payload)
    print(f'Tipo de resposta: {type(payload).__name__}')
    if isinstance(payload,dict): print(f'Chaves de topo: {sorted(payload.keys())}')
    print(f'Registros normalizados: {len(records)}')
    selected=[]
    for r in records:
        dt=parse_datetime(r.get('dataHora'))
        if dt and dt.strftime('%Y-%m-%d')==a.day: selected.append(r)
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(build_dump(selected,a.day),encoding='utf-8')
    print(f'Registros totais recebidos: {len(records)}'); print(f'Registros do dia {a.day}: {len(selected)}'); print(f'Dump: {out}')
if __name__=='__main__': main()
