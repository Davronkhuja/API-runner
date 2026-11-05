<script setup lang="ts">
/** Collection Runner v2 (docs/design/Runner.dc.html): sozlamalar (yagona RunSettings), real-time SSE natijalar, Testlar ustuni, run raqami/tarixi, solishtirish va eksport. Hisoblash serverda, natijalar SQLite'da. */
import { computed, onMounted, ref, watch } from 'vue'
import Icon from './Icon.vue'
import Dialog from './Dialog.vue'
import RunSettings from './RunSettings.vue'
import { askRunGuard, fmtMs, showToast } from '../lib/ui'
import { useTree } from '../stores/tree'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useRunner, type LiveRun } from '../stores/runner'
import { parseDataFile, isDataFile } from '../lib/datafile'
import { buildPlan, compareRuns, defaultRunSettings, exportRun, getResult, listRuns, type RunInfo } from '../lib/runs'
import { isProd, runnerGetOnly } from '../lib/envkind'
import { isFolder, type RequestItem, type TreeItem } from '../types/model'

const props = defineProps<{ tab: Tab }>()
const tree = useTree(), tabs = useTabs(), ws = useWorkspace(), runner = useRunner()
props.tab.state ??= {}
const st = props.tab.state!
st.order ??= null; st.checked ??= {}; st.data ??= null; st.filter ??= 'all'; st.settings ??= defaultRunSettings(); st.runId ??= null
delete st.log; delete st.iterations; delete st.delay; delete st.stopOnError          // eski (v2.3) maydonlar
const [cid, fid] = props.tab.ref!.split(':')
const scopeNode = computed<any>(() => (fid ? tree.findItem(cid, fid) : tree.cols[cid]))
const scopeName = computed(() => scopeNode.value?.name ?? scopeNode.value?.info?.name ?? '')

function flat(items: TreeItem[], path = ''): { id: string; name: string; method: string; path: string; item: RequestItem }[] {
  return items.flatMap(i => isFolder(i) ? flat(i.item, path + i.name + ' / ') : [{ id: i.id, name: i.name, method: i.request.method, path, item: i }])
}
const base = computed(() => flat((fid ? (scopeNode.value?.item ?? []) : (tree.cols[cid]?.item ?? []))))
const items = computed(() => {
  const order: string[] | null = st.order
  if (!order) return base.value
  const byId = new Map(base.value.map(x => [x.id, x]))
  return [...order.filter(id => byId.has(id)).map(id => byId.get(id)!), ...base.value.filter(x => !order.includes(x.id))]
})
// Belgilash: oxirgi tanlov (shu collection/papka uchun eslab qolinadi) → bo'lmasa muhit sozlamasi (Prod: faqat GET; Dev/Test: hammasi)
const SEL_KEY = 'apirunner.runner.sel.v1'
const loadSel = (): Record<string, boolean> => { try { return JSON.parse(localStorage.getItem(SEL_KEY) ?? '{}')[props.tab.ref!] ?? {} } catch { return {} } }
const saveSel = () => { try { const all = JSON.parse(localStorage.getItem(SEL_KEY) ?? '{}'); all[props.tab.ref!] = { ...loadSel(), ...st.checked }; localStorage.setItem(SEL_KEY, JSON.stringify(all)) } catch { /* bloklangan */ } }
const remembered = loadSel()
const isOn = (id: string) => st.checked[id] ?? remembered[id] ?? (runnerGetOnly(ws.activeEnv) ? items.value.find(x => x.id === id)?.method === 'GET' : true)
const enabled = computed(() => items.value.filter(x => isOn(x.id)))

const dragId = ref<string | null>(null), overIdx = ref<number | null>(null)
function drop(idx: number) {
  if (!dragId.value) return
  const ids = items.value.map(x => x.id), from = ids.indexOf(dragId.value)
  ids.splice(from, 1); ids.splice(from < idx ? idx - 1 : idx, 0, dragId.value)
  st.order = ids; dragId.value = overIdx.value = null; tabs.touch(props.tab.id)
}
function loadData(name: string, text: string) {
  try { st.data = { name, rows: parseDataFile(name, text) } } catch { st.data = null; showToast("Fayl o'qilmadi", 'error') }
  tabs.touch(props.tab.id)
}
;(props.tab as any)._loadData = loadData
async function onDataFile(f: File) { if (isDataFile(f)) loadData(f.name, await f.text()) }

