import type { Tab } from '../stores/tabs'
import { applyScriptResult } from './scripts'
import { logScripts } from './console'
import { buildPlan, defaultRunSettings, startRun, stopRun, type RunSettings } from './runs'

/** Batch ham Runner bilan bir xil sozlamalar (RunSettings) + qatorlar soni; hisoblash serverdagi yagona run engine'da. */
export interface BatchSettings extends RunSettings { rowsMode: 'all' | 'custom'; count: number }
export const defaultBatch = (): BatchSettings => ({ ...defaultRunSettings(), save_responses: true, rowsMode: 'all', count: 10 })

export interface BatchState {
  settings: BatchSettings
  data: { name: string; rows: Record<string, string>[] } | null
  status: 'idle' | 'running' | 'done' | 'stopped' | 'error'
  statusText: string
  jobId: number | null
  results: any[]
  total: number
  summary: any | null
  filter: 'all' | 'success' | 'error'
}
export const newBatchState = (): BatchState => ({ settings: defaultBatch(), data: null, status: 'idle', statusText: 'Tayyor', jobId: null, results: [], total: 0, summary: null, filter: 'all' })

/** Bitta so'rov × data qatorlari → bitta run (scope = so'rov ref); step hodisalari eski natija kartalariga moslanadi. */
export async function startBatch(tab: Tab, vars: Record<string, string>, onDone?: (b: BatchState) => void, envName = '') {
  const b = (tab.state!.batch ??= newBatchState()) as BatchState
  const d = tab.draft!
  const s = b.settings
  let rows = b.data?.rows?.length ? b.data.rows : [{}]
  if (s.rowsMode === 'custom') rows = rows.slice(0, Math.max(1, s.count || 1))
  b.results = []; b.summary = null; b.total = rows.length; b.status = 'running'; b.statusText = `${rows.length} ta so'rov yuborilmoqda...`
  tab.state!.mode = 'batch'
  try {
    const item = { id: tab.ref!, name: d.name, method: d.method, ref: tab.ref!, draft: d }
    const plan = await buildPlan({ ref: tab.ref!, name: d.name || d.url, kind: 'batch' }, [item], { ...s, iterations: rows.length }, rows, envName, vars)
    const h = await startRun(plan, {
      step: st => {
        b.results.push({ index: st.iter, total: rows.length, status: st.status, time: st.time, size: st.size, url: st.url, response: st.response ?? '', resp_headers: st.resp_headers ?? {}, retries: (st as any).retries, error: !!st.error || typeof st.status !== 'number' || st.status >= 400, scripts: st.scripts })
        if (st.scripts) logScripts(st.scripts, { tabId: tab.id, ref: tab.ref })
        b.statusText = `${b.results.length} / ${rows.length}`
      },
      done: sm => {
        b.summary = sm; b.jobId = null
        b.status = sm.stopped ? 'stopped' : sm.error ? 'error' : 'done'
        b.statusText = sm.error ? 'Xatolik: ' + sm.error : sm.stopped ? `To'xtatildi — ${sm.completed} ta yuborildi` : `Bajarildi — ${sm.successful} muvaffaqiyatli, ${sm.failed} xatolik`
        if (b.results.some(r => r.scripts?.changed?.length)) applyScriptResult({ available: true, tests: [], console: [], errors: [], changed: ['environment', 'globals', 'collection'] }, { tabId: tab.id, ref: tab.ref })
        onDone?.(b)
      },
      lost: () => { if (b.status === 'running') { b.status = 'error'; b.statusText = "Oqim uzildi — natijalar Runner tarixida saqlangan" } },
    })
    b.jobId = h.id
  } catch (e: any) { b.status = 'error'; b.statusText = 'Xatolik: ' + e.message }
}
export async function stopBatch(tab: Tab) {
  const b = tab.state?.batch as BatchState | undefined
  if (b?.jobId) await stopRun(b.jobId)
}

export const statsOf = (b: BatchState) => {
  const c = { s2: 0, s4: 0, s5: 0 }
  for (const r of b.results) if (typeof r.status === 'number') { if (r.status < 300 && r.status >= 200) c.s2++; else if (r.status >= 400 && r.status < 500) c.s4++; else if (r.status >= 500) c.s5++ }
  const ok = b.results.filter(r => !r.error).length
  const times = b.results.map(r => r.time)
  return { ...c, total: b.total, ok, err: b.results.length - ok, avg: times.length ? times.reduce((a, x) => a + x, 0) / times.length : null }
}

export function toCSV(results: any[]): string {
  const esc = (v: unknown) => `"${String(typeof v === 'object' ? JSON.stringify(v) : v ?? '').replace(/"/g, '""')}"`
  const head = ['index', 'status', 'time', 'size', 'url', 'response', 'error']
  return [head.join(','), ...results.map(r => head.map(k => esc(r[k])).join(','))].join('\n')
}
export function download(name: string, text: string, mime = 'text/plain') {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type: mime })); a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
