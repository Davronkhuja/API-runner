import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'node:fs'

// UI versiyasi — yagona manba apirunner/__init__.py (server bilan solishtirish uchun build'ga yoziladi)
const uiVersion = /__version__\s*=\s*"([^"]+)"/.exec(readFileSync('../apirunner/__init__.py', 'utf8'))![1]

// Build natijasi Flask static papkasiga tushadi va git'ga commit qilinadi (run.command Node'siz ishlaydi).
export default defineConfig({
  plugins: [vue()],
  define: { __UI_VERSION__: JSON.stringify(uiVersion) },
  base: '/static/app/',
  build: { outDir: '../apirunner/static/app', emptyOutDir: true, sourcemap: false },
  server: { proxy: { '/api': 'http://127.0.0.1:5050', '/run': 'http://127.0.0.1:5050', '/run_one': 'http://127.0.0.1:5050', '/stream': 'http://127.0.0.1:5050', '/stop': 'http://127.0.0.1:5050', '/upload_temp': 'http://127.0.0.1:5050' } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
