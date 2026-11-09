/** WebSocket/SSE jurnali yordamchilari (toza funksiyalar). */
import type { ProtoEvent } from '../stores/protocols'

export const b64bytes = (b64: string): Uint8Array => Uint8Array.from(atob(b64), c => c.charCodeAt(0))
export const bytesToText = (u: Uint8Array) => new TextDecoder('utf-8', { fatal: false }).decode(u)

/** 16 baytli qatorlar: ofset · hex · ASCII. */
export function hexdump(u: Uint8Array, max = 4096): string {
  const rows: string[] = []
  for (let i = 0; i < Math.min(u.length, max); i += 16) {
    const chunk = u.subarray(i, i + 16)
    const hex = [...chunk].map(b => b.toString(16).padStart(2, '0')).join(' ').padEnd(47)
    const asc = [...chunk].map(b => (b >= 32 && b < 127 ? String.fromCharCode(b) : '.')).join('')
    rows.push(`${i.toString(16).padStart(6, '0')}  ${hex}  ${asc}`)
  }
  if (u.length > max) rows.push(`… yana ${u.length - max} bayt`)
  return rows.join('\n')
}

export const fmtTime = (ts: number): string => {
  const d = new Date(ts * 1000)
  const p = (n: number, l = 2) => String(n).padStart(l, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`
}

export function tryJson(s: string): unknown | undefined {
  const t = s.trim()
  if (!t || !'{["-0123456789tfn'.includes(t[0])) return undefined
  try { const v = JSON.parse(t); return typeof v === 'object' && v !== null ? v : undefined } catch { return undefined }
}

/** Xabarning matn ko'rinishi (binary — base64'dan UTF-8 yoki hex). */
export function textOf(e: ProtoEvent): string {
  if (e.kind === 'binary') { const u = b64bytes(e.data ?? ''); return hexdump(u, 256).split('\n')[0] || '(bo\'sh)' }
  return e.data ?? ''
}

export const oneLine = (s: string, n = 200) => { const t = s.replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n) + '…' : t }

export const SYSTEM = new Set(['connecting', 'open', 'close', 'closed', 'error', 'reconnecting', 'comment'])
export const isSystem = (e: ProtoEvent) => SYSTEM.has(e.type)

export function systemText(e: ProtoEvent): string {
  switch (e.type) {
    case 'connecting': return e.attempt ? `Ulanilmoqda… (urinish ${e.attempt})` : 'Ulanilmoqda…'
    case 'open': return `Ulandi${e.status ? ` (HTTP ${e.status})` : ''}${e.subprotocol ? ` · subprotokol: ${e.subprotocol}` : ''}${e.warning ? ` · ⚠ ${e.warning}` : ''}`
    case 'close': return `Yopildi${e.code != null ? ` (kod ${e.code}${e.reason ? `: ${e.reason}` : ''})` : ''}`
    case 'closed': return 'Sessiya tugadi'
    case 'error': return e.message ?? 'Xato'
    case 'reconnecting': return `Qayta ulanish ${e.delay != null ? e.delay.toFixed(e.delay < 1 ? 2 : 1) : ''} s dan keyin (urinish ${e.attempt})${e.last_event_id ? ` · Last-Event-ID: ${e.last_event_id}` : ''}`
    case 'comment': return `: ${e.data ?? ''}`
  }
  return e.type
}

export interface LogFilter { dir: 'all' | 'in' | 'out'; system: boolean; types: string[] | null; q: string; regex: boolean }

/** Filtr + qidiruv. `types` (SSE): null = hammasi. */
export function filterEvents(events: ProtoEvent[], f: LogFilter): ProtoEvent[] {
  let rx: RegExp | null = null
  const q = f.q.trim()
  if (q) { try { rx = f.regex ? new RegExp(q, 'i') : new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') } catch { rx = null } }
  return events.filter(e => {
    if (isSystem(e)) return f.system && (!rx || rx.test(systemText(e)))
    if (f.dir !== 'all' && (e.dir ?? 'in') !== f.dir) return false          // SSE hodisalari doim kiruvchi
    if (f.types && e.type === 'event' && !f.types.includes(e.event ?? 'message')) return false
    if (rx) return rx.test(e.kind === 'binary' ? bytesToText(b64bytes(e.data ?? '')) : (e.data ?? '')) || (e.event ? rx.test(e.event) : false)
    return true
  })
}

export const fmtSize = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`)

export const newTemplateId = () => 'tp' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5)
