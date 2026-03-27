#!/bin/bash

# Script para configurar Git e fazer primeiro commit
# Este script prepara o projeto para deploy online

cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

echo "🚀 Configurando Git para Deploy..."
echo ""

# Verificar se git está instalado
if ! command -v git &> /dev/null; then
    echo "❌ Git não está instalado"
    echo "Instale em: https://git-scm.com"
    exit 1
fi

# Verificar se já é um repositório git
if [ ! -d .git ]; then
    echo "📦 Inicializando repositório Git..."
    git init
    git config user.name "Rede Vítima"
    git config user.email "dev@redevitima.com"
else
    echo "✅ Repositório Git já existe"
fi

echo ""
echo "📝 Adicionando arquivos..."
git add .

echo ""
echo "📋 Status atual:"
git status

echo ""
echo "💾 Fazendo commit inicial..."
git commit -m "Rede Vítima - App de reporte de acidentes

Features:
- Geolocalização GPS
- Upload de fotos
- Interface PWA
- Armazenamento centralizado
- Deploy automático

Pronto para: https://render.com ou https://railway.app" 2>/dev/null || echo "✅ Já tem commits"

echo ""
echo "✅ Git configurado!"
echo ""
echo "📌 Próximos passos:"
echo "1. Criar repositório no GitHub: https://github.com/new"
echo "2. Copiar os comandos para adicionar remote:"
echo "   git remote add origin https://github.com/seu-usuario/acidentes_pe.git"
echo "   git push -u origin main"
echo "3. Ir para https://render.com e conectar o repositório"
echo ""
echo "Documentação completa em: DEPLOY.md"