const rowsCount = computed(() => st.data?.rows?.length ?? 0)
const iterations = computed(() => Math.max(1, Number(st.settings.iterations) || rowsCount.value || 1))
const planned = computed(() => iterations.value * enabled.value.length)

// ── run holati ──
const run = ref<LiveRun | null>(null)
const history = ref<RunInfo[]>([])
const running = computed(() => run.value?.status === 'running')
const starting = ref(false)
async function refreshHistory() { history.value = await listRuns(props.tab.ref!).catch(() => []) }
async function view(id: number | null) {
  st.runId = id
  run.value = id ? await runner.load(id, props.tab.id) : null
  expanded.value = new Set()
}
onMounted(async () => { await refreshHistory(); if (st.runId) await view(st.runId) })
watch(() => run.value?.status, s => { if (s && s !== 'running') refreshHistory() })

async function start() {
  if (starting.value) return
  starting.value = true
  try { await begin() } finally { starting.value = false }
}
async function begin() {
  let onlyGet = false
  if (isProd(ws.activeEnv)) {
    const counts: Record<string, number> = {}
    for (const x of enabled.value) counts[x.method] = (counts[x.method] ?? 0) + iterations.value
    const a = await askRunGuard(ws.activeEnv!.name, counts)
    if (!a) return
    onlyGet = a === 'get'
  }
  const list = (onlyGet ? enabled.value.filter(x => x.method === 'GET') : enabled.value).map(x => ({ id: x.id, name: x.name, method: x.method, ref: `${cid}:${x.id}`, item: x.item }))
  try {
    const plan = await buildPlan({ ref: props.tab.ref!, name: scopeName.value, kind: 'runner' }, list, st.settings, st.data?.rows ?? [], ws.activeEnv?.name ?? '')
    const r = await runner.launch(plan, props.tab.id)
    st.runId = r.id; run.value = runner.live[r.id]; expanded.value = new Set(); tabs.touch(props.tab.id)
  } catch (e: any) { showToast(e.message, 'error') }
}
const stop = () => run.value && runner.stop(run.value.id)

const steps = computed(() => run.value?.steps ?? [])
const done = computed(() => steps.value.length)
const plannedNow = computed(() => (run.value ? run.value.planned : planned.value))
const sum = computed(() => run.value?.summary)
const okCount = computed(() => steps.value.filter(r => typeof r.status === 'number' && r.status < 400).length)
const skippedCount = computed(() => steps.value.filter(r => r.status === 'SKIPPED').length)
const failCount = computed(() => done.value - okCount.value - skippedCount.value)
const testsPass = computed(() => steps.value.reduce((n, r) => n + r.test_pass, 0))
const testsFail = computed(() => steps.value.reduce((n, r) => n + r.test_fail, 0))
const avg = computed(() => (done.value ? Math.round(steps.value.reduce((n, r) => n + (r.time ?? 0), 0) / done.value * 1000) : 0))
const pct = computed(() => (plannedNow.value ? Math.min(100, Math.round(done.value / plannedNow.value * 100)) : 0))
const stat = (s: any) => (typeof s === 'number' && s < 400 ? 'ok' : s === 'SKIPPED' ? '' : 'err')
const filtered = computed(() => steps.value.filter(r => st.filter === 'all' || (st.filter === 'ok') === (typeof r.status === 'number' && r.status < 400) && r.status !== 'SKIPPED'))
const when = computed(() => (run.value ? new Date(run.value.started * 1000).toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''))
const title = computed(() => `${scopeName.value} — ${run.value ? 'run #' + run.value.number : 'Runner'}`)

