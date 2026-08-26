#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def sql_value(value):
    if value is None or value == "": return "NULL"
    if isinstance(value, bool): return "TRUE" if value else "FALSE"
    return "'" + str(value).replace("'", "''") + "'"

def normalize(payload):
    if isinstance(payload, dict) and isinstance(payload.get('records'), list):
        return [r for r in payload['records'] if isinstance(r, dict)]
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []

def build_dump(records):
    columns = [
        'id','municipio_notificacao','nome_notificante','endereco','veiculo_usuario',
        'sinistro_com_vitimas','quantidade_vitimas','sinistro_vitimas','equipamentos_seguranca',
        'latitude','longitude','descricao','registro_no_local_sinistro',
        'registro_fora_local_descricao','tempo_registro_segundos','data_hora','photo_count'
    ]
    lines = [
        'DROP TABLE IF EXISTS "acidentes_observatrafego_snapshot";',
        'CREATE TABLE "acidentes_observatrafego_snapshot" (',
        '  "id" TEXT, "municipio_notificacao" TEXT, "nome_notificante" TEXT,',
        '  "endereco" TEXT, "veiculo_usuario" TEXT, "sinistro_com_vitimas" TEXT,',
        '  "quantidade_vitimas" TEXT, "sinistro_vitimas" TEXT, "equipamentos_seguranca" TEXT,',
        '  "latitude" TEXT, "longitude" TEXT, "descricao" TEXT,',
        '  "registro_no_local_sinistro" TEXT, "registro_fora_local_descricao" TEXT,',
        '  "tempo_registro_segundos" INTEGER, "data_hora" TEXT, "photo_count" INTEGER',
        ');',''
    ]
    col_sql=', '.join('"'+c+'"' for c in columns)
    seen=set()
    for item in records:
        key=str(item.get('id','')).strip()
        if key and key in seen: continue
        if key: seen.add(key)
        vals=[
            item.get('id'), item.get('municipioNotificacao'), item.get('nomeNotificante'), item.get('endereco'),
            item.get('veiculoUsuario'), item.get('sinistroComVitimas'), item.get('quantidadeVitimas'),
            item.get('sinistroVitimas'), item.get('equipamentosSeguranca'), item.get('latitude'), item.get('longitude'),
            item.get('descricao'), item.get('registroNoLocalSinistro'), item.get('registroForaLocalDescricao'),
            item.get('tempoRegistroSegundos',0), item.get('dataHora'),
            item.get('photoCount', len(item.get('fotos',[])) if isinstance(item.get('fotos'),list) else 0)
        ]
        lines.append(f'INSERT INTO "acidentes_observatrafego_snapshot" ({col_sql}) VALUES ({", ".join(sql_value(v) for v in vals)});')
    lines.append('COMMIT;')
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',required=True); p.add_argument('--output',required=True); a=p.parse_args()
    payload=json.loads(Path(a.input).read_text(encoding='utf-8'))
    records=normalize(payload)
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(build_dump(records),encoding='utf-8')
    print(f'Registros preservados no snapshot: {len(records)}')
    print(f'Dump: {out}')
if __name__=='__main__': main()
