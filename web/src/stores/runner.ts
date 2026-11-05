import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { getRun, startRun, stopRun, type RunStep, type RunSummary } from '../lib/runs'
import { activity } from '../lib/ui'
import { logScripts } from '../lib/console'
import { push as pushLog } from '../lib/console'
import { applyScriptResult } from '../lib/scripts'

export interface LiveRun {
  id: number; number: number; scope: string; scopeName: string; status: 'running' | 'done' | 'stopped' | 'error'
  planned: number; steps: (RunStep & { dbId?: number })[]; summary: Partial<RunSummary> | null; notes: string[]; started: number; env: string
}

/** Run'lar holati (komponent almashganda ham SSE obunasi tirik): jonli natijalar xotirada, asl nusxa SQLite'da. */
export const useRunner = defineStore('runner', () => {
  const live = reactive<Record<number, LiveRun>>({})

  function track(run: LiveRun, key: string) {
    const upd = () => { activity[key] = run.status === 'running' ? `Runner ${run.steps.length}/${run.planned}` : (undefined as any); if (run.status !== 'running') delete activity[key] }
    upd()
    return upd
  }

  async function launch(plan: any, tabId: string) {
    let run: LiveRun | null = null
    let upd = () => {}
    const handle = await startRun(plan, {
      start: d => { run!.planned = d.planned },
      step: s => { run!.steps.push(s); if (s.scripts) logScripts(s.scripts, { tabId, ref: s.ref }); upd() },
      note: m => run!.notes.push(m),
      done: d => { run!.status = d.status; if (d.error) pushLog({ level: 'error', text: d.error, tabId }); run!.summary = d; upd(); applyScriptResult({ available: true, tests: [], console: [], errors: [], changed: ['environment', 'globals', 'collection'] } as any, { tabId }).catch(() => {}) },
      lost: () => { if (run!.status === 'running') { run!.status = 'error'; run!.notes.push("Oqim uzildi — natijalar tarixda saqlangan"); upd() } },
    })
    run = reactive<LiveRun>({ id: handle.id, number: handle.number, scope: plan.scope, scopeName: plan.scope_name, status: 'running', planned: plan.iterations * plan.items.length, steps: [], summary: null, notes: [], started: Date.now() / 1000, env: plan.env_name }) as LiveRun
    live[handle.id] = run
    upd = track(run, tabId)
    return run
  }

  /** Tarixdan (SQLite) yuklash; run hali ketayotgan bo'lsa SSE'ga qayta ulanadi. */
  async function load(id: number, tabId?: string): Promise<LiveRun | null> {
    if (live[id]) return live[id]
    let r: any
    try { r = await getRun(id) } catch { return null }
    const run = reactive<LiveRun>({ id: r.id, number: r.number, scope: r.scope, scopeName: r.scope_name, status: r.status, planned: r.summary?.planned ?? r.results.length, summary: r.summary, notes: [], started: r.started, env: r.env_name,
      steps: r.results.map((x: any) => ({ run_id: r.id, iter: x.iter, seq: x.seq, index: 0, total: 0, id: x.item_id, name: x.name, method: x.method, url: x.url, status: /^\d+$/.test(x.status) ? Number(x.status) : x.status, time: x.time, size: x.size, error: x.error, tests: x.tests,
        test_pass: x.tests.filter((t: any) => t.passed && !t.skipped).length, test_fail: x.tests.filter((t: any) => !t.passed).length, successful: 0, failed: 0, dbId: x.id })) }) as LiveRun
    live[id] = run
    if (r.status === 'running' && tabId) { /* server oqimi ketayotgan bo'lsa — yangilash uchun qayta yuklash kifoya */ }
    return run
  }
  const stop = (id: number) => stopRun(id)
  return { live, launch, load, stop }
})
