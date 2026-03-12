"""
Configuração de Produção do ObservaTrânsito
Este arquivo facilita o deployment em ambiente de produção
"""

import os

# Detectar ambiente
ENV = os.environ.get('FLASK_ENV', 'development')
DEBUG = ENV == 'development'

# Configuração de banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///accidents.db')

# Configuração de segurança
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Configuração de CORS
CORS_ORIGINS = [
    'http://localhost:8000',
    'http://localhost:3000',
    'http://127.0.0.1:8000',
]

# Tentar adicionar URL do Render, Railway, etc
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
if RENDER_EXTERNAL_URL:
    CORS_ORIGINS.append(RENDER_EXTERNAL_URL)

RAILWAY_STATIC_URL = os.environ.get('RAILWAY_STATIC_URL')
if RAILWAY_STATIC_URL:
    CORS_ORIGINS.append(RAILWAY_STATIC_URL)

# Configuração de armazenamento de arquivos
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB máximo

# Criar pasta de uploads se não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)