// PM2 sozlamasi: `pm2 start ecosystem.config.js` (keyin `pm2 save`).
// Loyiha ichidagi .venv interpreteri ishlatiladi; yo'llar shu fayl joylashgan papkadan olinadi.
const path = require('path')

module.exports = {
  apps: [
    {
      name: 'api-runner',
      script: 'api_runner.py',
      cwd: __dirname,
      interpreter: path.join(__dirname, '.venv', 'bin', 'python'),
      env: {
        APIRUNNER_PORT: '5050',
        APIRUNNER_NO_BROWSER: '1', // PM2 ostida brauzer avtomatik ochilmasin
        PYTHONUNBUFFERED: '1',
      },
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 2000,
    },
  ],
}