// ── qator tafsiloti (testlar + javob) ──
const expanded = ref<Set<string>>(new Set())
const bodies = ref<Record<string, string>>({})
const keyOf = (r: any) => `${r.iter}:${r.seq}`
async function toggle(r: any) {
  const k = keyOf(r), n = new Set(expanded.value)
  if (n.has(k)) n.delete(k); else { n.add(k); if (bodies.value[k] === undefined) bodies.value[k] = r.response ?? (r.dbId ? ((await getResult(r.dbId).catch(() => null))?.body ?? '') : '') }
  expanded.value = n
}

// ── solishtirish va eksport ──
const cmpOpen = ref(false), cmpId = ref<number | null>(null), cmp = ref<any>(null), expMenu = ref(false)
async function openCompare() {
  await refreshHistory()
  const prev = history.value.filter(h => h.id !== run.value?.id)
  cmpId.value = prev[0]?.id ?? null; cmpOpen.value = true
  if (cmpId.value) await doCompare()
}
async function doCompare() { cmp.value = run.value && cmpId.value ? await compareRuns(cmpId.value, run.value.id) : null }
const doExport = (f: 'json' | 'html' | 'junit') => { expMenu.value = false; if (run.value) exportRun(run.value.id, f, run.value.number) }
const fmtWhen = (t: number) => new Date(t * 1000).toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
defineExpose({ loadData })
</script>

