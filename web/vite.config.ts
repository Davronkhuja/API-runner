import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Build natijasi Flask static papkasiga tushadi va git'ga commit qilinadi (run.command Node'siz ishlaydi).
export default defineConfig({
  plugins: [vue()],
  base: '/static/app/',
  build: { outDir: '../apirunner/static/app', emptyOutDir: true, sourcemap: false },
  server: { proxy: { '/api': 'http://127.0.0.1:5050', '/run': 'http://127.0.0.1:5050', '/run_one': 'http://127.0.0.1:5050', '/stream': 'http://127.0.0.1:5050', '/stop': 'http://127.0.0.1:5050', '/upload_temp': 'http://127.0.0.1:5050' } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
