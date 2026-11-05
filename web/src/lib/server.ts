/** Server holati: versiya farqlari (server eski / yangi UI build), qayta ishga tushirish oqimi. */
import { reactive } from 'vue'
import { ApiError, get, post } from '../api/client'
import { useTabs } from '../stores/tabs'
import { askConfirm, showToast } from './ui'

export const uiVersion = __UI_VERSION__
export const server = reactive({ version: '', diskUi: null as string | null, started: 0, managed: false, active: 0, restarting: false, restartError: '' })
export const NOT_MANAGED_HINT = "Server PM2 ostida emas: terminalda Ctrl+C bosing va ./run.command bilan qayta ishga tushiring."

export async function checkVersion() {
  const d = await get('/api/version')
  Object.assign(server, { version: d.version, diskUi: d.ui_version ?? null, started: d.started ?? 0, managed: !!d.managed, active: d.active ?? 0 })
  return d
}
export const isServerStale = () => !!server.version && server.version !== uiVersion
/** Diskdagi UI build ochiq sahifadan yangi. */
export const hasNewBuild = () => !!server.diskUi && server.diskUi !== uiVersion

/** Saqlanmagan (dirty) tablar sonini aytib, tasdiq so'raydi; keyin holatni serverga yozib sahifani qayta yuklaydi. */
export async function reloadForNewBuild() {
  const tabs = useTabs()
  const dirty = tabs.tabs.filter(t => t.dirty).length
  if (dirty && !(await askConfirm(`${dirty} ta tabda saqlanmagan o'zgarish bor. Ular tab holati sifatida saqlanadi va qayta yuklangach tiklanadi, lekin collection'ga yozilmagan. Davom etilsinmi?`, 'Yangilash'))) return
  await tabs.flush()
  location.reload()
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
async function waitForRestart(started0: number) {
  const end = Date.now() + 60000
  let down = false
  while (Date.now() < end) {
    await sleep(600)
    try {
      const d = await get('/api/version')
      if (d.started !== started0 || down) return true
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return true        // server qayta ko'tarildi, sessiya tokeni yangi — sahifa yangilanishi kerak
      down = true
    }
  }
  return false
}

export async function restartServer(): Promise<void> {
  if (!server.managed) { showToast(NOT_MANAGED_HINT, 'warn', 8000); return }
  const tabs = useTabs()
  await tabs.flush()
  try {
    try { await post('/api/admin/restart', {}) } catch (e: any) {
      if (!(e instanceof ApiError) || e.status !== 409) throw e
      const m = e.message
      if (!/Faol run/.test(m)) throw e
      await checkVersion().catch(() => {})
      const n = server.active || 1
      if (!(await askConfirm(`${n} ta faol run bor. Qayta ishga tushirsangiz u to'xtatiladi (shu paytgacha natijalar tarixda qoladi). Davom etilsinmi?`, 'To\'xtatib, qayta ishga tushirish'))) return
      await post('/api/admin/restart', { force: true })
    }
  } catch (e: any) { showToast(e.message, 'error'); return }
  server.restarting = true; server.restartError = ''
  const ok = await waitForRestart(server.started)
  if (ok) location.reload()
  else server.restartError = "Server 60 soniyada qayta ko'tarilmadi — pm2 logs api-runner ni tekshiring"
}
