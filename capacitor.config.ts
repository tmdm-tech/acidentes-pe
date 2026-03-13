import type { CapacitorConfig } from '@capacitor/cli';

const appUrl = process.env.OBSERVAPE_APP_URL || 'https://SEU-SERVICO.onrender.com';

const config: CapacitorConfig = {
  appId: 'br.gov.pe.observape',
  appName: 'ObservaPE',
  webDir: 'ios_web',
  server: {
    // Em producao iOS, carregamos o app via HTTPS no Render para manter /api/* funcional
    url: appUrl,
    cleartext: false
  },
  ios: {
    contentInset: 'automatic'
  }
};

export default config;
