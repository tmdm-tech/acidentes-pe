#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory, send_file, Response, stream_with_context
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
import re
from queue import Queue, Empty
from zoneinfo import ZoneInfo
from urllib import request as urllib_request
from urllib import error as urllib_error

try:
    _supabase_module = importlib.import_module('supabase')
    create_client = getattr(_supabase_module, 'create_client')
except Exception:  # pragma: no cover - fallback para ambiente sem dependencia
    create_client = None

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
APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'America/Recife').strip() or 'America/Recife'
MAX_PHOTOS = 5
MAX_PHOTO_CHARS = 1_200_000

try:
    APP_TZ = ZoneInfo(APP_TIMEZONE)
except Exception:
    APP_TZ = ZoneInfo('America/Recife')


def now_local_datetime():
    return datetime.now(APP_TZ)


def _as_bool_env(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'on', 'sim'}


def _can_use_directory(path):
    """Return True when path exists/is creatable and writable by current process."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return False

    return os.path.isdir(path) and os.access(path, os.W_OK)


def resolve_data_dir():
    configured = os.environ.get('DATA_DIR', '').strip()
    if configured:
        if _can_use_directory(configured):
            return configured
        return '.'

    # Em Render, /var/data e o local recomendado para disco persistente.
    if os.environ.get('RENDER') and _can_use_directory('/var/data'):
        return '/var/data'

    persistent_dir = '/var/data'
    if _can_use_directory(persistent_dir):
        return persistent_dir

    return '.'


def is_persistent_data_dir(path):
    normalized = os.path.abspath(path)
    return normalized == '/var/data' or normalized.startswith('/var/data/')


DATA_DIR = resolve_data_dir()
DATA_DIR_PERSISTENT = is_persistent_data_dir(DATA_DIR)
REQUIRE_PERSISTENT_STORAGE = _as_bool_env(
    'REQUIRE_PERSISTENT_STORAGE',
    default=bool(os.environ.get('RENDER')),
)
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
SUPABASE_SPREADSHEETS_URL = os.environ.get(
    'SUPABASE_SPREADSHEETS_URL',
    'https://supabase.com/dashboard/project/izdubenyjyxhtooaaxzv/editor/17552?schema=public'
).strip()
DATA_ENCRYPTION_KEY = os.environ.get('DATA_ENCRYPTION_KEY', '').strip()
DATA_ENCRYPTION_ENABLED = bool(DATA_ENCRYPTION_KEY)
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
SUPABASE_TABLE = os.environ.get('SUPABASE_TABLE', 'acidentes').strip() or 'acidentes'
SUPABASE_BOOTSTRAP_LOCAL = _as_bool_env('SUPABASE_BOOTSTRAP_LOCAL', default=True)
SUPABASE_PAGE_SIZE = 1000
REALTIME_SUBSCRIBERS = []
REALTIME_SUBSCRIBERS_LOCK = threading.Lock()
LOCAL_SUPABASE_SYNC_INTERVAL_SECONDS = 30
LAST_LOCAL_SUPABASE_SYNC_AT = 0.0
LOCAL_SUPABASE_SYNC_LOCK = threading.Lock()

if DATA_ENCRYPTION_ENABLED and Fernet is None:
    print('[WARN] DATA_ENCRYPTION_KEY definida, mas cryptography nao esta disponivel. Criptografia desativada.')
    DATA_ENCRYPTION_ENABLED = False
    DATA_FERNET = None
elif DATA_ENCRYPTION_ENABLED:
    try:
        DATA_FERNET = Fernet(DATA_ENCRYPTION_KEY.encode('utf-8'))
    except Exception:
        print('[WARN] DATA_ENCRYPTION_KEY invalida. Criptografia desativada para evitar falha no startup.')
        DATA_ENCRYPTION_ENABLED = False
        DATA_FERNET = None
else:
    DATA_FERNET = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and create_client is None:
    print('[WARN] Variaveis do Supabase configuradas, mas dependencia supabase nao esta disponivel.')

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and create_client is not None:
    try:
        SUPABASE_CLIENT = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception:
        print('[WARN] Falha ao inicializar cliente Supabase. API seguira com fallback local.')
        SUPABASE_CLIENT = None
else:
    SUPABASE_CLIENT = None


def validate_persistence_mode():
    if REQUIRE_PERSISTENT_STORAGE and not DATA_DIR_PERSISTENT and not supabase_enabled():
        print(
            '[WARN] Persistencia obrigatoria ativa, mas DATA_DIR nao aponta para /var/data. '
            'Continuando sem persistencia obrigatoria para evitar erro de deploy.'
        )


def supabase_enabled():
    return SUPABASE_CLIENT is not None


def supabase_configured():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def storage_mode_label():
    return 'supabase' if supabase_enabled() else 'local-json'


def get_supabase_diagnostics():
    diagnostics = {
        'configured': supabase_configured(),
        'enabled': supabase_enabled(),
        'table': SUPABASE_TABLE,
        'bootstrapLocal': SUPABASE_BOOTSTRAP_LOCAL,
        'healthy': False,
        'connected': False,
        'tableAccessible': False,
        'recordCount': None,
        'error': '',
    }

    if not supabase_configured():
        diagnostics['error'] = 'SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nao configuradas'
        return diagnostics

    if not supabase_enabled():
        diagnostics['error'] = 'Cliente Supabase indisponivel; verifique dependencia e credenciais'
        return diagnostics

    try:
        response = (
            SUPABASE_CLIENT
            .table(SUPABASE_TABLE)
            .select('id')
            .limit(1)
            .execute()
        )
        diagnostics['connected'] = True
        diagnostics['tableAccessible'] = True
        # Mantem o campo para compatibilidade de payload, sem obrigar count exato.
        data = response.data or []
        diagnostics['recordCount'] = len(data)
        diagnostics['healthy'] = True
    except Exception as exc:
        diagnostics['error'] = str(exc)

    return diagnostics


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


def _normalize_accident_record(item):
    if not isinstance(item, dict):
        return {}

    photos = item.get('fotos', [])
    if not isinstance(photos, list):
        photos = []

    return {
        'id': str(item.get('id', '')).strip(),
        'municipioNotificacao': str(item.get('municipioNotificacao', '')).strip(),
        'nomeNotificante': str(item.get('nomeNotificante', '')).strip(),
        'endereco': str(item.get('endereco', '')).strip(),
        'veiculoUsuario': str(item.get('veiculoUsuario', '')).strip(),
        'sinistroComVitimas': str(item.get('sinistroComVitimas', '')).strip(),
        'quantidadeVitimas': str(item.get('quantidadeVitimas', '')).strip(),
        'sinistroVitimas': str(item.get('sinistroVitimas', '')).strip(),
        'equipamentosSeguranca': str(item.get('equipamentosSeguranca', '')).strip(),
        'latitude': str(item.get('latitude', '')).strip(),
        'longitude': str(item.get('longitude', '')).strip(),
        'descricao': str(item.get('descricao', '')).strip(),
        'registroNoLocalSinistro': str(item.get('registroNoLocalSinistro', '')).strip(),
        'registroForaLocalDescricao': str(item.get('registroForaLocalDescricao', '')).strip(),
        'fotos': photos,
        'tempoRegistroSegundos': int(item.get('tempoRegistroSegundos', 0) or 0),
        'dataHora': str(item.get('dataHora', '')).strip(),
        'photoCount': len(photos),
    }


def _merge_accident_records(primary, secondary):
    """Merge two accident lists by id, preserving primary precedence."""
    merged = []
    seen = set()

    def is_missing(value):
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ''
        if isinstance(value, list):
            return len(value) == 0
        if isinstance(value, (int, float)):
            return value == 0
        return False

    for source in (primary or [], secondary or []):
        for item in source:
            normalized = _normalize_accident_record(item)
            item_id = normalized.get('id', '').strip()
            if not item_id or item_id in seen:
                if item_id:
                    existing = next((record for record in merged if record.get('id') == item_id), None)
                    if existing:
                        for key, value in normalized.items():
                            if is_missing(existing.get(key)) and not is_missing(value):
                                existing[key] = value
                continue
            seen.add(item_id)
            merged.append(normalized)

    return merged


def _accident_sort_key(item):
    try:
        return parse_accident_datetime(item)
    except Exception:
        pass

    try:
        return datetime.fromtimestamp(int(str(item.get('id', '0')).strip()) / 1000.0)
    except Exception:
        return datetime.min


def _sort_accidents(records):
    return sorted(records or [], key=_accident_sort_key)


def publish_realtime_event(event_name, payload):
    message = json.dumps({
        'event': event_name,
        'payload': payload,
        'ts': now_local_datetime().strftime('%d/%m/%Y %H:%M:%S')
    }, ensure_ascii=False)

    with REALTIME_SUBSCRIBERS_LOCK:
        subscribers = list(REALTIME_SUBSCRIBERS)

    for sub_queue in subscribers:
        try:
            sub_queue.put_nowait(message)
        except Exception:
            # Falha em assinante isolado nao deve afetar os demais.
            pass


def _safe_error_excerpt(exc):
    """Return a short non-sensitive error excerpt for API responses/logs."""
    raw = str(exc or '').replace('\n', ' ').replace('\r', ' ').strip()
    if not raw:
        return 'Erro nao especificado'

    lowered = raw.lower()
    sensitive_markers = [
        'service_role',
        'authorization',
        'apikey',
        'bearer',
        'token',
    ]
    if any(marker in lowered for marker in sensitive_markers):
        return 'Erro de autenticacao/permissao no Supabase'

    return raw[:200]


def _local_load_accidents():
    ensure_exports_dir()
    if os.path.exists(ACCIDENTS_FILE):
        try:
            with open(ACCIDENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                loaded = _deserialize_accidents_payload(data)
                return [_normalize_accident_record(item) for item in loaded if isinstance(item, dict)]
        except json.JSONDecodeError:
            if os.path.exists(ACCIDENTS_BAK_FILE):
                with open(ACCIDENTS_BAK_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded = _deserialize_accidents_payload(data)
                    return [_normalize_accident_record(item) for item in loaded if isinstance(item, dict)]
        except RuntimeError:
            raise
    return []


def _local_save_accidents(accidents):
    validate_persistence_mode()
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


def _supabase_record_from_accident(accident):
    normalized = _normalize_accident_record(accident)
    created_at = None
    try:
        created_at = parse_accident_datetime(normalized).isoformat()
    except Exception:
        created_at = now_local_datetime().isoformat()

    return {
        'id': normalized['id'],
        'municipio_notificacao': normalized['municipioNotificacao'],
        'nome_notificante': normalized['nomeNotificante'],
        'endereco': normalized['endereco'],
        'veiculo_usuario': normalized['veiculoUsuario'],
        'registro_no_local_sinistro': normalized['registroNoLocalSinistro'],
        'registro_fora_local_descricao': normalized['registroForaLocalDescricao'],
        'sinistro_com_vitimas': normalized['sinistroComVitimas'],
        'quantidade_vitimas': normalized['quantidadeVitimas'],
        'sinistro_vitimas': normalized['sinistroVitimas'],
        'equipamentos_seguranca': normalized['equipamentosSeguranca'],
        'latitude': normalized['latitude'],
        'longitude': normalized['longitude'],
        'descricao': normalized['descricao'],
        'fotos': normalized['fotos'],
        'tempo_registro_segundos': normalized['tempoRegistroSegundos'],
        'data_hora': normalized['dataHora'],
        'photo_count': normalized['photoCount'],
        'created_at': created_at,
    }


def _accident_from_supabase_record(row):
    photos = row.get('fotos', [])
    if not isinstance(photos, list):
        photos = []
    return {
        'id': str(row.get('id', '')).strip(),
        'municipioNotificacao': str(row.get('municipio_notificacao', '')).strip(),
        'nomeNotificante': str(row.get('nome_notificante', '')).strip(),
        'endereco': str(row.get('endereco', '')).strip(),
        'veiculoUsuario': str(row.get('veiculo_usuario', '')).strip(),
        'sinistroComVitimas': str(row.get('sinistro_com_vitimas', '')).strip(),
        'quantidadeVitimas': str(row.get('quantidade_vitimas', '')).strip(),
        'sinistroVitimas': str(row.get('sinistro_vitimas', '')).strip(),
        'equipamentosSeguranca': str(row.get('equipamentos_seguranca', '')).strip(),
        'latitude': str(row.get('latitude', '')).strip(),
        'longitude': str(row.get('longitude', '')).strip(),
        'descricao': str(row.get('descricao', '')).strip(),
        'registroNoLocalSinistro': str(row.get('registro_no_local_sinistro', '')).strip(),
        'registroForaLocalDescricao': str(row.get('registro_fora_local_descricao', '')).strip(),
        'fotos': photos,
        'tempoRegistroSegundos': int(row.get('tempo_registro_segundos', 0) or 0),
        'dataHora': str(row.get('data_hora', '')).strip(),
        'photoCount': int(row.get('photo_count', len(photos)) or len(photos)),
    }


def _supabase_fetch_all_accidents():
    records = []
    offset = 0

    while True:
        query = (
            SUPABASE_CLIENT
            .table(SUPABASE_TABLE)
            .select('*')
        )
        try:
            response = query.order('created_at', desc=False).range(offset, offset + SUPABASE_PAGE_SIZE - 1).execute()
        except Exception as exc:
            if 'created_at' not in str(exc):
                raise
            response = query.range(offset, offset + SUPABASE_PAGE_SIZE - 1).execute()
        rows = response.data or []
        records.extend(_accident_from_supabase_record(row) for row in rows if isinstance(row, dict))

        if len(rows) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE

    return records


def _extract_missing_column_name(exc):
    message = str(exc or '')
    patterns = [
        r"Could not find the '([^']+)' column",
        r'column\s+"?([a-zA-Z0-9_]+)"?\s+does not exist',
        r"Could not find the field '([^']+)'",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def _supabase_upsert_resilient(payload):
    items = payload if isinstance(payload, list) else [payload]
    sanitized_items = [dict(item) for item in items]
    removed_columns = []

    while True:
        try:
            SUPABASE_CLIENT.table(SUPABASE_TABLE).upsert(sanitized_items, on_conflict='id').execute()
            return {'removedColumns': removed_columns}
        except Exception as exc:
            missing_column = _extract_missing_column_name(exc)
            if not missing_column:
                raise

            removed_any = False
            for item in sanitized_items:
                if missing_column in item:
                    item.pop(missing_column, None)
                    removed_any = True

            if not removed_any:
                raise

            if missing_column not in removed_columns:
                removed_columns.append(missing_column)
            print(f'[WARN] Coluna ausente no Supabase ignorada no upsert: {missing_column}')


def _supabase_insert_accident(accident):
    payload = _supabase_record_from_accident(accident)
    return _supabase_upsert_resilient(payload)


def sync_local_records_to_supabase(local_records=None, supabase_records=None, force=False):
    if not supabase_enabled():
        return {'enabled': False, 'synced': 0, 'pending': 0}

    global LAST_LOCAL_SUPABASE_SYNC_AT
    now_ts = time.time()

    with LOCAL_SUPABASE_SYNC_LOCK:
        if not force and (now_ts - LAST_LOCAL_SUPABASE_SYNC_AT) < LOCAL_SUPABASE_SYNC_INTERVAL_SECONDS:
            return {'enabled': True, 'synced': 0, 'pending': 0, 'skipped': 'throttled'}
        LAST_LOCAL_SUPABASE_SYNC_AT = now_ts

    local_items = local_records if local_records is not None else _local_load_accidents()
    if not local_items:
        return {'enabled': True, 'synced': 0, 'pending': 0}

    if force:
        payload = [_supabase_record_from_accident(item) for item in local_items if str(item.get('id', '')).strip()]
        if not payload:
            return {'enabled': True, 'synced': 0, 'pending': 0}
        upsert_info = _supabase_upsert_resilient(payload)
        print(f'[INFO] Sincronizacao completa local->Supabase: {len(payload)} registro(s) enviados.')
        return {'enabled': True, 'synced': len(payload), 'pending': len(payload), **upsert_info}

    remote_items = supabase_records if supabase_records is not None else _supabase_fetch_all_accidents()
    remote_ids = {str(item.get('id', '')).strip() for item in remote_items if str(item.get('id', '')).strip()}

    pending = [item for item in local_items if str(item.get('id', '')).strip() and str(item.get('id', '')).strip() not in remote_ids]
    if not pending:
        return {'enabled': True, 'synced': 0, 'pending': 0}

    payload = [_supabase_record_from_accident(item) for item in pending]
    upsert_info = _supabase_upsert_resilient(payload)
    print(f'[INFO] Sincronizacao local->Supabase: {len(payload)} registro(s) enviados.')
    return {'enabled': True, 'synced': len(payload), 'pending': len(pending), **upsert_info}


def bootstrap_supabase_from_local():
    if not supabase_enabled() or not SUPABASE_BOOTSTRAP_LOCAL:
        return {'enabled': supabase_enabled(), 'bootstrapped': False, 'records': 0}

    try:
        response = SUPABASE_CLIENT.table(SUPABASE_TABLE).select('id').limit(1).execute()
        existing = response.data or []
    except Exception:
        return {'enabled': True, 'bootstrapped': False, 'records': 0}

    if existing:
        return {'enabled': True, 'bootstrapped': False, 'records': 0}

    local_records = _local_load_accidents()
    if not local_records:
        return {'enabled': True, 'bootstrapped': False, 'records': 0}

    payload = [_supabase_record_from_accident(item) for item in local_records if item.get('id')]
    if not payload:
        return {'enabled': True, 'bootstrapped': False, 'records': 0}

    SUPABASE_CLIENT.table(SUPABASE_TABLE).insert(payload).execute()
    return {'enabled': True, 'bootstrapped': True, 'records': len(payload)}


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

    now = now_local_datetime()
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
        return now_local_datetime()


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


def format_duration_hms(seconds_value):
    try:
        total = max(0, int(seconds_value))
    except (TypeError, ValueError):
        total = 0
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f'{hours:02d}h {minutes:02d}m {seconds:02d}s'


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
        'registro_no_local_sinistro',
        'registro_fora_local_descricao',
        'sinistro_com_vitimas',
        'quantidade_vitimas',
        'sinistro_vitimas',
        'equipamentos_seguranca',
        'latitude',
        'longitude',
        'quantidade_fotos',
        'tempo_registro_segundos',
        'tempo_registro_formatado'
    ]

    with open(file_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for item in accidents:
            photos = item.get('fotos') if isinstance(item.get('fotos'), list) else []
            tempo_segundos = item.get('tempoRegistroSegundos', 0)
            writer.writerow({
                'id': item.get('id', ''),
                'periodo': label,
                'data_hora_registro': item.get('dataHora', ''),
                'municipio_notificacao': item.get('municipioNotificacao', ''),
                'nome_notificante': item.get('nomeNotificante', ''),
                'endereco': item.get('endereco', ''),
                'veiculo_usuario': item.get('veiculoUsuario', ''),
                'registro_no_local_sinistro': item.get('registroNoLocalSinistro', ''),
                'registro_fora_local_descricao': item.get('registroForaLocalDescricao', ''),
                'sinistro_com_vitimas': item.get('sinistroComVitimas', ''),
                'quantidade_vitimas': item.get('quantidadeVitimas', ''),
                'sinistro_vitimas': item.get('sinistroVitimas', ''),
                'equipamentos_seguranca': item.get('equipamentosSeguranca', ''),
                'latitude': item.get('latitude', ''),
                'longitude': item.get('longitude', ''),
                'quantidade_fotos': len(photos),
                'tempo_registro_segundos': tempo_segundos,
                'tempo_registro_formatado': format_duration_hms(tempo_segundos)
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
  <title>Mapa Diário de Acidentes - {label}</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" crossorigin=\"\"/>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; }}
    header {{ padding: 12px 16px; background: #0b3d91; color: #fff; }}
    #map {{ height: calc(100vh - 64px); width: 100%; }}
  </style>
</head>
<body>
  <header>
    <strong>Mapa Diário de Acidentes - {label}</strong>
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
        `Município: ${{p.municipioNotificacao || '-'}}<br/>` +
        `Notificante: ${{p.nomeNotificante || '-'}}<br/>` +
        `Veículo/Usuário: ${{p.veiculoUsuario || '-'}}<br/>` +
            `Sinistro com vítimas: ${{p.sinistroComVitimas || '-'}}<br/>` +
            `Quantidade de vítimas: ${{p.quantidadeVitimas || '-'}}<br/>` +
            `Vítimas: ${{p.sinistroVitimas || '-'}}`
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
    now_dt = now_local_datetime()
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
    now = now_local_datetime()
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
        'registro_no_local_sinistro',
        'registro_fora_local_descricao',
        'sinistro_com_vitimas',
        'quantidade_vitimas',
        'sinistro_vitimas',
        'equipamentos_seguranca',
        'latitude',
        'longitude',
        'quantidade_fotos',
        'tempo_registro_segundos',
        'tempo_registro_formatado'
    ]

    with open(archived_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for item in accidents:
            dt = parse_accident_datetime(item)
            photos = item.get('fotos') if isinstance(item.get('fotos'), list) else []
            tempo_segundos = item.get('tempoRegistroSegundos', 0)
            writer.writerow({
                'id': item.get('id', ''),
                'periodo': period_label(dt, period),
                'data_hora_registro': item.get('dataHora', ''),
                'municipio_notificacao': item.get('municipioNotificacao', ''),
                'nome_notificante': item.get('nomeNotificante', ''),
                'endereco': item.get('endereco', ''),
                'veiculo_usuario': item.get('veiculoUsuario', ''),
                'registro_no_local_sinistro': item.get('registroNoLocalSinistro', ''),
                'registro_fora_local_descricao': item.get('registroForaLocalDescricao', ''),
                'sinistro_com_vitimas': item.get('sinistroComVitimas', ''),
                'quantidade_vitimas': item.get('quantidadeVitimas', ''),
                'sinistro_vitimas': item.get('sinistroVitimas', ''),
                'equipamentos_seguranca': item.get('equipamentosSeguranca', ''),
                'latitude': item.get('latitude', ''),
                'longitude': item.get('longitude', ''),
                'quantidade_fotos': len(photos),
                'tempo_registro_segundos': tempo_segundos,
                'tempo_registro_formatado': format_duration_hms(tempo_segundos)
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
    local_records = _local_load_accidents()

    if supabase_enabled():
        try:
            supabase_records = _supabase_fetch_all_accidents()
            try:
                sync_local_records_to_supabase(local_records=local_records, supabase_records=supabase_records)
            except Exception as sync_exc:
                print(f'[WARN] Falha ao sincronizar registros locais para Supabase: {sync_exc}')
            merged_records = _sort_accidents(_merge_accident_records(supabase_records, local_records))

            # Mantem cache local alinhado para evitar sumico visual em instabilidades.
            if merged_records:
                _local_save_accidents(merged_records)

            return merged_records
        except Exception as exc:
            print(f'[WARN] Falha ao ler Supabase; usando fallback local. Motivo: {exc}')
    return _sort_accidents(local_records)

def save_accidents(accidents):
    normalized = [_normalize_accident_record(item) for item in accidents if isinstance(item, dict)]
    _local_save_accidents(normalized)


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
    supabase_diag = get_supabase_diagnostics()
    supabase_ready = True
    if supabase_diag['configured']:
        supabase_ready = bool(supabase_diag['healthy'])

    persistence_ok = (
        (supabase_enabled() and supabase_ready)
        or (not REQUIRE_PERSISTENT_STORAGE)
        or DATA_DIR_PERSISTENT
    )
    payload = {
        'status': 'healthy' if persistence_ok else 'degraded',
        'storage': {
            'mode': storage_mode_label(),
            'supabaseConfigured': supabase_diag['configured'],
            'supabaseEnabled': supabase_enabled(),
            'supabaseHealthy': supabase_diag['healthy'],
            'supabaseTable': SUPABASE_TABLE if supabase_configured() else '',
            'supabaseError': supabase_diag['error'] if supabase_diag['configured'] else ''
        },
        'persistence': {
            'dataDir': DATA_DIR,
            'isPersistent': DATA_DIR_PERSISTENT,
            'requirePersistentStorage': REQUIRE_PERSISTENT_STORAGE,
        }
    }
    status_code = 200 if persistence_ok else 503
    return jsonify(payload), status_code

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
    return no_cache_response(jsonify(accidents))


@app.route('/api/accidents/meta', methods=['GET'])
def get_accidents_meta():
    accidents = load_accidents()
    latest = accidents[-1] if accidents else {}
    latest_id = str(latest.get('id', '')).strip()
    latest_data_hora = str(latest.get('dataHora', '')).strip()
    payload = {
        'total': len(accidents),
        'latestId': latest_id,
        'latestDataHora': latest_data_hora,
        'fingerprint': f'{len(accidents)}:{latest_id}:{latest_data_hora}'
    }
    return no_cache_response(jsonify(payload))


@app.route('/api/accidents/stream', methods=['GET'])
def stream_accidents():
    @stream_with_context
    def event_stream():
        subscriber_queue = Queue(maxsize=100)
        with REALTIME_SUBSCRIBERS_LOCK:
            REALTIME_SUBSCRIBERS.append(subscriber_queue)

        yield 'event: ready\ndata: {"event":"ready"}\n\n'

        try:
            while True:
                try:
                    payload = subscriber_queue.get(timeout=20)
                    yield f'event: update\ndata: {payload}\n\n'
                except Empty:
                    yield ': keepalive\n\n'
        finally:
            with REALTIME_SUBSCRIBERS_LOCK:
                if subscriber_queue in REALTIME_SUBSCRIBERS:
                    REALTIME_SUBSCRIBERS.remove(subscriber_queue)

    response = Response(event_stream(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


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


@app.route('/api/admin/spreadsheets-link', methods=['GET'])
def admin_spreadsheets_link():
    if not is_admin_request():
        return require_admin_response()

    if not SUPABASE_SPREADSHEETS_URL:
        return jsonify({
            'success': False,
            'error': 'SUPABASE_SPREADSHEETS_URL nao configurada no servidor'
        }), 503

    return jsonify({
        'success': True,
        'url': SUPABASE_SPREADSHEETS_URL
    })


@app.route('/api/admin/supabase-status', methods=['GET'])
def admin_supabase_status():
    if not is_admin_request():
        return require_admin_response()

    diagnostics = get_supabase_diagnostics()
    http_status = 200 if diagnostics['healthy'] or not diagnostics['configured'] else 503
    return jsonify({
        'success': diagnostics['healthy'],
        'storageMode': storage_mode_label(),
        'diagnostics': diagnostics,
    }), http_status

@app.route('/api/accidents', methods=['POST'])
def add_accident():
    try:
        data = request.get_json() or {}

        def split_multi_values(raw_value):
            if isinstance(raw_value, list):
                return [str(item).strip() for item in raw_value if str(item).strip()]
            text = str(raw_value or '').strip()
            if not text:
                return []
            return [part.strip() for part in text.split('|') if part.strip()]

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
            return jsonify({'error': 'Campo sinistroComVitimas inválido. Use Sim ou Não.'}), 400

        veiculo_usuario_values = split_multi_values(data.get('veiculoUsuario', ''))
        if not veiculo_usuario_values:
            return jsonify({'error': 'Selecione ao menos uma opção em Veículo/Usuário.'}), 400

        registro_no_local_sinistro = str(data.get('registroNoLocalSinistro', '')).strip()
        if registro_no_local_sinistro not in {'Sim', 'Não'}:
            return jsonify({'error': 'Informe se o registro está sendo feito no local do sinistro.'}), 400

        registro_fora_local_descricao = str(data.get('registroForaLocalDescricao', '')).strip()
        if registro_no_local_sinistro == 'Não' and not registro_fora_local_descricao:
            return jsonify({'error': 'Informe a breve descrição quando o registro não for feito no local do sinistro.'}), 400
        if registro_no_local_sinistro == 'Sim':
            registro_fora_local_descricao = ''

        quantidade_vitimas_values = split_multi_values(data.get('quantidadeVitimas', ''))
        allowed_victim_options = {
            '1 vítima sem gravidade',
            '1 vítima com gravidade',
            '2 vítimas ou mais sem gravidade',
            '2 vítimas ou mais com gravidade',
            'Vítima fatal',
        }
        if any(value not in allowed_victim_options for value in quantidade_vitimas_values):
            return jsonify({'error': 'Perfil de vítimas inválido.'}), 400
        quantidade_vitimas = ' | '.join(quantidade_vitimas_values)
        if sinistro_com_vitimas == 'Sim' and not quantidade_vitimas_values:
            return jsonify({'error': 'Selecione pelo menos uma opção no perfil das vítimas.'}), 400
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
            'id': str(int(now_local_datetime().timestamp() * 1000)),
            'municipioNotificacao': data['municipioNotificacao'].strip(),
            'nomeNotificante': data['nomeNotificante'].strip(),
            'endereco': data['endereco'].strip(),
            'veiculoUsuario': ' | '.join(veiculo_usuario_values),
            'sinistroComVitimas': sinistro_com_vitimas,
            'quantidadeVitimas': quantidade_vitimas,
            'sinistroVitimas': sinistro_vitimas,
            'equipamentosSeguranca': data['equipamentosSeguranca'].strip(),
            'latitude': data['latitude'].strip(),
            'longitude': data['longitude'].strip(),
            'descricao': registro_fora_local_descricao or str(data.get('descricao', '')).strip(),
            'registroNoLocalSinistro': registro_no_local_sinistro,
            'registroForaLocalDescricao': registro_fora_local_descricao,
            'fotos': photos,
            'tempoRegistroSegundos': elapsed_seconds,
            'dataHora': now_local_datetime().strftime('%d/%m/%Y %H:%M:%S'),
            'photoCount': len(photos)
        }

        # Espelho local e persistencia imediata para nao perder visibilidade no app.
        local_records = _local_load_accidents()
        local_records = _merge_accident_records(local_records, [accident])
        save_accidents(local_records)

        supabase_warning = ''
        supabase_warning_excerpt = ''
        supabase_warning_type = ''
        supabase_removed_columns = []
        if supabase_enabled():
            try:
                upsert_info = _supabase_insert_accident(accident)
                supabase_removed_columns = upsert_info.get('removedColumns', [])
            except Exception as exc:
                supabase_warning = str(exc)
                supabase_warning_excerpt = _safe_error_excerpt(exc)
                supabase_warning_type = type(exc).__name__
                print(f'[WARN] Falha ao inserir no Supabase; registro mantido no espelho local. Motivo: {exc}')

        accidents = load_accidents()
        ensure_scheduled_daily_exports(accidents)
        generate_all_exports(accidents)
        backup_accidents_to_github(accidents)

        response = {
            'success': True,
            'message': 'Acidente reportado com sucesso!',
            'id': accident['id']
        }
        if supabase_warning:
            response['warning'] = 'Registro salvo localmente; sincronizacao com Supabase pendente.'
            response['warningType'] = supabase_warning_type or 'SupabaseInsertError'
            response['warningDetail'] = supabase_warning_excerpt
        elif supabase_removed_columns:
            response['warning'] = 'Registro enviado ao Supabase com compatibilidade para tabela antiga.'
            response['warningType'] = 'SupabaseSchemaCompatibility'
            response['warningDetail'] = 'Colunas ausentes ignoradas: ' + ', '.join(supabase_removed_columns)

        publish_realtime_event('accident-created', {
            'id': accident['id'],
            'dataHora': accident['dataHora']
        })

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accidents/<accident_id>', methods=['DELETE'])
def delete_accident(accident_id):
    return jsonify({
        'success': False,
        'error': 'Remocao desativada. Os registros sao permanentes.'
    }), 403

validate_persistence_mode()
bootstrap_supabase_from_local()
if supabase_enabled():
    try:
        sync_local_records_to_supabase(force=True)
    except Exception as startup_sync_exc:
        print(f'[WARN] Falha na sincronizacao inicial local->Supabase: {startup_sync_exc}')
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