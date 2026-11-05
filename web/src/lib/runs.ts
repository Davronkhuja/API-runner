/** Run engine mijozi: reja tuzish, SSE obuna, tarix/solishtirish/eksport. Hisoblash serverda (core/run_engine.py), natijalar SQLite'da. */
import { eventSource, get, post, token } from '../api/client'
import { draftFromItem } from './draft'
import { prepareAuth, specFor } from './scope'
import { scriptsFor } from './scripts'
import type { RequestItem } from '../types/model'

export interface RunSettings {
  iterations: number | null      // null — data qatorlari soni (yo'q bo'lsa 1)
  delay_ms: number; parallel: number; retry: number; timeout: number; ssl: boolean
  stop_on_error: boolean; save_vars: boolean; save_responses: boolean
}
export const defaultRunSettings = (): RunSettings => ({ iterations: null, delay_ms: 0, parallel: 1, retry: 0, timeout: 30, ssl: true, stop_on_error: false, save_vars: true, save_responses: true })

export interface PlanItem { id: string; name: string; method: string; ref: string; item?: RequestItem; draft?: any }
export interface RunSummary { planned: number; completed: number; successful: number; failed: number; skipped: number; tests_passed: number; tests_failed: number; min_time: number; max_time: number; avg_time: number; stopped: boolean; error: string | null }
export interface RunInfo { id: number; scope: string; scope_name: string; number: number; kind: string; started: number; finished: number | null; status: string; env_name: string; iterations: number; summary: Partial<RunSummary> }
export interface RunStep { run_id: number; iter: number; seq: number; index: number; total: number; id: string; name: string; method: string; ref?: string; url: string; status: number | string; time: number; size: number; error: boolean
  tests: { name: string; passed: boolean; skipped: boolean; error?: string }[]; test_pass: number; test_fail: number; response?: string; resp_headers?: Record<string, string>; scripts?: any; successful: number; failed: number }

/** Har so'rov uchun engine spec (auth tayyorlanadi, `specFor` bilan bir xil qoidalar) — server uni har iteratsiyada data qatori bilan bajaradi. */
export async function buildPlan(scope: { ref: string; name: string; kind: 'runner' | 'batch' }, items: PlanItem[], settings: RunSettings, rows: Record<string, unknown>[], envName: string, vars: Record<string, string> = {}) {
  const plan: any[] = []
  const first = Object.fromEntries(Object.entries(rows[0] ?? {}).map(([k, v]) => [k, String(v)]))     // auth tayyorlash uchun birinchi data qatori (eski xatti-harakat)
  vars = { ...vars, ...first }
  for (const x of items) {
    const d = x.draft ?? draftFromItem(x.item!)
    await prepareAuth(d, x.ref, vars)
    const spec = specFor(d, x.ref, vars)
    delete spec.timeout
    const scripts = scriptsFor(x.ref, d.scripts, x.name)
    plan.push({ id: x.id, name: x.name, method: x.method, ref: x.ref, spec, scripts: scripts ?? null })
  }
  return { scope: scope.ref, scope_name: scope.name, kind: scope.kind, env_name: envName, items: plan, rows, iterations: settings.iterations ?? (rows.length || 1),
    settings: { delay_ms: settings.delay_ms, parallel: settings.parallel, retry: settings.retry, timeout: settings.timeout, ssl: settings.ssl, stop_on_error: settings.stop_on_error, save_vars: settings.save_vars, save_responses: settings.save_responses, include_response: true, max_steps: Number((window as any).__MAX_RUN_STEPS) || undefined } }
}

export interface RunHandle { id: number; number: number; close: () => void }
/** Run'ni boshlaydi va SSE hodisalarini uzatadi. */
export async function startRun(plan: unknown, on: { start?: (d: any) => void; step?: (s: RunStep) => void; note?: (m: string) => void; done?: (d: any) => void; lost?: () => void }): Promise<RunHandle> {
  const r = await post('/api/runs', plan)
  const src = eventSource(`/api/runs/${r.id}/stream`)
  let finished = false
  src.addEventListener('start', (e: MessageEvent) => on.start?.(JSON.parse(e.data)))
  src.addEventListener('step', (e: MessageEvent) => on.step?.(JSON.parse(e.data)))
  src.addEventListener('note', (e: MessageEvent) => on.note?.(JSON.parse(e.data).message))
  src.addEventListener('done', (e: MessageEvent) => { finished = true; src.close(); on.done?.(JSON.parse(e.data)) })
  src.onerror = () => { if (!finished) { src.close(); on.lost?.() } }
  return { id: r.id, number: r.number, close: () => src.close() }
}
export const stopRun = (id: number) => post(`/api/runs/${id}/stop`)

export const listRuns = (scope: string, limit = 30) => get(`/api/runs?scope=${encodeURIComponent(scope)}&limit=${limit}`) as Promise<RunInfo[]>
export const getRun = (id: number) => get(`/api/runs/${id}`)
export const getResult = (id: number) => get(`/api/runs/results/${id}`)
export const compareRuns = (a: number, b: number) => get(`/api/runs/${a}/compare/${b}`)
export const deleteRun = (id: number) => fetch(`/api/runs/${id}`, { method: 'DELETE', headers: { 'X-Session-Token': token() } })
export const lastResults = (refs: string[], scope?: string) => get(`/api/last-results?refs=${encodeURIComponent(refs.join(','))}${scope ? '&scope=' + encodeURIComponent(scope) : ''}`)

export async function exportRun(id: number, format: 'json' | 'html' | 'junit', number: number) {
  const r = await fetch(`/api/runs/${id}/export?format=${format}`, { headers: { 'X-Session-Token': token() } })
  const blob = await r.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = `run-${number}.${format === 'junit' ? 'junit.xml' : format}`; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
