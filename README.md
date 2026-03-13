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
