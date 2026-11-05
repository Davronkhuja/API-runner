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

/** Fayl nomi: Content-Disposition → URL oxirgi qismi (kengaytma bilan) → `javob.<ext>`. */
export function fileNameFor(headers: Record<string, string>, url: string, ctype: string, fallbackExt: string): string {
  const h = Object.entries(headers ?? {}).find(([k]) => k.toLowerCase() === 'content-disposition')?.[1] ?? ''
  const star = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(h), plain = /filename\s*=\s*"?([^";]+)"?/i.exec(h)
  const clean = (n: string) => n.replace(/[\\/:*?"<>|\x00-\x1f]+/g, '_').trim().slice(0, 150)
  try { if (star) return clean(decodeURIComponent(star[1].trim())) || 'javob.' + fallbackExt } catch { /* noto'g'ri kodlash */ }
  if (plain) return clean(plain[1]) || 'javob.' + fallbackExt
  try {
    const last = decodeURIComponent(new URL(url).pathname.split('/').filter(Boolean).pop() ?? '')
    if (last) return clean(/\.[A-Za-z0-9]{1,6}$/.test(last) ? last : `${last}.${fallbackExt}`)
  } catch { /* URL emas */ }
  void ctype
  return 'javob.' + fallbackExt
}

/** Javobni faylga saqlaydi (binary — serverdagi nusxadan, matn — joriy matndan). Qaytaradi: saqlangan nom. */
export async function saveResponseFile(resp: any, text: string): Promise<string | null> {
  const ctype = Object.entries(resp?.resp_headers ?? {}).find(([k]) => k.toLowerCase() === 'content-type')?.[1] as string ?? ''
  if (resp?.binary && resp.response_id) {
    const b = await fetchRawBlob(resp.response_id)
    if (!b) return null
    const name = fileNameFor(resp.resp_headers, resp.url ?? '', ctype, extFor(ctype))
    downloadBlob(b, name)
    return name
  }
  const name = fileNameFor(resp?.resp_headers, resp?.url ?? '', ctype, typeof resp?.response === 'string' ? (extFor(ctype) === 'bin' ? 'txt' : extFor(ctype)) : 'json')
  downloadBlob(new Blob([text]), name)
  return name
}
