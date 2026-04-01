# Preparacao iOS App Store (ObservaATT PE)

Este guia deixa o projeto pronto para abrir no Xcode e publicar na Apple App Store.

## 1. O que foi preparado no repositório

- `package.json` com scripts de empacotamento iOS (Capacitor)
- `capacitor.config.ts` com `appId`, `appName` e `OBSERVAATT_APP_URL`
- `scripts/sync_web_for_ios.sh` para sincronizar assets de `web/` para `ios_web/`
- `.env.ios.example` para configurar a URL publica do Render

## 2. Instalar Xcode (obrigatoriamente em Mac)

No Linux, Windows ou Codespaces nao e possivel instalar Xcode.

No seu Mac:

1. Abra a App Store
2. Busque por `Xcode`
3. Instale (ID oficial: `497799835`)
4. Depois rode no terminal:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -runFirstLaunch
```

## 3. Gerar projeto iOS com Capacitor

No Mac, dentro da pasta do projeto:

```bash
cp .env.ios.example .env.ios
export $(grep -v '^#' .env.ios | xargs)
npm install
npm run ios:init
npm run ios:sync
npm run ios:open
```

Isso abre o workspace iOS no Xcode.

## 4. Ajustes obrigatorios no Xcode

No target do app (`Signing & Capabilities`):

1. Defina `Team` (sua conta Apple Developer)
2. Defina `Bundle Identifier` unico (ex.: `br.gov.pe.observape`)
3. Habilite `Automatically manage signing`

No `Info.plist`, adicione descricoes de permissao:

- `NSLocationWhenInUseUsageDescription`: "Usamos sua localizacao para registrar o local do acidente."
- `NSCameraUsageDescription`: "Usamos a camera para capturar fotos do sinistro."
- `NSPhotoLibraryUsageDescription`: "Usamos a galeria para anexar fotos do sinistro."

## 5. Medidas obrigatorias para App Store

### Icone do app

- 1024 x 1024 px (PNG, sem transparencia) para App Store Connect

### Screenshots (recomendado minimo)

- iPhone 6.7": 1290 x 2796
- iPhone 6.5": 1242 x 2688
- iPhone 5.5": 1242 x 2208
- iPad 12.9" (opcional, se suportar iPad): 2048 x 2732

### Versao

- `CFBundleShortVersionString`: ex. `1.0.0`
- `CFBundleVersion`: ex. `1`

## 6. Publicacao no App Store Connect

1. Acesse [https://appstoreconnect.apple.com](https://appstoreconnect.apple.com)
2. Crie o app (nome, idioma, bundle id, SKU)
3. No Xcode: `Product > Archive`
4. Em `Window > Organizer`: `Distribute App > App Store Connect > Upload`
5. No App Store Connect:
   - complete descricao, categoria e palavras-chave
   - envie screenshots nas medidas acima
   - preencha politica de privacidade
   - envie para revisao

## 7. TestFlight (antes de producao)

1. Suba um build via Xcode
2. Ative em `TestFlight`
3. Convide testadores internos
4. Corrija problemas antes do envio final

## 8. Checklist rapido

- [ ] URL do Render em HTTPS funcionando
- [ ] Xcode instalado e configurado
- [ ] Certificados e signing OK
- [ ] Permissoes no Info.plist
- [ ] Icone 1024x1024 pronto
- [ ] Screenshots nas medidas exigidas
- [ ] Build validado no TestFlight
- [ ] App enviado para revisao
