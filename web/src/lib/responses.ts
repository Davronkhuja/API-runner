/** Serverda saqlangan javoblar (SQLite, 5 MB gacha): tabni tiklash, tarix diff'i, binary preview. */
import { get, token } from '../api/client'

export const MAX_STORED = 5 * 1024 * 1024

export interface StoredResponse { id: number; status: string; headers: Record<string, string>; ctype: string; size: number; stored: number; truncated: boolean; binary: boolean; body: string | null }

const cache = new Map<number, Promise<StoredResponse | null>>()
export function fetchStored(id: number): Promise<StoredResponse | null> {
  if (!cache.has(id)) cache.set(id, get(`/api/responses/${id}`).then(r => r as StoredResponse).catch(() => null))
  return cache.get(id)!
}

/** Javob matnini jonli javob kabi ko'rinishga keltiradi: JSON bo'lsa obyekt, aks holda matn. */
export function parseBody(text: string, ctype: string): unknown {
  if (/json/i.test(ctype) || /^\s*[{[]/.test(text)) { try { return JSON.parse(text) } catch { /* kesilgan yoki JSON emas — matn */ } }
  return text
}

/** Tab javobini serverdagi nusxadan to'ldiradi. Muvaffaqiyatsiz (o'chirilgan/yo'q) bo'lsa — `truncated` ("Javob saqlanmagan") qoladi. */
export async function hydrateResponse(resp: any) {
  if (!resp?.response_id) return
  if (resp.binary) { resp.restored = true; return }                       // binary: tana serverda, Preview uni blob sifatida oladi
  const s = await fetchStored(resp.response_id)
  if (!s || s.body === null) { resp.truncated = true; return }
  resp.response = parseBody(s.body, s.ctype)
  resp.restored = true
  resp.stored_truncated = s.truncated || undefined
  resp.truncated = undefined
}

export async function fetchRawBlob(id: number): Promise<Blob | null> {
  try {
    const r = await fetch(`/api/responses/${id}/raw`, { headers: { 'X-Session-Token': token() } })
    return r.ok ? await r.blob() : null
  } catch { return null }
}

export function downloadBlob(blob: Blob, name: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

const EXT: Record<string, string> = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp', 'application/pdf': 'pdf', 'application/zip': 'zip', 'application/json': 'json', 'text/html': 'html', 'text/plain': 'txt' }
export const extFor = (ctype: string) => EXT[(ctype || '').split(';')[0].trim().toLowerCase()] ?? 'bin'
