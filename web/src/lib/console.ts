/** Console paneli ma'lumotlari: so'rov/javob loglari, skriptdagi console.* va skript xatolari (status bardan ochiladi). */
import { computed, reactive, ref } from 'vue'

export type Level = 'log' | 'info' | 'warn' | 'error' | 'debug' | 'request' | 'response' | 'script-error'
export interface Origin { kind?: string; scope?: string; name?: string; id?: string }
export interface Entry { id: number; ts: number; level: Level; text: string; origin?: Origin; line?: number | null; stack?: string; tabId?: string; ref?: string | null }

const MAX = 1000
let seq = 0
export const entries = ref<Entry[]>([])
export const consoleOpen = ref(false)
const CH_KEY = 'apirunner.console.h'
export const CONSOLE_DEFAULT = 240
const loadCH = () => { try { return Number(localStorage.getItem(CH_KEY)) || CONSOLE_DEFAULT } catch { return CONSOLE_DEFAULT } }
export const consoleHeight = ref(loadCH())
/** Console balandligi: kamida 100px; yuqoridagi ish maydoni (tablar, URL, so'rov va javob kamida 120px dan) sig'ishi uchun oyna balandligidan 420px zaxira qoladi. */
export const clampConsole = (h: number) => Math.max(100, Math.min(window.innerHeight - 420, Math.round(h)))
export const saveConsoleHeight = () => { try { localStorage.setItem(CH_KEY, String(consoleHeight.value)) } catch { /* bloklangan */ } }
export const unreadErrors = ref(0)
export const filters = reactive<Record<string, boolean>>({ log: true, info: true, warn: true, error: true, debug: true, request: true, response: true })

export function push(e: Omit<Entry, 'id' | 'ts'> & { ts?: number }) {
  entries.value.push({ id: ++seq, ts: e.ts ?? Date.now(), ...e })
  if (entries.value.length > MAX) entries.value.splice(0, entries.value.length - MAX)
  if ((e.level === 'error' || e.level === 'script-error') && !consoleOpen.value) unreadErrors.value++
}
export const clear = () => { entries.value = []; unreadErrors.value = 0 }
export const toggle = () => { consoleOpen.value = !consoleOpen.value; if (consoleOpen.value) unreadErrors.value = 0 }
export const visible = computed(() => entries.value.filter(e => (e.level === 'script-error' ? filters.error : filters[e.level] !== false)))

export const logRequest = (method: string, url: string, tabId?: string) => push({ level: 'request', text: `${method} ${url}`, tabId })
export function logResponse(r: any, tabId?: string) {
  const ok = typeof r?.status === 'number' && r.status < 400
  const t = typeof r?.time === 'number' ? ` · ${r.time < 1 ? Math.round(r.time * 1000) + ' ms' : r.time.toFixed(2) + ' s'}` : ''
  push({ level: 'response', text: `${r?.status ?? '—'}${t}${r?.size != null ? ' · ' + r.size + ' B' : ''}${ok || r?.status === 'SKIPPED' ? '' : ' ⚠'}`, tabId })
}
/** Skript natijasi: console.* (originli), xatolar (stack bilan), qo'llab-quvvatlanmaydigan API ogohlantirishlari. */
export function logScripts(sc: any, ctx: { tabId?: string; ref?: string | null } = {}) {
  if (!sc) return
  if (sc.available === false) { push({ level: 'warn', text: `Skriptlar o'chiq: ${sc.message ?? 'quickjs-ng o\'rnatilmagan'} — ${sc.install ?? ''}`, ...ctx }); return }
  for (const l of sc.console ?? []) push({ level: l.level, text: l.text, origin: l.origin, ts: l.ts, ...ctx })
  for (const e of sc.errors ?? []) push({ level: 'script-error', text: `${e.name}: ${e.message}`, origin: e.origin, line: e.line, stack: e.stack, ...ctx })
  for (const t of sc.tests ?? []) if (!t.passed) push({ level: 'error', text: `✗ ${t.name}${t.error ? ' — ' + t.error.message : ''}`, origin: t.origin, line: t.error?.line, stack: t.error?.stack, ...ctx })
}
