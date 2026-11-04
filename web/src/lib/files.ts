/** Biriktirilgan fayllar: yuklash (workspace/files), holat (topilmadi/hajm), tur taxmini. */
import { reactive } from 'vue'
import { post, token } from '../api/client'
import type { RequestDraft } from './draft'

export interface FileRef { ref: string; name: string }
export interface FileInfo { exists: boolean; size: number }

/** Havola bo'yicha holat keshi (reaktiv): qator qizil bo'lishi va hajm ko'rsatilishi shundan. */
export const fileInfo = reactive<Record<string, FileInfo>>({})

/** `files/<hash>/<nom>` -> nom; tashqi yo'l ("yo'l::nom" ham) -> nom. */
export function refName(ref: string): string {
  const m = /^files\/[0-9a-f]{64}(?:\/(.*))?$/.exec(ref)
  if (m) { try { return decodeURIComponent(m[1] ?? '') || 'file' } catch { return m[1] || 'file' } }
  const [path, label] = ref.split('::')
  return (label?.trim() || path.split(/[\\/]/).pop() || 'file')
}
export const toFileRef = (ref: string): FileRef => ({ ref, name: refName(ref) })

export async function uploadFile(f: File): Promise<FileRef & { size: number }> {
  const fd = new FormData(); fd.append('file', f)
  const r = await fetch('/api/files', { method: 'POST', body: fd, headers: { 'X-Session-Token': token() } })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(d.error ?? `HTTP ${r.status}`)
  fileInfo[d.ref] = { exists: true, size: d.size }
  return { ref: d.ref, name: d.name, size: d.size }
}

export async function refreshFileInfo(refs: string[]) {
  const want = [...new Set(refs.filter(Boolean))]
  if (!want.length) return
  try {
    const st = await post('/api/files/status', { refs: want })
    for (const r of want) if (st[r]) fileInfo[r] = { exists: st[r].exists, size: st[r].size }
  } catch { /* eski server: holat noma'lum — qator qizil bo'lmaydi */ }
}

export const isMissing = (ref: string) => fileInfo[ref]?.exists === false

const TYPES: Record<string, string> = {
  pdf: 'application/pdf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', svg: 'image/svg+xml',
  txt: 'text/plain', csv: 'text/csv', html: 'text/html', json: 'application/json', xml: 'application/xml', zip: 'application/zip',
  doc: 'application/msword', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xls: 'application/vnd.ms-excel', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', mp3: 'audio/mpeg', mp4: 'video/mp4',
}
/** Fayl nomidan Content-Type taxmini (server ham shunday: mimetypes). */
export const guessType = (name: string) => TYPES[(name.split('.').pop() ?? '').toLowerCase()] ?? 'application/octet-stream'

/** Yoqilgan form-data fayl qatorlari va binary fayl havolalari. */
export function draftFileRefs(d: RequestDraft): FileRef[] {
  const out: FileRef[] = []
  if (d.body.mode === 'multipart') for (const f of d.body.fields) if (f.enabled && f.kind === 'file') out.push(...(f.files ?? []))
  if (d.body.mode === 'binary' && d.body.file.path) out.push({ ref: d.body.file.path, name: d.body.file.name })
  return out
}

/** Yuborishdan oldin: diskda topilmayotgan fayllar (server so'raladi). */
export async function missingFilesOf(d: RequestDraft): Promise<FileRef[]> {
  const refs = draftFileRefs(d)
  if (!refs.length) return []
  await refreshFileInfo(refs.map(r => r.ref))
  return refs.filter(r => isMissing(r.ref))
}
