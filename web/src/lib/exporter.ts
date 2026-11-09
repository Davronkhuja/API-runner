/** Eksport yuklab olish: token bilan fetch → Blob → fayl. Nom — serverning Content-Disposition'idan. */
import { token } from '../api/client'
import { showToast } from './ui'

export async function downloadFrom(path: string, fallback = 'export', body?: unknown): Promise<string | null> {
  try {
    const r = await fetch(path, body === undefined ? { headers: { 'X-Session-Token': token() } } : { method: 'POST', headers: { 'X-Session-Token': token(), 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error((j as any).error ?? `HTTP ${r.status}`) }
    const m = /filename="?([^";]+)"?/i.exec(r.headers.get('Content-Disposition') ?? '')
    const name = m ? decodeURIComponent(m[1]) : fallback
    const blob = await r.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob); a.download = name; a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 1000)
    return name
  } catch (e: any) { showToast('Eksport bajarilmadi: ' + e.message, 'error'); return null }
}

export const EXPORT_FORMATS: { id: string; label: string; hint: string }[] = [
  { id: 'postman', label: 'Postman Collection v2.1 (.json)', hint: "Postman, Newman va boshqa vositalarga; skriptlar, auth, o'zgaruvchilar, namunalar saqlanadi" },
  { id: 'openapi', label: 'OpenAPI 3.0 (.json)', hint: "Yo'llar, parametrlar, body sxemalari (JSON'dan), javoblar (namunalardan), xavfsizlik sxemalari" },
  { id: 'openapi-yaml', label: 'OpenAPI 3.0 (.yaml)', hint: 'Xuddi shu hujjat YAML ko\'rinishida' },
]
