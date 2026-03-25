#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory, send_file
import json
import os
import csv
from datetime import datetime, date, timedelta
import socket
import threading
import time
import base64
import shutil
import hmac
import importlib
from urllib import request as urllib_request
from urllib import error as urllib_error

try:
    _fernet_module = importlib.import_module('cryptography.fernet')
    Fernet = getattr(_fernet_module, 'Fernet')
    InvalidToken = getattr(_fernet_module, 'InvalidToken')
except Exception:  # pragma: no cover - fallback para ambiente sem dependencia
    Fernet = None
    InvalidToken = Exception

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024


def load_dotenv_file(path='.env'):
    if not os.path.exists(path):
        return

    try:
        with open(path, 'r', encoding='utf-8') as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Falha no parser do .env nao deve derrubar a API.
        pass


load_dotenv_file()

WEB_DIR = 'web'
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
MAX_PHOTOS = 5
MAX_PHOTO_CHARS = 1_200_000


def resolve_data_dir():
    configured = os.environ.get('DATA_DIR', '').strip()
    if configured:
        return configured

    # Em provedores como Render, /var/data e persistente entre deploys.
    persistent_dir = '/var/data'
    if os.path.isdir(persistent_dir) and os.access(persistent_dir, os.W_OK):
        return persistent_dir

    return '.'


DATA_DIR = resolve_data_dir()
ACCIDENTS_FILE = os.path.join(DATA_DIR, 'accidents.json')
ACCIDENTS_BAK_FILE = os.path.join(DATA_DIR, 'accidents.bak.json')
EXPORTS_DIR = os.path.join(DATA_DIR, 'exports')
EXPORT_STATE_FILE = os.path.join(EXPORTS_DIR, 'daily_export_state.json')
SCHEDULER_STARTED = False
ADMIN_ACCESS_KEY = (
    os.environ.get('ADMIN_ACCESS_KEY', '')
    or os.environ.get('ADMIN_KEY', '')
    or os.environ.get('ADMIM_ACESS_KEY', '')
).strip()
GITHUB_BACKUP_REPO = os.environ.get('GITHUB_BACKUP_REPO', '')  # owner/repo
GITHUB_BACKUP_TOKEN = os.environ.get('GITHUB_BACKUP_TOKEN', '')
GITHUB_BACKUP_BRANCH = os.environ.get('GITHUB_BACKUP_BRANCH', 'main')
GITHUB_BACKUP_PATH = os.environ.get('GITHUB_BACKUP_PATH', 'observa_backup')
BACKUP_STATE_FILE = os.path.join(DATA_DIR, 'backup_state.json')
DATA_ENCRYPTION_KEY = os.environ.get('DATA_ENCRYPTION_KEY', '').strip()
DATA_ENCRYPTION_ENABLED = bool(DATA_ENCRYPTION_KEY)

if DATA_ENCRYPTION_ENABLED and Fernet is None:
    raise RuntimeError('DATA_ENCRYPTION_KEY configurada, mas dependência cryptography não está instalada')

if DATA_ENCRYPTION_ENABLED:
    try:
        DATA_FERNET = Fernet(DATA_ENCRYPTION_KEY.encode('utf-8'))
    except Exception as exc:
        raise RuntimeError('DATA_ENCRYPTION_KEY inválida. Gere com Fernet.generate_key().') from exc
else:
    DATA_FERNET = None


def ensure_exports_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def secure_file_permissions(file_path):
    # Em ambientes Linux, restringe leitura/escrita ao dono do processo.
    try:
        os.chmod(file_path, 0o600)
    except Exception:
        pass


def _serialize_accidents_payload(accidents):
    if not DATA_FERNET:
        return accidents

    raw = json.dumps(accidents, ensure_ascii=False).encode('utf-8')
    encrypted = DATA_FERNET.encrypt(raw).decode('utf-8')
    return {
        '_encrypted': True,
        'algorithm': 'fernet',
        'version': 1,
        'payload': encrypted,
    }


def _deserialize_accidents_payload(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict) and payload.get('_encrypted') is True:
        if not DATA_FERNET:
            raise RuntimeError('Arquivo de acidentes está criptografado e DATA_ENCRYPTION_KEY não foi configurada')

        encrypted = str(payload.get('payload', '')).encode('utf-8')
        if not encrypted:
            return []
        try:
            decrypted = DATA_FERNET.decrypt(encrypted)
        except InvalidToken as exc:
            raise RuntimeError('Falha ao descriptografar acidentes: chave incorreta ou arquivo inválido') from exc

        loaded = json.loads(decrypted.decode('utf-8'))
        return loaded if isinstance(loaded, list) else []

    return []


