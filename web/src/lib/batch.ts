import { eventSource, post } from '../api/client'
import { prepareAuth, specFor } from './scope'
import type { Tab } from '../stores/tabs'

export interface BatchSettings { rowsMode: 'all' | 'custom'; count: number; delay: number; timeout: number; concurrency: number; retry: number; ssl: boolean }
export const defaultBatch = (): BatchSettings => ({ rowsMode: 'all', count: 10, delay: 0, timeout: 120, concurrency: 1, retry: 0, ssl: true })

export interface BatchState {
  settings: BatchSettings
  data: { name: string; rows: Record<string, string>[] } | null
  status: 'idle' | 'running' | 'done' | 'stopped' | 'error'
  statusText: string
  jobId: string | null
  results: any[]
  total: number
  summary: any | null
  filter: 'all' | 'success' | 'error'
}
export const newBatchState = (): BatchState => ({ settings: defaultBatch(), data: null, status: 'idle', statusText: 'Tayyor', jobId: null, results: [], total: 0, summary: null, filter: 'all' })

let sources = new WeakMap<object, EventSource>()

/** Eski UI bilan bir xil protokol: POST /run -> SSE /stream/<id> (result, done). */
export async function startBatch(tab: Tab, vars: Record<string, string>, onDone?: (b: BatchState) => void) {
  const b = (tab.state!.batch ??= newBatchState()) as BatchState
  const d = tab.draft!
  const s = b.settings
  let rows = b.data?.rows?.length ? b.data.rows : [{}]
  if (s.rowsMode === 'custom') rows = rows.slice(0, Math.max(1, s.count || 1))
  try { await prepareAuth(d, tab.ref, vars) } catch (e: any) { b.status = 'error'; b.statusText = e.message; return }
  let spec: Record<string, any>
  try { spec = specFor(d, tab.ref, vars) } catch (e: any) { b.status = 'error'; b.statusText = e.message; return }
  Object.assign(spec, { delay: s.delay, timeout: s.timeout, concurrency: s.concurrency, retry_count: s.retry, ssl_verify: s.ssl, rows })
  b.results = []; b.summary = null; b.total = rows.length; b.status = 'running'; b.statusText = `${rows.length} ta so'rov yuborilmoqda...`
  tab.state!.mode = 'batch'
  try {
    const r = await post('/run', spec)
    b.jobId = r.job_id
  } catch (e: any) { b.status = 'error'; b.statusText = 'Xatolik: ' + e.message; return }
  const src = eventSource('/stream/' + b.jobId)
  sources.set(b, src)
  src.addEventListener('result', (ev: MessageEvent) => {
    const item = JSON.parse(ev.data)
    b.results.push(item)
    b.statusText = `${item.index} / ${item.total}`
  })
  src.addEventListener('done', (ev: MessageEvent) => {
    const sm = JSON.parse(ev.data)
    src.close(); b.summary = sm; b.jobId = null
    b.status = sm.stopped ? 'stopped' : 'done'
    b.statusText = sm.stopped ? `To'xtatildi — ${sm.completed} ta yuborildi` : `Bajarildi — ${sm.successful} muvaffaqiyatli, ${sm.failed} xatolik`
    onDone?.(b)
  })
  src.onerror = () => { if (b.status === 'running') { src.close() } }
}
export async function stopBatch(tab: Tab) {
  const b = tab.state?.batch as BatchState | undefined
  if (b?.jobId) await post('/stop/' + b.jobId)
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
