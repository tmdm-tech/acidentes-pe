# 🌍 Como Colocar o App ONLINE (Passo a Passo)

Seu app será acessível de **QUALQUER LUGAR** por QUALQUER PESSOA com internet!

## ⚡ Resumo Rápido

1. Crie conta no **GitHub** (grátis)
2. Suba o código para GitHub
3. Crie conta no **Render** (grátis)
4. Conecte seu GitHub ao Render
5. Pronto! App online e acessível 🎉

---

## 📋 Passo 1: Criar Repositório no GitHub

### Acesse GitHub

- Vá para: https://github.com
- Clique em **Sign up** (cadastro)
- Use email pessoal
- Confirme email

### Crie um Novo Repositório

1. Clique em **+** (canto superior direito)
2. Selecione **New repository**
3. Preencha:
   - **Repository name**: `acidentes-pe` ou `observatrafego`
   - **Description**: `App de sinistro de transito`
   - **Public** (assim qualquer um consegue acessar)
   - Desmarque "Add a README.md" (já tem)
4. Clique **Create repository**

### Copie as URLs que aparecem

Você verá algo assim:
```
git remote add origin https://github.com/seu-usuario/acidentes-pe.git
git branch -M main
git push -u origin main
```

---

## 📦 Passo 2: Enviar Código para GitHub

No terminal, execute (na pasta do projeto):

```bash
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Se não tiver git inicializado, execute:
./setup_git.sh

# Adicionar o repositório remoto (copie do GitHub)
git remote add origin https://github.com/SEU-USUARIO/acidentes-pe.git

# Renomear branch para 'main'
git branch -M main

# Enviar código para GitHub
git push -u origin main
```

**✅ Pronto! Seu código está no GitHub!**

---

## 🚀 Passo 3: Deploy no Render (Serviço Online Grátis)

### 1. Crie conta no Render

- Vá para: https://render.com
- Clique **Sign up**
- Use GitHub (mais fácil!) ou email

### 2. Conecte seu GitHub

- Dashboard do Render
- Clique **New +** → **Web Service**
- Selecione **Build and deploy from a Git repository**
- Clique **Connect account** (autorize Render no GitHub)

### 3. Selecione seu Repositório

- Escolha: `acidentes-pe` ou qualquer que nomeou

### 4. Configure o Deploy

Preencha os campos:

```
Name: observatrafego (ou outro nome)
Region: (qualquer uma, recomendo próxima)
Branch: main
Build Command: pip install -r requirements.txt
Start Command: gunicorn server:app --bind 0.0.0.0:$PORT
Instance Type: Free
Plan: Free
```

### 5. Clique **Create Web Service**

Espere 3-5 minutos enquanto faz deploy...

---

## ✅ SEU APP ESTÁ ONLINE!

Quando terminar, você verá:
- Uma URL como: `https://observatrafego.onrender.com`
- Copie e compartilhe essa URL!

---

## 📱 Como Usar no Celular

### Acessar como Website

1. Abra o navegador no celular
2. Cole a URL: `https://observatrafego.onrender.com`
3. Toque em "Instalar app" ou "Adicionar à tela inicial"

### Instalar como App (PWA)

**Android (Chrome):**
1. Abra em Chrome
2. Toque em **⋮** (três pontos)
3. Selecione **Instalar app**
4. Aparecerá na tela inicial como app!

**iPhone (Safari):**
1. Abra em Safari
2. Toque em **Compartilhar**
3. Selecione **Adicionar à Tela Inicial**
4. Aparecerá na tela inicial como app!

---

## 🔄 Atualizar o App Online

Depois que estiver online, se fazer mudanças:

```bash
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"

# Fazer suas mudanças no código...

# Enviar para GitHub (automático faz deploy)
git add .
git commit -m "Descrição da mudança"
git push
```

**Render automaticamente redeploy a cada push!**

---

## 🔗 Compartilhar com Outras Pessoas

Basta compartilhar a URL:
```
https://observatrafego.onrender.com
```

Qualquer pessoa com internet consegue:
- ✅ Acessar o app
- ✅ Reportar acidentes
- ✅ Ver fotos e dados
- ✅ Instalar como app no celular

---

## 💾 Dados do App Online

Os acidentes reportados são salvos no servidor!

**Problema:** No Render free, dados podem ser perdidos ao reiniciar

**Solução (opcional):** 
- Usar MongoDB Atlas (banco de dados gratuito)
- Dados persistem para sempre
- Requer 10 linhas de código extra

---

## 🐛 Se der Erro no Deploy

### 1. Verifique os Logs

No Render:
- Dashboard
- Seu Web Service
- Aba **Logs**
- Procure por erros

### 2. Problemas Comuns

**"requirements.txt not found"**
- Confirme arquivo `requirements.txt` existe na raiz

**"gunicorn command not found"**
- Adicione `Gunicorn` em `requirements.txt`

**"Port already in use"**
- Não se preocupe, Render escolhe uma porta livre

### 3. Teste Localmente Primeiro

```bash
pip3 install gunicorn
gunicorn server:app --bind 0.0.0.0:8000
```

Abra: `http://localhost:8000`

---

## 🎯 Arquivos Necessários para Deploy

✅ `requirements.txt` - Dependências Python
✅ `Procfile` - Como iniciar app
✅ `server.py` - Seu app Flask
✅ `web/index_simple.html` - Interface
✅ `web/manifest.json` - Configuração PWA
✅ `.git/` - Repositório Git

Verifique:
```bash
ls -la requirements.txt Procfile server.py web/index_simple.html web/manifest.json
```

---

## 🎉 PRONTO!

Seu app agora é:
- ✅ **Online** - Acessível de qualquer lugar
- ✅ **Gratuito** - Sem custo no Render
- ✅ **Instalável** - Como app no celular
- ✅ **Compartilhável** - Uma URL para todo mundo

**Compartilhe a URL e deixe pessoas reportarem acidentes de qualquer lugar!** 🚗📱