def read_backup_state():
    ensure_exports_dir()
    if not os.path.exists(BACKUP_STATE_FILE):
        return {'lastBackupAt': '', 'lastBackupError': ''}
    try:
        with open(BACKUP_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            if not isinstance(state, dict):
                return {'lastBackupAt': '', 'lastBackupError': ''}
            return {
                'lastBackupAt': str(state.get('lastBackupAt', '')),
                'lastBackupError': str(state.get('lastBackupError', '')),
            }
    except Exception:
        return {'lastBackupAt': '', 'lastBackupError': ''}


def write_backup_state(state):
    ensure_exports_dir()
    with open(BACKUP_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    secure_file_permissions(BACKUP_STATE_FILE)


def is_admin_request():
    if not ADMIN_ACCESS_KEY:
        return False
    candidate = str(request.headers.get('X-Admin-Key', '')).strip()
    return hmac.compare_digest(candidate, ADMIN_ACCESS_KEY)


def require_admin_response():
    return jsonify({'error': 'Acesso restrito ao administrador'}), 403


def github_backup_enabled():
    return bool(GITHUB_BACKUP_REPO and GITHUB_BACKUP_TOKEN)


def _github_api(method, path, payload=None):
    url = f'https://api.github.com{path}'
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')

    req = urllib_request.Request(url=url, method=method, data=data)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'Bearer {GITHUB_BACKUP_TOKEN}')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    req.add_header('User-Agent', 'observa-pe-backup')
    if data is not None:
        req.add_header('Content-Type', 'application/json')

    try:
        with urllib_request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib_error.HTTPError as err:
        body = err.read().decode('utf-8', errors='ignore') if hasattr(err, 'read') else ''
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {'message': body}
        return err.code, parsed


def _github_upsert_json(path, obj, message):
    content = json.dumps(obj, ensure_ascii=False, indent=2)
    encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')

    get_path = f'/repos/{GITHUB_BACKUP_REPO}/contents/{path}?ref={GITHUB_BACKUP_BRANCH}'
    status, current = _github_api('GET', get_path)
    sha = current.get('sha') if status == 200 and isinstance(current, dict) else None

    payload = {
        'message': message,
        'content': encoded,
        'branch': GITHUB_BACKUP_BRANCH,
    }
    if sha:
        payload['sha'] = sha

    put_path = f'/repos/{GITHUB_BACKUP_REPO}/contents/{path}'
    put_status, put_data = _github_api('PUT', put_path, payload)
    return put_status, put_data


def backup_accidents_to_github(accidents):
    if not github_backup_enabled():
        return {'enabled': False, 'message': 'Backup GitHub nao configurado'}

    now = datetime.now()
    day_label = now.strftime('%Y-%m-%d')
    base_path = GITHUB_BACKUP_PATH.strip('/').strip()
    latest_path = f'{base_path}/accidents_latest.json' if base_path else 'accidents_latest.json'
    daily_path = f'{base_path}/accidents_{day_label}.json' if base_path else f'accidents_{day_label}.json'

    st_latest, _ = _github_upsert_json(
        latest_path,
        {'generatedAt': now.isoformat(), 'records': accidents},
        f'Backup atualizado ({now.strftime("%d/%m/%Y %H:%M:%S")})'
    )
    st_daily, _ = _github_upsert_json(
        daily_path,
        {'generatedAt': now.isoformat(), 'records': accidents},
        f'Backup diario {day_label}'
    )

    ok = st_latest in (200, 201) and st_daily in (200, 201)
    state = {
        'lastBackupAt': now.strftime('%d/%m/%Y %H:%M:%S') if ok else '',
        'lastBackupError': '' if ok else f'Falha GitHub ({st_latest}/{st_daily})'
    }
    write_backup_state(state)
    return {
        'enabled': True,
        'ok': ok,
        'statusLatest': st_latest,
        'statusDaily': st_daily,
        'repo': GITHUB_BACKUP_REPO,
        'branch': GITHUB_BACKUP_BRANCH,
        'path': base_path or '/'
    }


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
    secure_file_permissions(EXPORT_STATE_FILE)


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
        'municipio_notificacao',
        'nome_notificante',
        'endereco',
        'veiculo_usuario',
        'sinistro_com_vitimas',
        'quantidade_vitimas',
        'sinistro_vitimas',
        'equipamentos_seguranca',
        'latitude',
        'longitude',
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
                'municipio_notificacao': item.get('municipioNotificacao', ''),
                'nome_notificante': item.get('nomeNotificante', ''),
                'endereco': item.get('endereco', ''),
                'veiculo_usuario': item.get('veiculoUsuario', ''),
                'sinistro_com_vitimas': item.get('sinistroComVitimas', ''),
                'quantidade_vitimas': item.get('quantidadeVitimas', ''),
                'sinistro_vitimas': item.get('sinistroVitimas', ''),
                'equipamentos_seguranca': item.get('equipamentosSeguranca', ''),
                'latitude': item.get('latitude', ''),
                'longitude': item.get('longitude', ''),
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
            'nomeNotificante': item.get('nomeNotificante', ''),
            'municipioNotificacao': item.get('municipioNotificacao', ''),
            'veiculoUsuario': item.get('veiculoUsuario', ''),
            'sinistroComVitimas': item.get('sinistroComVitimas', ''),
            'quantidadeVitimas': item.get('quantidadeVitimas', ''),
            'sinistroVitimas': item.get('sinistroVitimas', '')
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
        `Municipio: ${{p.municipioNotificacao || '-'}}<br/>` +
        `Notificante: ${{p.nomeNotificante || '-'}}<br/>` +
        `Veiculo/Usuario: ${{p.veiculoUsuario || '-'}}<br/>` +
                `Sinistro com vitimas: ${{p.sinistroComVitimas || '-'}}<br/>` +
                `Quantidade de vitimas: ${{p.quantidadeVitimas || '-'}}<br/>` +
                `Vitimas: ${{p.sinistroVitimas || '-'}}`
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
        'municipio_notificacao',
        'nome_notificante',
        'endereco',
        'veiculo_usuario',
        'sinistro_com_vitimas',
        'quantidade_vitimas',
        'sinistro_vitimas',
        'equipamentos_seguranca',
        'latitude',
        'longitude',
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
                'municipio_notificacao': item.get('municipioNotificacao', ''),
                'nome_notificante': item.get('nomeNotificante', ''),
                'endereco': item.get('endereco', ''),
                'veiculo_usuario': item.get('veiculoUsuario', ''),
                'sinistro_com_vitimas': item.get('sinistroComVitimas', ''),
                'quantidade_vitimas': item.get('quantidadeVitimas', ''),
                'sinistro_vitimas': item.get('sinistroVitimas', ''),
                'equipamentos_seguranca': item.get('equipamentosSeguranca', ''),
                'latitude': item.get('latitude', ''),
                'longitude': item.get('longitude', ''),
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
    ensure_exports_dir()
    if os.path.exists(ACCIDENTS_FILE):
        try:
            with open(ACCIDENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return _deserialize_accidents_payload(data)
        except json.JSONDecodeError:
            # Se o arquivo principal corromper, tenta recuperar do backup.
            if os.path.exists(ACCIDENTS_BAK_FILE):
                with open(ACCIDENTS_BAK_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return _deserialize_accidents_payload(data)
        except RuntimeError:
            # Propaga erro de criptografia para facilitar diagnostico de ambiente.
            raise
    return []

def save_accidents(accidents):
    ensure_exports_dir()

    if os.path.exists(ACCIDENTS_FILE):
        shutil.copy2(ACCIDENTS_FILE, ACCIDENTS_BAK_FILE)
        secure_file_permissions(ACCIDENTS_BAK_FILE)

    tmp_file = f'{ACCIDENTS_FILE}.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        payload = _serialize_accidents_payload(accidents)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_file, ACCIDENTS_FILE)
    secure_file_permissions(ACCIDENTS_FILE)


def no_cache_response(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    if os.path.exists(os.path.join(WEB_DIR, 'index_simple.html')):
        return no_cache_response(send_from_directory(WEB_DIR, 'index_simple.html', max_age=0))
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
        lower_name = filename.lower()
        if lower_name.endswith(('.html', '.htm')):
            return no_cache_response(send_from_directory(WEB_DIR, filename, max_age=0))
        # Assets estaticos podem ser cacheados para melhorar tempo de abertura.
        return send_from_directory(WEB_DIR, filename, max_age=86400)
    return jsonify({'error': 'Arquivo nao encontrado'}), 404

@app.route('/api/accidents', methods=['GET'])
def get_accidents():
    accidents = load_accidents()
    ensure_scheduled_daily_exports(accidents)
    return jsonify(accidents)


@app.route('/api/exports', methods=['GET'])
def get_exports_status():
    if not is_admin_request():
        return require_admin_response()

    accidents = load_accidents()
    schedule = ensure_scheduled_daily_exports(accidents)
    info = generate_all_exports(accidents)
    backup_state = read_backup_state()
    return jsonify({
        'success': True,
        'records': len(accidents),
        'exports': info,
        'scheduledDaily': schedule,
        'backup': {
            'githubEnabled': github_backup_enabled(),
            'repo': GITHUB_BACKUP_REPO,
            'branch': GITHUB_BACKUP_BRANCH,
            'path': GITHUB_BACKUP_PATH,
            **backup_state
        }
    })


@app.route('/api/exports/download/<period>', methods=['GET'])
def download_export(period):
    if not is_admin_request():
        return require_admin_response()

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
    if not is_admin_request():
        return require_admin_response()

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


@app.route('/api/admin/auth', methods=['POST'])
def admin_auth():
    data = request.get_json(silent=True) or {}
    key = str(data.get('key', '')).strip()

    if not ADMIN_ACCESS_KEY:
        return jsonify({
            'success': False,
            'error': 'ADMIN_ACCESS_KEY nao configurada no servidor',
            'hint': 'Defina ADMIN_ACCESS_KEY (ou ADMIN_KEY) nas variaveis de ambiente e reinicie o servidor.'
        }), 503

    if key == ADMIN_ACCESS_KEY:
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Chave de administrador invalida'}), 403


@app.route('/api/admin/backup-now', methods=['POST'])
def admin_backup_now():
    if not is_admin_request():
        return require_admin_response()

    accidents = load_accidents()
    result = backup_accidents_to_github(accidents)
    if result.get('enabled') and not result.get('ok', True):
        return jsonify({'success': False, 'backup': result}), 502
    return jsonify({'success': True, 'backup': result})

@app.route('/api/accidents', methods=['POST'])
def add_accident():
    try:
        data = request.get_json() or {}

        # Validar dados obrigatórios
        required_fields = [
            'municipioNotificacao',
            'nomeNotificante',
            'endereco',
            'veiculoUsuario',
            'sinistroComVitimas',
            'equipamentosSeguranca',
            'latitude',
            'longitude'
        ]
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify({'error': f'Campo obrigatório: {field}'}), 400

        sinistro_com_vitimas = str(data.get('sinistroComVitimas', '')).strip()
        if sinistro_com_vitimas not in {'Sim', 'Não'}:
            return jsonify({'error': 'Campo sinistroComVitimas invalido. Use Sim ou Não.'}), 400

        quantidade_vitimas = str(data.get('quantidadeVitimas', '')).strip()
        if sinistro_com_vitimas == 'Sim' and quantidade_vitimas not in {'1', '2 ou mais', 'Vítima fatal'}:
            return jsonify({'error': 'Quantidade de vitimas invalida.'}), 400
        if sinistro_com_vitimas == 'Não':
            quantidade_vitimas = ''

        sinistro_vitimas = quantidade_vitimas if sinistro_com_vitimas == 'Sim' else 'Sem vítimas'

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
            'municipioNotificacao': data['municipioNotificacao'].strip(),
            'nomeNotificante': data['nomeNotificante'].strip(),
            'endereco': data['endereco'].strip(),
            'veiculoUsuario': data['veiculoUsuario'].strip(),
            'sinistroComVitimas': sinistro_com_vitimas,
            'quantidadeVitimas': quantidade_vitimas,
            'sinistroVitimas': sinistro_vitimas,
            'equipamentosSeguranca': data['equipamentosSeguranca'].strip(),
            'latitude': data['latitude'].strip(),
            'longitude': data['longitude'].strip(),
            'descricao': str(data.get('descricao', '')).strip(),
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
        backup_accidents_to_github(accidents)

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
    print("🚀 RedeVitima - Servidor Web")
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