#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory
import json
import os
from datetime import datetime
import socket

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

# Arquivo para armazenar acidentes
ACCIDENTS_FILE = 'accidents.json'
WEB_DIR = 'web'
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
MAX_PHOTOS = 5
MAX_PHOTO_CHARS = 1_200_000

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
    return jsonify(accidents)

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
            'dataHora': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'photoCount': len(photos)
        }

        # Salvar acidente
        accidents = load_accidents()
        accidents.append(accident)
        save_accidents(accidents)

        return jsonify({'success': True, 'message': 'Acidente reportado com sucesso!', 'id': accident['id']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accidents/<accident_id>', methods=['DELETE'])
def delete_accident(accident_id):
    try:
        accidents = load_accidents()
        accidents = [a for a in accidents if a['id'] != accident_id]
        save_accidents(accidents)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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