<template>
  <div class="runner" data-testid="runner-tab">
    <aside class="cfg scroll" aria-label="Runner sozlamalari">
      <div style="display:flex;flex-direction:column;gap:6px">
        <span class="lbl">Collection</span>
        <div class="panel-box" style="padding:8px 12px;font-weight:500" data-testid="runner-collection">{{ scopeName }}</div>
      </div>

      <div style="display:flex;flex-direction:column;gap:6px">
        <div style="display:flex;align-items:center;justify-content:space-between"><span class="lbl">So'rovlar tartibi</span><span class="muted" style="font-size:var(--fs-sm)" data-testid="runner-selcount">{{ enabled.length }} / {{ items.length }} tanlangan</span></div>
        <div class="panel-box runner-list" role="list">
          <div v-for="(x, i) in items" :key="x.id" class="req" data-testid="runner-item" role="listitem" draggable="true" :class="{ 'drop-before': overIdx === i }"
               @dragstart="dragId = x.id" @dragover.prevent="overIdx = i" @dragleave="overIdx = null" @drop.prevent="drop(i)" @dragend="dragId = overIdx = null">
            <span class="grip" aria-hidden="true"><Icon name="grip" :size="14" /></span>
            <input type="checkbox" :checked="isOn(x.id)" :aria-label="`${x.name} — Runner'ga qo'shish`" @change="st.checked[x.id] = ($event.target as HTMLInputElement).checked; saveSel()">
            <span class="m" :class="'m-' + x.method" style="width:46px;font:700 var(--fs-xs) var(--font-mono)">{{ x.method }}</span>
            <span class="name" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span class="muted">{{ x.path }}</span>{{ x.name }}</span>
          </div>
          <div v-if="!items.length" class="empty" style="padding:16px">Collection'da so'rov yo'q</div>
        </div>
      </div>

      <RunSettings :model="st.settings" tid="runner" :data="st.data" mode="runner" @change="tabs.touch(tab.id)" @data-file="onDataFile" @data-clear="st.data = null; tabs.touch(tab.id)" />

      <div style="margin-top:auto">
        <button v-if="running" class="stop" data-testid="runner-stop" @click="stop">To'xtatish</button>
        <button v-else class="go" data-testid="runner-run" :disabled="!planned || starting" @click="start"><Icon name="play" :size="15" />Ishga tushirish · {{ planned }} so'rov</button>
      </div>
    </aside>

    <section class="out" aria-label="Natijalar">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <div><h1 style="margin:0;font-size:var(--fs-2xl);font-weight:700" data-testid="runner-title">{{ title }}</h1>
          <p class="muted" style="margin:2px 0 0;font-size:var(--fs-md)" data-testid="runner-sub">{{ run ? `${when} · ${run.env || 'muhit yo\'q'} · ${run.summary?.planned ? Math.max(1, Math.round((run.summary.planned as number) / Math.max(1, enabled.length))) : iterations} iteratsiya` : 'Hali ishga tushirilmagan' }}</p></div>
        <div style="flex:1" />
        <select v-if="history.length" class="sm" :value="st.runId ?? ''" aria-label="Run tarixi" data-testid="runner-history" @change="view(Number(($event.target as HTMLSelectElement).value) || null)">
          <option v-if="!st.runId" value="">Run tarixi ({{ history.length }})</option>
          <option v-for="h in history" :key="h.id" :value="h.id">#{{ h.number }} · {{ fmtWhen(h.started) }} · {{ h.summary.successful ?? 0 }}/{{ h.summary.completed ?? 0 }}</option>
        </select>
        <button data-testid="runner-compare" :disabled="!run || running || history.length < 2" @click="openCompare">Avvalgi run bilan solishtirish</button>
        <span style="position:relative">
          <button data-testid="runner-export" :disabled="!run || running" aria-haspopup="menu" :aria-expanded="expMenu" @click="expMenu = !expMenu">Eksport ▾</button>
          <div v-if="expMenu" class="menu" style="position:absolute;right:0;top:36px;z-index:20;min-width:140px" role="menu">
            <button role="menuitem" data-testid="runner-export-json" @click="doExport('json')">JSON</button><button role="menuitem" data-testid="runner-export-html" @click="doExport('html')">HTML</button><button role="menuitem" data-testid="runner-export-junit" @click="doExport('junit')">JUnit XML</button>
          </div>
        </span>
      </div>
      <p v-for="n in run?.notes ?? []" :key="n" class="state-error" style="padding:8px 12px;align-items:flex-start" role="alert">{{ n }}</p>
      <p v-if="sum?.error" class="state-error" style="padding:8px 12px" role="alert" data-testid="runner-error">{{ sum.error }}</p>
      <div>
        <div style="display:flex;justify-content:space-between;font-size:var(--fs-sm);color:var(--muted);margin-bottom:6px"><span data-testid="runner-progress-label">{{ running ? 'Bajarilmoqda…' : (run ? (run.status === 'stopped' ? "To'xtatildi" : 'Tugadi') : 'Tayyor') }} · {{ done }} / {{ plannedNow }}</span><span>{{ pct }}%</span></div>
        <div class="progress" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100" aria-label="Bajarilish"><div :style="{ width: pct + '%' }" /></div>
      </div>
      <div class="stat-cards">
        <div class="stat"><div class="lbl">Bajarildi</div><div class="v" data-testid="runner-s-done">{{ done }}<small> / {{ plannedNow }}</small></div></div>
        <div class="stat"><div class="lbl">Muvaffaqiyatli</div><div class="v ok" data-testid="runner-s-ok">{{ okCount }}</div></div>
        <div class="stat"><div class="lbl">Xato</div><div class="v err" data-testid="runner-s-fail">{{ failCount }}</div></div>
        <div class="stat"><div class="lbl">Testlar</div><div class="v" data-testid="runner-s-tests"><span class="ok">{{ testsPass }}</span><small> o'tdi · </small><span :class="{ err: testsFail }">{{ testsFail }}</span><small> yiqildi</small></div></div>
        <div class="stat"><div class="lbl">O'rtacha vaqt</div><div class="v" data-testid="runner-s-avg">{{ avg }}<small> ms</small></div></div>
      </div>
      <div class="result-table">
        <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border)">
          <div class="seg-group" role="group" aria-label="Filtr">
            <button v-for="f in ([['all', 'Hammasi'], ['ok', 'Muvaffaqiyatli'], ['err', 'Xato']] as const)" :key="f[0]" class="seg" :class="{ on: st.filter === f[0] }" :aria-pressed="st.filter === f[0]" :data-filter="f[0]" @click="st.filter = f[0]">{{ f[1] }}</button>
          </div>
        </div>
        <div class="res head"><span>Iter.</span><span>Metod</span><span>So'rov</span><span>Status</span><span>Vaqt</span><span>Testlar</span></div>
        <div class="scroll" style="flex:1;overflow-y:auto" data-testid="runner-results">
          <template v-for="r in filtered" :key="keyOf(r)">
            <div class="res" data-testid="runner-row" role="button" tabindex="0" :aria-expanded="expanded.has(keyOf(r))" @click="toggle(r)" @keydown.enter="toggle(r)">
              <span class="muted" style="font-family:var(--font-mono)">#{{ r.iter }}</span>
              <span class="m" :class="'m-' + r.method" style="font:700 var(--fs-xs) var(--font-mono)">{{ r.method }}</span>
              <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</span>
              <span><span class="status-pill" :class="stat(r.status)" data-testid="runner-result">{{ r.status }}</span></span>
              <span style="font:400 var(--fs-md) var(--font-mono)">{{ fmtMs(r.time) }}</span>
              <span data-testid="runner-tests-cell" :class="{ err: r.test_fail, ok: r.tests.length && !r.test_fail }">{{ r.tests.length ? `${r.test_pass}/${r.tests.length}` : '—' }}</span>
            </div>
            <div v-if="expanded.has(keyOf(r))" class="res-detail" data-testid="runner-detail">
              <p class="muted" style="margin:0 0 6px;overflow-wrap:anywhere">{{ r.url }}</p>
              <ul v-if="r.tests.length" class="res-tests"><li v-for="t in r.tests" :key="t.name" :class="t.skipped ? 'muted' : t.passed ? 'ok' : 'err'" data-testid="runner-test">{{ t.skipped ? '○' : t.passed ? '✓' : '✗' }} {{ t.name }}<small v-if="t.error"> — {{ t.error }}</small></li></ul>
              <pre v-if="bodies[keyOf(r)]" class="res-body" tabindex="0" aria-label="Javob matni" data-testid="runner-body">{{ bodies[keyOf(r)].slice(0, 20000) }}</pre>
              <p v-else-if="bodies[keyOf(r)] === ''" class="muted" style="margin:0">Javob matni saqlanmagan (sozlamalarda "Javoblarni saqlash" o'chiq yoki bo'sh javob).</p>
            </div>
          </template>
          <div v-if="!filtered.length" class="empty" data-testid="runner-empty">{{ steps.length ? "Bu filtr bo'yicha natija yo'q" : 'Natijalar shu yerda chiqadi' }}</div>
        </div>
      </div>
    </section>

    <Dialog v-if="cmpOpen" title="Run'larni solishtirish" testid="runner-compare-dialog" width="min(820px,92vw)" @close="cmpOpen = false">
      <p v-if="!cmpId" class="muted">Solishtirish uchun oldingi run kerak.</p>
      <template v-else>
        <label class="dlg-field"><span>Avvalgi run</span><select v-model="cmpId" data-testid="rc-select" @change="doCompare"><option v-for="h in history.filter(x => x.id !== run?.id)" :key="h.id" :value="h.id">#{{ h.number }} · {{ fmtWhen(h.started) }}</option></select></label>
        <p v-if="cmp" class="muted" data-testid="rc-summary">#{{ cmp.a.number }} → #{{ cmp.b.number }}: <b>{{ cmp.changed }}</b> ta so'rov statusi o'zgargan</p>
        <table v-if="cmp" class="kv rc-table" data-testid="rc-table"><thead><tr><th>Iter.</th><th>So'rov</th><th>Oldingi</th><th>Hozirgi</th><th>Δ vaqt</th></tr></thead>
          <tbody><tr v-for="(x, i) in cmp.rows" :key="i" :class="{ 'rc-changed': x.changed }" data-testid="rc-row"><td>#{{ x.iter }}</td><td :title="`${x.method} ${x.name}`">{{ x.method }} {{ x.name }}</td><td>{{ x.a ? x.a.status + ' · ' + fmtMs(x.a.time) : '—' }}</td><td>{{ x.b ? x.b.status + ' · ' + fmtMs(x.b.time) : '—' }}</td>
            <td>{{ x.delta == null ? '—' : (x.delta >= 0 ? '+' : '') + fmtMs(x.delta) }}</td></tr></tbody></table>
      </template>
    </Dialog>
  </div>
</template>
