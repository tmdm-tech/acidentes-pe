#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory, send_file
import json
import os
import csv
from datetime import datetime, date, timedelta
import socket
import threading
import time

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

# Arquivo para armazenar acidentes
ACCIDENTS_FILE = 'accidents.json'
WEB_DIR = 'web'
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
MAX_PHOTOS = 5
MAX_PHOTO_CHARS = 1_200_000
EXPORTS_DIR = 'exports'
EXPORT_STATE_FILE = os.path.join(EXPORTS_DIR, 'daily_export_state.json')
SCHEDULER_STARTED = False


def ensure_exports_dir():
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def read_export_state():
    ensure_exports_dir()
    if not os.path.exists(EXPORT_STATE_FILE):
        return {'lastGeneratedFor': ''}
    try:
        with open(EXPORT_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            if not isinstance(state, dict):
                return {'lastGeneratedFor': ''}
            return {'lastGeneratedFor': str(state.get('lastGeneratedFor', ''))}
    except Exception:
        return {'lastGeneratedFor': ''}


def write_export_state(state):
    ensure_exports_dir()
    with open(EXPORT_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_accident_datetime(item):
    item_id = item.get('id', '')
    try:
        ts = int(str(item_id))
        return datetime.fromtimestamp(ts / 1000)
    except (TypeError, ValueError):
        pass

    text = item.get('dataHora', '')
    try:
        return datetime.strptime(text, '%d/%m/%Y %H:%M:%S')
    except (TypeError, ValueError):
        return datetime.now()


def period_label(dt, period):
    if period == 'daily':
        return dt.strftime('%Y-%m-%d')
    if period == 'weekly':
        iso = dt.isocalendar()
        return f'{iso.year}-W{iso.week:02d}'
    if period == 'monthly':
        return dt.strftime('%Y-%m')
    return dt.strftime('%Y-%m-%d')


def daily_date_label(dt_value):
    return dt_value.strftime('%Y-%m-%d')


def accidents_for_date(accidents, target_date):
    rows = []
    for item in accidents:
        if parse_accident_datetime(item).date() == target_date:
            rows.append(item)
    return rows


def write_daily_csv_for_date(target_date, accidents):
    ensure_exports_dir()
    label = daily_date_label(target_date)
    file_name = f'acidentes_diario_{label}.csv'
    latest_name = 'acidentes_diario_latest.csv'
    file_path = os.path.join(EXPORTS_DIR, file_name)
    latest_path = os.path.join(EXPORTS_DIR, latest_name)

    headers = [
        'id',
        'periodo',
        'data_hora_registro',
        'nome_notificante',
        'cpf',
        'endereco',
        'latitude',
        'longitude',
        'descricao',
        'quantidade_fotos',
        'tempo_registro_segundos'
    ]

    with open(file_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for item in accidents:
            photos = item.get('fotos') if isinstance(item.get('fotos'), list) else []
            writer.writerow({
                'id': item.get('id', ''),
                'periodo': label,
                'data_hora_registro': item.get('dataHora', ''),
                'nome_notificante': item.get('nomeNotificante', ''),
                'cpf': item.get('cpf', ''),
                'endereco': item.get('endereco', ''),
                'latitude': item.get('latitude', ''),
                'longitude': item.get('longitude', ''),
                'descricao': item.get('descricao', ''),
                'quantidade_fotos': len(photos),
                'tempo_registro_segundos': item.get('tempoRegistroSegundos', 0)
            })

    with open(file_path, 'r', encoding='utf-8-sig') as src:
        content = src.read()
    with open(latest_path, 'w', encoding='utf-8-sig') as dst:
        dst.write(content)

    return {'file': file_name, 'latest': latest_name, 'records': len(accidents)}


def write_daily_map_for_date(target_date, accidents):
    ensure_exports_dir()
    label = daily_date_label(target_date)
    file_name = f'mapa_pe_diario_{label}.html'
    latest_name = 'mapa_pe_diario_latest.html'
    file_path = os.path.join(EXPORTS_DIR, file_name)
    latest_path = os.path.join(EXPORTS_DIR, latest_name)

    markers = []
    for item in accidents:
        try:
            lat = float(str(item.get('latitude', '')).replace(',', '.'))
            lon = float(str(item.get('longitude', '')).replace(',', '.'))
        except (TypeError, ValueError):
            continue
        markers.append({
            'lat': lat,
            'lon': lon,
            'endereco': item.get('endereco', ''),
            'dataHora': item.get('dataHora', ''),
            'descricao': item.get('descricao', ''),
            'nomeNotificante': item.get('nomeNotificante', '')
        })

    markers_json = json.dumps(markers, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Mapa Diario de Acidentes - {label}</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" crossorigin=\"\"/>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; }}
    header {{ padding: 12px 16px; background: #0b3d91; color: #fff; }}
    #map {{ height: calc(100vh - 64px); width: 100%; }}
  </style>
</head>
<body>
  <header>
    <strong>Mapa Diario de Acidentes - {label}</strong>
    <div>Total de pontos: {len(markers)}</div>
  </header>
  <div id=\"map\"></div>
  <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\" crossorigin=\"\"></script>
  <script>
    const map = L.map('map').setView([-8.3, -36.0], 8);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);

    const points = {markers_json};
    const bounds = [];

    points.forEach((p) => {{
      const marker = L.marker([p.lat, p.lon]).addTo(map);
      marker.bindPopup(
        `<b>${{p.endereco || '-'}}</b><br/>` +
        `Data/Hora: ${{p.dataHora || '-'}}<br/>` +
        `Notificante: ${{p.nomeNotificante || '-'}}<br/>` +
        `Descricao: ${{p.descricao || '-'}}`
      );
      bounds.push([p.lat, p.lon]);
    }});

    if (bounds.length > 0) {{
      map.fitBounds(bounds, {{ padding: [20, 20] }});
    }}
  </script>
</body>
</html>
"""

    with open(file_path, 'w', encoding='utf-8') as f:
      f.write(html)
    with open(file_path, 'r', encoding='utf-8') as src:
      content = src.read()
    with open(latest_path, 'w', encoding='utf-8') as dst:
      dst.write(content)

    return {'file': file_name, 'latest': latest_name, 'points': len(markers)}


def _generation_cutoff(now_dt):
    # Ate 07:59, o ultimo dia que deveria estar gerado eh D-2.
    # A partir de 08:00, o ultimo dia devido eh D-1.
    if now_dt.hour >= 8:
        return now_dt.date() - timedelta(days=1)
    return now_dt.date() - timedelta(days=2)


def ensure_scheduled_daily_exports(accidents):
    state = read_export_state()
    last_label = state.get('lastGeneratedFor', '')
    now_dt = datetime.now()
    cutoff = _generation_cutoff(now_dt)

    try:
        last_date = datetime.strptime(last_label, '%Y-%m-%d').date() if last_label else None
    except ValueError:
        last_date = None

    if last_date is None:
        # Se nunca gerou, inicia em D-2 para atender o ciclo de 08h.
        last_date = now_dt.date() - timedelta(days=3)

    next_date = last_date + timedelta(days=1)
    generated = []

    while next_date <= cutoff:
        daily_items = accidents_for_date(accidents, next_date)
        csv_info = write_daily_csv_for_date(next_date, daily_items)
        map_info = write_daily_map_for_date(next_date, daily_items)
        generated.append({
            'date': daily_date_label(next_date),
            'csv': csv_info,
            'map': map_info
        })
        last_date = next_date
        next_date = next_date + timedelta(days=1)

    if generated:
        write_export_state({'lastGeneratedFor': daily_date_label(last_date)})

    return {
        'generated': generated,
        'lastGeneratedFor': daily_date_label(last_date)
    }


def daily_scheduler_loop():
    while True:
        try:
            accidents = load_accidents()
            ensure_scheduled_daily_exports(accidents)
        except Exception:
            pass
        time.sleep(300)


def start_daily_scheduler():
    global SCHEDULER_STARTED
    if SCHEDULER_STARTED:
        return
    thread = threading.Thread(target=daily_scheduler_loop, daemon=True)
    thread.start()
    SCHEDULER_STARTED = True


def write_export_csv(period, accidents):
    ensure_exports_dir()
    now = datetime.now()
    ts = now.strftime('%Y%m%d_%H%M%S')
    period_slug = {
        'daily': 'diario',
        'weekly': 'semanal',
        'monthly': 'mensal'
    }.get(period, period)

    archived_name = f'acidentes_{period_slug}_{ts}.csv'
    latest_name = f'acidentes_{period_slug}_latest.csv'
    archived_path = os.path.join(EXPORTS_DIR, archived_name)
    latest_path = os.path.join(EXPORTS_DIR, latest_name)

    headers = [
        'id',
        'periodo',
        'data_hora_registro',
        'nome_notificante',
        'cpf',
        'endereco',
        'latitude',
        'longitude',
        'descricao',
        'quantidade_fotos',
        'tempo_registro_segundos'
    ]

    with open(archived_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for item in accidents:
            dt = parse_accident_datetime(item)
            photos = item.get('fotos') if isinstance(item.get('fotos'), list) else []
            writer.writerow({
                'id': item.get('id', ''),
                'periodo': period_label(dt, period),
                'data_hora_registro': item.get('dataHora', ''),
                'nome_notificante': item.get('nomeNotificante', ''),
                'cpf': item.get('cpf', ''),
                'endereco': item.get('endereco', ''),
                'latitude': item.get('latitude', ''),
                'longitude': item.get('longitude', ''),
                'descricao': item.get('descricao', ''),
                'quantidade_fotos': len(photos),
                'tempo_registro_segundos': item.get('tempoRegistroSegundos', 0)
            })

    with open(archived_path, 'r', encoding='utf-8-sig', newline='') as src:
        content = src.read()
    with open(latest_path, 'w', encoding='utf-8-sig', newline='') as dst:
        dst.write(content)

    return {
        'period': period,
        'archived': archived_name,
        'latest': latest_name,
        'totalRecords': len(accidents),
        'generatedAt': now.strftime('%d/%m/%Y %H:%M:%S')
    }


def generate_all_exports(accidents):
    ensure_scheduled_daily_exports(accidents)
    return {
        'daily': write_export_csv('daily', accidents),
        'weekly': write_export_csv('weekly', accidents),
        'monthly': write_export_csv('monthly', accidents)
    }

def load_accidents():
    if os.path.exists(ACCIDENTS_FILE):
        with open(ACCIDENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_accidents(accidents):
    with open(ACCIDENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accidents, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    if os.path.exists(os.path.join(WEB_DIR, 'index_simple.html')):
        return send_from_directory(WEB_DIR, 'index_simple.html')
    return jsonify({
        'status': 'ok',
        'service': 'acidentes-pe',
        'message': 'API online. Frontend estatico nao encontrado neste deploy.',
        'endpoints': ['/health', '/version', '/api/accidents']
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/version')
def version():
    return jsonify({'version': APP_VERSION}), 200

@app.route('/<path:filename>')
def serve_static(filename):
    if os.path.exists(os.path.join(WEB_DIR, filename)):
        return send_from_directory(WEB_DIR, filename)
    return jsonify({'error': 'Arquivo nao encontrado'}), 404

@app.route('/api/accidents', methods=['GET'])
def get_accidents():
    accidents = load_accidents()
    ensure_scheduled_daily_exports(accidents)
    return jsonify(accidents)


@app.route('/api/exports', methods=['GET'])
def get_exports_status():
    accidents = load_accidents()
    schedule = ensure_scheduled_daily_exports(accidents)
    info = generate_all_exports(accidents)
    return jsonify({
        'success': True,
        'records': len(accidents),
        'exports': info,
        'scheduledDaily': schedule
    })


@app.route('/api/exports/download/<period>', methods=['GET'])
def download_export(period):
    if period not in {'daily', 'weekly', 'monthly'}:
        return jsonify({'error': 'Periodo invalido. Use daily, weekly ou monthly.'}), 400

    accidents = load_accidents()
    ensure_scheduled_daily_exports(accidents)

    if period == 'daily':
        latest_file = os.path.join(EXPORTS_DIR, 'acidentes_diario_latest.csv')
        if not os.path.exists(latest_file):
            return jsonify({'error': 'Planilha diaria ainda nao foi gerada.'}), 404
        return send_file(
            latest_file,
            as_attachment=True,
            download_name='acidentes_diario_latest.csv',
            mimetype='text/csv'
        )

    info = write_export_csv(period, accidents)
    latest_file = info['latest']
    return send_file(
        os.path.join(EXPORTS_DIR, latest_file),
        as_attachment=True,
        download_name=latest_file,
        mimetype='text/csv'
    )


@app.route('/api/exports/download/daily-map', methods=['GET'])
def download_daily_map():
    accidents = load_accidents()
    ensure_scheduled_daily_exports(accidents)
    latest_file = os.path.join(EXPORTS_DIR, 'mapa_pe_diario_latest.html')
    if not os.path.exists(latest_file):
        return jsonify({'error': 'Mapa diario ainda nao foi gerado.'}), 404

    return send_file(
        latest_file,
        as_attachment=True,
        download_name='mapa_pe_diario_latest.html',
        mimetype='text/html'
    )

@app.route('/api/accidents', methods=['POST'])
def add_accident():
    try:
        data = request.get_json() or {}

        # Validar dados obrigatórios
        required_fields = ['endereco', 'latitude', 'longitude', 'nomeNotificante', 'cpf', 'descricao']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify({'error': f'Campo obrigatório: {field}'}), 400

        raw_photos = data.get('fotos', [])
        if raw_photos is None:
            raw_photos = []
        if not isinstance(raw_photos, list):
            return jsonify({'error': 'Campo fotos deve ser uma lista'}), 400
        if len(raw_photos) > MAX_PHOTOS:
            return jsonify({'error': f'Maximo de {MAX_PHOTOS} fotos por registro'}), 400

        photos = []
        for photo in raw_photos:
            if not isinstance(photo, str) or not photo.startswith('data:image/'):
                return jsonify({'error': 'Formato de foto invalido'}), 400
            if len(photo) > MAX_PHOTO_CHARS:
                return jsonify({'error': 'Foto muito grande; reduza a qualidade/tamanho'}), 400
            photos.append(photo)

        raw_elapsed = data.get('tempoRegistroSegundos', 0)
        elapsed_seconds = 0
        try:
            elapsed_seconds = max(0, int(raw_elapsed))
        except (TypeError, ValueError):
            elapsed_seconds = 0

        # Criar acidente
        accident = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'endereco': data['endereco'].strip(),
            'latitude': data['latitude'].strip(),
            'longitude': data['longitude'].strip(),
            'nomeNotificante': data['nomeNotificante'].strip(),
            'cpf': data['cpf'].strip(),
            'descricao': data['descricao'].strip(),
            'fotos': photos,
            'tempoRegistroSegundos': elapsed_seconds,
            'dataHora': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'photoCount': len(photos)
        }

        # Salvar acidente
        accidents = load_accidents()
        accidents.append(accident)
        save_accidents(accidents)
        ensure_scheduled_daily_exports(accidents)
        generate_all_exports(accidents)

        return jsonify({'success': True, 'message': 'Acidente reportado com sucesso!', 'id': accident['id']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accidents/<accident_id>', methods=['DELETE'])
def delete_accident(accident_id):
    return jsonify({
        'success': False,
        'error': 'Remocao desativada. Os registros sao permanentes.'
    }), 403

start_daily_scheduler()
ensure_scheduled_daily_exports(load_accidents())


if __name__ == '__main__':
    # Obter IP local
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("\n" + "="*60)
    print("🚀 ObservaTrânsito - Servidor Web")
    print("="*60)
    print(f"📱 Acesso Local: http://localhost:8000")
    print(f"🌐 Acesso na Rede: http://{local_ip}:8000")
    print("\n📋 Instruções para acesso:")
    print("1. No mesmo computador: http://localhost:8000")
    print(f"2. Em outros dispositivos na rede: http://{local_ip}:8000")
    print("3. Para celular: Abra o link acima no navegador")
    print("4. Para instalar como app: Toque em 'Adicionar à Tela Inicial'")
    print("\n⚠️  IMPORTANTE: Certifique-se de que o firewall permite conexões na porta 8000")
    print("   No macOS: System Settings > Network > Firewall")
    print("\nPressione Ctrl+C para parar o servidor...")
    print("="*60 + "\n")

    # Obter porta da variável de ambiente (para deploy online)
    port = int(os.environ.get('PORT', 8000))

    # Executar servidor acessível de qualquer IP
    app.run(host='0.0.0.0', port=port, debug=False)