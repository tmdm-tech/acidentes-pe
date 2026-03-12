# 🚀 Guia de Deploy Online do ObservaTrânsito

Siga as instruções abaixo para colocar seu app online e acessível de qualquer lugar!

## Opção 1: Deploy no Render (RECOMENDADO - Gratuito)

### Passo 1: Preparar o Repositório Git

```bash
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Inicializar git (se não tiver)
git init

# Adicionar todos os arquivos
git add .

# Fazer commit
git commit -m "Initial commit - ObservaTrânsito"
```

### Passo 2: Criar Conta no Render

1. Acesse https://render.com
2. Clique em "Sign Up" (cadastre-se)
3. Use email/GitHub/GitLab
4. Confirme seu email

### Passo 3: Conectar GitHub

1. No dashboard do Render, vá em **Dashboard**
2. Clique em **New +**
3. Selecione **Web Service**
4. Escolha **Build and deploy from a Git repository**
5. Conecte seu GitHub:
   - Clique em **Connect account**
   - Autorize o Render no GitHub
   - Selecione o repositório `acidentes_pe`

### Passo 4: Configurar o Deploy

Na página de criação do Web Service:

- **Name**: `observatrafego` (ou outro nome)
- **Region**: Choose one (qualquer uma)
- **Branch**: `main` ou `master`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn server:app --bind 0.0.0.0:$PORT`
- **Instance Type**: Free (gratuito)
- **Plan**: Free

Clique em **Create Web Service**

### Passo 5: Acompanhar o Deploy

- Você verá logs do deploy
- Quando terminar, terá uma URL como `https://observatrafego.onrender.com`

---

## Opção 2: Deploy no Railway (ALTERNATIVA - Gratuito)

### Passo 1: Criar Conta

1. Acesse https://railway.app
2. Clique em **Start Project**
3. Faça login com GitHub

### Passo 2: Conectar Repositório

1. Clique em **Create New**
2. Selecione **GitHub Repo**
3. Selecione seu repositório `acidentes_pe`

### Passo 3: Configurar Variáveis

1. Vá em **Variables**
2. Nenhuma variável especial necessária

### Passo 4: Deploy Automático

O Railway automaticamente:
- Detecta `requirements.txt`
- Executa `pip install`
- Roda o app

---

## ⚠️ Antes de Fazer Deploy

Certifique-se de que:

1. ✅ Arquivo `requirements.txt` existe
2. ✅ Arquivo `Procfile` existe
3. ✅ Arquivo `server.py` está correto
4. ✅ Pasta `web/` com `index_simple.html` existe
5. ✅ Arquivo `manifest.json` foi atualizado

Verifique:
```bash
ls -la requirements.txt Procfile server.py web/index_simple.html web/manifest.json
```

---

## 🔄 Atualizar App Online

Depois de fazer mudanças locais:

```bash
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Adicionar mudanças
git add .

# Fazer commit
git commit -m "Atualização: sua mensagem aqui"

# Enviar para GitHub
git push origin main
```

O app online será atualizado automaticamente! 🎉

---

## 📱 Acessar no Celular (App Online)

Depois de fazer deploy:

1. **URL do App**: `https://seu-app.onrender.com`
2. **Abrir no celular**: Copiar URL e abrir no navegador
3. **Instalar como App**: 
   - Chrome/Android: Toque **⋮** → **Instalar app**
   - Safari/iOS: Toque **Compartilhar** → **Adicionar à Tela Inicial**

---

## 🔗 Teste Local Antes de Deploy

Para testar como se fosse online:

```bash
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Instalar gunicorn
pip3 install gunicorn

# Rodar localmente como em produção
gunicorn server:app --bind 0.0.0.0:8000
```

Acesse: `http://localhost:8000`

---

## 📊 Dados do App

### Arquivo de Dados (accidents.json)

O arquivo `accidents.json` armazena todos os acidentes localmente no servidor.

**Backup dos Dados:**

```bash
# Copiar arquivo de dados para backup
cp accidents.json accidents_backup_$(date +%Y%m%d_%H%M%S).json
```

---

## 🐛 Troubleshooting

**App não carrega no Render:**
- Verifique logs no dashboard Render
- Confirme que `requirements.txt` tem Flask e Gunicorn
- Teste localmente com `gunicorn server:app`

**PWA não instala:**
- Certifique-se de acessar via HTTPS (Render fornece)
- Manifesto em `web/manifest.json` precisa estar correto
- Cache do navegador: Ctrl+Shift+Delete

**Dados não salvam:**
- No Render free, dados em disco são perdidos ao reiniciar
- Solução: Usar banco de dados (MongoDB Atlas gratuito)

---

## 💾 Próxima Etapa: Banco de Dados Persistente

Se quiser que dados persistam mesmo após reinicializações:

```bash
pip3 install pymongo
```

Adicionar MongoDB Atlas (gratuito):
1. https://www.mongodb.com/cloud/atlas
2. Criar conta
3. Cluster gratuito
4. Modificar `server.py` para usar MongoDB

---

**Seu app estará ONLINE e ACESSÍVEL DE QUALQUER LUGAR!** 🌍🎉