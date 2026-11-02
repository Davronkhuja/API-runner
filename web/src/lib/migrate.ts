/** Eski brauzer (localStorage) ma'lumotlarini serverga ko'chirish va legacy formatga eksport. */
import { get, post as apiPost, put } from '../api/client'
import { useHistory } from '../stores/history'
import { useWorkspace } from '../stores/workspace'
import { showToast } from './ui'

const LS_KEYS = ['apiRunnerEnvs', 'apiRunnerActiveEnvId', 'apiRunnerEnvVars', 'apiRunnerHistory', 'apiRunnerRunHistory', 'apiRunnerUrlHistory']
/** localStorage'dan faqat O'QIYDI — hech narsa o'chirilmaydi. */
export function readLocalStorage(): Record<string, string> {
  const data: Record<string, string> = {}
  try { LS_KEYS.forEach(k => { const v = localStorage.getItem(k); if (v != null) data[k] = v }) } catch { /* ixtiyoriy */ }
  return data
}
export async function defaultNotice() {
  const st = await get('/api/status').catch(() => null)
  if (st?.meta?.legacy_default_migrated && !st.meta.legacy_default_notified) {
    showToast("Eski Default o'zgaruvchilar Globals'ga ko'chirildi", 'info', 8000)
    await put('/api/workspace/meta', { legacy_default_notified: true }).catch(() => {})
  }
}

export async function importLocalStorage() {
  const data = readLocalStorage()
  if (!Object.keys(data).length) return showToast("localStorage'da ko'chiriladigan ma'lumot yo'q", 'warn')
  const ws = useWorkspace(), hist = useHistory()
  try {
    const r = await apiPost('/api/import/localstorage', { data })
    await Promise.all([ws.load(), hist.load()])
    showToast(`Ko'chirildi: ${r.stats.environments} env, ${r.stats.history + r.stats.run_history + r.stats.url_history} tarix yozuvi`, 'success')
    await defaultNotice()
  } catch (err: any) { showToast('Import xatosi: ' + err.message, 'error') }
}
export async function exportLegacy() {
  const r = await fetch('/api/export/legacy', { headers: { 'X-Session-Token': window.__API_TOKEN__ ?? '' } })
  const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = 'saved_requests.json'; a.click()
}

