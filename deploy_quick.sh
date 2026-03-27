#!/bin/bash

# Script de Deploy Rápido
# Execute este script para colocar o app online em minutos!

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║       🚀 Rede Vítima - Deploy Rápido Online 🚀         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

PROJECT_DIR="/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd "$PROJECT_DIR"

echo -e "${BLUE}📋 Verificando arquivos necessários...${NC}"
echo ""

# Verificar arquivos
FILES=("requirements.txt" "Procfile" "server.py" "web/index_simple.html" "web/manifest.json")

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $file"
    else
        echo -e "${YELLOW}⚠️${NC}  $file FALTANDO"
    fi
done

echo ""
echo -e "${BLUE}🔧 Configurando Git...${NC}"
echo ""

# Inicializar Git se não tiver
if [ ! -d .git ]; then
    git init
    git config user.name "Rede Vítima"
    git config user.email "dev@redevitima.com"
    echo -e "${GREEN}✅${NC} Git inicializado"
else
    echo -e "${GREEN}✅${NC} Git já configurado"
fi

echo ""
echo -e "${BLUE}📦 Preparando arquivos...${NC}"
git add .
git commit -m "Deploy: Rede Vítima" 2>/dev/null || true
echo -e "${GREEN}✅${NC} Arquivos prontos"

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}PRÓXIMAS ETAPAS:${NC}"
echo ""
echo "1️⃣  Crie conta no GitHub (https://github.com)"
echo "   - Clique em 'Sign up'"
echo ""
echo "2️⃣  Crie um novo repositório"
echo "   - Nome: acidentes-pe"
echo "   - Public"
echo ""
echo "3️⃣  Execute estes comandos no terminal:"
echo ""
echo -e "${YELLOW}git remote add origin https://github.com/SEU-USUARIO/acidentes-pe.git${NC}"
echo -e "${YELLOW}git branch -M main${NC}"
echo -e "${YELLOW}git push -u origin main${NC}"
echo ""
echo "   (Substitua SEU-USUARIO pelo seu usuário GitHub)"
echo ""
echo "4️⃣  Crie conta no Render (https://render.com)"
echo "   - Sign up com GitHub"
echo ""
echo "5️⃣  Crie um novo Web Service"
echo "   - Conecte seu repositório GitHub"
echo "   - Build: pip install -r requirements.txt"
echo "   - Start: gunicorn server:app --bind 0.0.0.0:\$PORT"
echo ""
echo "6️⃣  Pronto! Seu app está ONLINE! 🎉"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📖 Para mais detalhes, leia:${NC}"
echo "   - DEPLOY_SIMPLES.md (Guia em português)"
echo "   - DEPLOY.md (Guia completo)"
echo ""
echo -e "${GREEN}✅ Setup concluído!${NC}"
echo ""