# ObservaTrânsito - App de Sinistro de Trânsito

Aplicativo web para reportar acidentes de trânsito em Pernambuco, com funcionalidades de localização GPS, upload de fotos e armazenamento centralizado de dados.

## 🚀 Funcionalidades

- ✅ Marcação de localização GPS automática
- ✅ Upload de fotos do acidente
- ✅ Coleta de dados do usuário (nome e CPF)
- ✅ Interface responsiva com gradiente verde-amarelo-azul-vermelho
- ✅ Instalação como app móvel (PWA)
- ✅ Acesso via rede local (qualquer dispositivo)
- ✅ Armazenamento centralizado de dados

## 📱 Como Usar

### 1. Iniciar o Servidor

Execute o script de inicialização:

```bash
./start_server.sh
```

Ou manualmente:

```bash
cd "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe"
python3 server.py
```

### 2. Acessar o App

- **Local**: http://localhost:8000
- **Rede**: http://[SEU_IP]:8000

Para descobrir seu IP local:
```bash
ipconfig getifaddr en0
```

### 3. Instalar no Celular

1. Abra o navegador no celular
2. Acesse o endereço do servidor
3. Toque em "Adicionar à tela inicial" ou "Instalar app"
4. O app aparecerá como um ícone na tela inicial

## 🛠️ Arquitetura

- **Frontend**: HTML5, CSS3, JavaScript (PWA)
- **Backend**: Flask (Python)
- **Armazenamento**: JSON local
- **Geolocalização**: API do navegador

## 🍎 Publicação na Apple App Store

Este repositório já foi preparado com base de empacotamento iOS via Capacitor.

Siga o guia completo em:

- `APP_STORE_IOS_PREPARACAO.md`

Resumo rápido:

1. Instalar Xcode no Mac (App Store)
2. Rodar `npm install`, `npm run ios:init`, `npm run ios:sync`, `npm run ios:open`
3. Configurar assinatura (`Signing & Capabilities`) no Xcode
4. Gerar archive e enviar para App Store Connect

## 📁 Estrutura do Projeto

```
acidentes_pe/
├── web/
│   ├── index_simple.html    # Interface principal
│   ├── manifest.json        # Configuração PWA
│   ├── icons/              # Ícones do app
│   └── favicon.png
├── server.py               # API Flask
├── start_server.sh        # Script de inicialização
└── accidents.json          # Dados dos acidentes
```

## 🔧 Requisitos

- Python 3.6+
- Flask (`pip3 install flask`)
- Navegador moderno com suporte a geolocalização

## 📊 Dados Coletados

Cada relatório de acidente inclui:
- Nome e CPF do usuário
- Coordenadas GPS (latitude/longitude)
- Fotos do acidente
- Data e hora do sinistro
- Status do acidente

## 🔒 Privacidade

- Dados armazenados localmente no servidor
- Acesso restrito à rede local
- Não há transmissão para servidores externos

## ☁️ Configuração no Render (o que faltava)

Para a versão nova funcionar no Render com persistência permanente:

1. **Build Command**
	- `pip install -r requirements.txt`
2. **Start Command**
	- `python -m gunicorn server:app --bind 0.0.0.0:$PORT`
3. **Environment Variable**
	- `DATA_DIR=/var/data`
4. **Persistent Disk**
	- Mount path: `/var/data`

Com isso, o app grava `accidents.json` e `exports/` em disco persistente e os registros não se perdem em restart/deploy.

Recursos já ativos:

- Geração diária automática às 08:00 do dia seguinte
- Planilha diária
- Mapa diário de Pernambuco com pontos dos acidentes
- Registros permanentes (remoção desativada)

## 🔐 Controle restrito ao administrador

As funcoes de manipulacao de registros (download de planilhas/mapas e backup) sao exclusivas do administrador.

Configure no Render:

- `ADMIN_ACCESS_KEY=uma_chave_forte_somente_sua`

No app:

1. Clique em **Entrar como administrador**.
2. Informe sua chave.
3. Os botoes de download e backup serao habilitados apenas para voce.

Usuarios comuns:

- conseguem apenas visualizar e registrar sinistros.
- nao conseguem baixar planilhas/mapas.

## 🗄️ Armazenamento privado opcional no GitHub

Para manter uma copia privada automatica dos registros no GitHub (repo privado), configure no Render:

- `GITHUB_BACKUP_REPO=seu-user/seu-repo-privado`
- `GITHUB_BACKUP_TOKEN=seu_token_com_permissao_repo`
- `GITHUB_BACKUP_BRANCH=main` (opcional)
- `GITHUB_BACKUP_PATH=observa_backup` (opcional)

Depois, no app em modo administrador, use o botao **Backup privado (GitHub)**.

## 🛡️ Ambiente seguro recomendado (producao)

Para elevar a seguranca do armazenamento dos dados coletados:

1. **Ative criptografia em disco dos registros (server-side):**

- Gere a chave localmente:
	- `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Configure no Render:
	- `DATA_ENCRYPTION_KEY=sua_chave_gerada_pelo_fernet`

2. **Mantenha chave administrativa forte:**

- `ADMIN_ACCESS_KEY=uma_chave_grande_e_unica`

3. **Use backup privado no GitHub (repo privado):**

- `GITHUB_BACKUP_REPO=seu-user/seu-repo-privado`
- `GITHUB_BACKUP_TOKEN=token_com_acesso_ao_repo_privado`
- `GITHUB_BACKUP_BRANCH=main`
- `GITHUB_BACKUP_PATH=observa_backup`

4. **Persistencia de disco no Render:**

- Garanta um Disk montado em `/var/data`.
- Opcionalmente, force por variavel:
	- `DATA_DIR=/var/data`

Com isso, os registros ficam:

- permanentes no disco persistente,
- protegidos por criptografia no arquivo principal,
- com copia externa privada no GitHub.

## 🐛 Troubleshooting

**Servidor não inicia:**
- Verifique se a porta 8000 está livre
- Confirme que o Flask está instalado

**GPS não funciona:**
- Permita acesso à localização no navegador
- Teste em um dispositivo móvel

**App não instala no celular:**
- Certifique-se de acessar via HTTP (não HTTPS)
- Use um navegador compatível (Chrome, Safari, etc.)

---

**Desenvolvido para Pernambuco** 🇧🇷

## Atualizacoes de Operacao (Geracao Diaria e Persistencia)

- Planilhas e mapa diario de Pernambuco sao gerados automaticamente as 08:00 para consolidar os dados do dia anterior.
- Endpoints disponiveis para consumo dessas saidas:
	- `GET /api/exports`
	- `GET /api/exports/download/daily`
	- `GET /api/exports/download/daily-map`
- A API mantem os registros de acidentes de forma permanente.
- O endpoint de exclusao foi desativado para impedir remocao de historico.

Arquivos gerados automaticamente em `exports/`:

- `acidentes_diario_YYYY-MM-DD.csv`
- `mapa_pe_diario_YYYY-MM-DD.html`
- `acidentes_diario_latest.csv`
- `mapa_pe_diario_latest.html`
