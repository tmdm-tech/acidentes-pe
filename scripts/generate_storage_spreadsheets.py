#!/usr/bin/env python3
"""Gera planilhas CSV (diaria, semanal e mensal) a partir do backup JSON."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


HEADERS = [
    "id",
    "periodo",
    "data_hora_registro",
    "municipio_notificacao",
    "nome_notificante",
    "endereco",
    "veiculo_usuario",
    "sinistro_com_vitimas",
    "quantidade_vitimas",
    "sinistro_vitimas",
    "equipamentos_seguranca",
    "latitude",
    "longitude",
    "quantidade_fotos",
    "tempo_registro_segundos",
    "tempo_registro_formatado",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera planilhas de armazenamento a partir de accidents_latest.json"
    )
    parser.add_argument(
        "--input",
        default="observa_backup/accidents_latest.json",
        help="Arquivo JSON de entrada com os registros",
    )
    parser.add_argument(
        "--output-dir",
        default="planilhas",
        help="Diretorio onde as planilhas serao salvas",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Nao falha quando o arquivo de entrada ainda nao existe",
    )
    return parser.parse_args()


def parse_record_datetime(item: dict) -> datetime:
    raw = str(item.get("dataHora") or "").strip()
    if raw:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw[:19], fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.min


def period_label(dt_value: datetime, period: str) -> str:
    if period == "daily":
        return dt_value.strftime("%Y-%m-%d") if dt_value != datetime.min else ""
    if period == "weekly":
        if dt_value == datetime.min:
            return ""
        year, week, _ = dt_value.isocalendar()
        return f"{year}-S{week:02d}"
    if period == "monthly":
        return dt_value.strftime("%Y-%m") if dt_value != datetime.min else ""
    return ""


def format_hms(total_seconds: int) -> str:
    try:
        secs = max(0, int(total_seconds))
    except (TypeError, ValueError):
        secs = 0
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def normalize_records(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        records = payload.get("records", [])
        if isinstance(records, list):
            return [r for r in records if isinstance(r, dict)]
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []


def build_row(period: str, item: dict) -> dict:
    dt_value = parse_record_datetime(item)
    fotos = item.get("fotos") if isinstance(item.get("fotos"), list) else []
    tempo_segundos = item.get("tempoRegistroSegundos", 0)

    return {
        "id": item.get("id", ""),
        "periodo": period_label(dt_value, period),
        "data_hora_registro": item.get("dataHora", ""),
        "municipio_notificacao": item.get("municipioNotificacao", ""),
        "nome_notificante": item.get("nomeNotificante", ""),
        "endereco": item.get("endereco", ""),
        "veiculo_usuario": item.get("veiculoUsuario", ""),
        "sinistro_com_vitimas": item.get("sinistroComVitimas", ""),
        "quantidade_vitimas": item.get("quantidadeVitimas", ""),
        "sinistro_vitimas": item.get("sinistroVitimas", ""),
        "equipamentos_seguranca": item.get("equipamentosSeguranca", ""),
        "latitude": item.get("latitude", ""),
        "longitude": item.get("longitude", ""),
        "quantidade_fotos": len(fotos),
        "tempo_registro_segundos": tempo_segundos,
        "tempo_registro_formatado": format_hms(tempo_segundos),
    }


def write_csv(period: str, records: list[dict], output_dir: Path, stamp: str) -> None:
    slug = {
        "daily": "diario",
        "weekly": "semanal",
        "monthly": "mensal",
    }[period]

    archived = output_dir / f"acidentes_{slug}_{stamp}.csv"
    latest = output_dir / f"acidentes_{slug}_latest.csv"

    with archived.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=HEADERS)
        writer.writeheader()
        for item in records:
            writer.writerow(build_row(period, item))

    latest.write_text(archived.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        message = f"Arquivo nao encontrado: {input_path}"
        if args.allow_missing:
            print(f"[AVISO] {message}. Nenhuma planilha gerada.")
            return 0
        print(f"[ERRO] {message}")
        return 1

    with input_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    records = normalize_records(payload)
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    write_csv("daily", records, output_dir, stamp)
    write_csv("weekly", records, output_dir, stamp)
    write_csv("monthly", records, output_dir, stamp)

    print(f"Planilhas geradas em: {output_dir}")
    print(f"Total de registros processados: {len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())