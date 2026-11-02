<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { newBatchState, startBatch, stopBatch, statsOf, toCSV, download, type BatchState } from '../lib/batch'
import { fmtBytes, fmtMs, showToast } from '../lib/ui'
import { parseDataFile, isDataFile } from '../lib/datafile'
import { highlightJson } from '../lib/highlight'
import DataPreview from './DataPreview.vue'

const props = defineProps<{ tab: Tab }>()
const tabs = useTabs(), ws = useWorkspace(), hist = useHistory()
props.tab.state ??= {}
props.tab.state.batch ??= newBatchState()
const b = computed(() => props.tab.state!.batch as BatchState)
const st = computed(() => statsOf(b.value))
const collapsed = ref(false)
const full = ref<any | null>(null)
const showCmp = ref(false)
const cmpId = ref<number | null>(null)
const hdrOpen = ref<Record<number, boolean>>({})
const folded = ref<Record<number, boolean>>({})
const foldAll = (v: boolean) => { folded.value = v ? Object.fromEntries(b.value.results.map(r => [r.index, true])) : {} }
const fileInput = ref<HTMLInputElement>()
const visible = computed(() => b.value.results.filter(r => b.value.filter === 'all' || (b.value.filter === 'error' ? r.error : !r.error)))
const pct = computed(() => (b.value.total ? (b.value.results.length / b.value.total) * 100 : 0))
const last60 = computed(() => b.value.results.slice(-60))
const maxT = computed(() => Math.max(0.001, ...last60.value.map(r => r.time)))
const badge = (s: any) => (typeof s === 'number' ? (s < 300 ? 'ok' : 'err') : 'err')
const body = (r: any) => (typeof r.response === 'string' ? r.response : JSON.stringify(r.response, null, 2))

async function loadFile(f: File) {
  try { b.value.data = { name: f.name, rows: parseDataFile(f.name, await f.text()) } } catch (err: any) { showToast('Fayl o\'qilmadi: ' + err.message, 'error') }
}
const onFile = (e: Event) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) loadFile(f) }
const zone = ref(false)
function onZoneDrop(e: DragEvent) {
  zone.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f && isDataFile(f)) { e.preventDefault(); e.stopPropagation(); loadFile(f) }
}
function onEsc(e: KeyboardEvent) { if (e.key === 'Escape') { if (full.value) full.value = null; else if (showCmp.value) showCmp.value = false } }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
async function run() {
  await tabs.flush()
  await startBatch(props.tab, {}, async done => {
    try { await hist.add('run', { ts: Date.now(), label: props.tab.draft!.url, count: done.results.length, results: done.results.map(r => ({ index: r.index, status: r.status, time: r.time, size: r.size, url: r.url })) }) } catch { /* tarix yozilmasa ham natija ko'rinadi */ }
  })
}
const runs = computed(() => hist.runs)
const cmpRun = computed(() => runs.value.find(r => r.id === cmpId.value))
async function openCmp() { await hist.load(); showCmp.value = true; cmpId.value = hist.runs[1]?.id ?? hist.runs[0]?.id ?? null }
const cmpRows = computed(() => {
  const cur = b.value.results, old = cmpRun.value?.payload.results ?? []
  return Array.from({ length: Math.max(cur.length, old.length) }, (_, i) => ({ i: i + 1, a: old[i], b: cur[i] }))
})
const copy = (t: string) => { navigator.clipboard?.writeText(t); showToast('Nusxalandi', 'success') }
const toggleHdr = (i: number) => (hdrOpen.value[i] = !hdrOpen.value[i])
void tabs
</script>

<template>
  <div data-testid="batch-panel">
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end" data-testid="batch-settings">
      <label>Data fayl (CSV/JSON)<br>
        <button data-testid="batch-file-btn" @click="fileInput?.click()">Tanlash…</button>
        <input ref="fileInput" type="file" accept=".csv,.json" hidden data-testid="batch-file" @change="onFile">
      </label>
      <span class="muted" data-testid="batch-data-info">{{ b.data ? `${b.data.name}: ${b.data.rows.length} qator` : 'faylsiz — 1 ta so\'rov' }}</span>
      <button v-if="b.data" class="ghost" data-testid="batch-file-clear" @click="b.data = null">× tozalash</button>
      <label>Qatorlar<br><select v-model="b.settings.rowsMode" data-testid="batch-rows-mode"><option value="all">Hammasi</option><option value="custom">Soni</option></select></label>
      <label v-if="b.settings.rowsMode === 'custom'">Soni<br><input type="number" min="1" v-model.number="b.settings.count" style="width:70px" data-testid="batch-count"></label>
      <label>Kechikish (s)<br><input type="number" min="0" step="0.1" v-model.number="b.settings.delay" style="width:70px" data-testid="batch-delay"></label>
      <label>Timeout (s)<br><input type="number" min="1" max="600" v-model.number="b.settings.timeout" style="width:70px" data-testid="batch-timeout"></label>
      <label>Parallel<br><input type="number" min="1" max="10" v-model.number="b.settings.concurrency" style="width:60px" data-testid="batch-concurrency"></label>
      <label>Retry<br><input type="number" min="0" max="5" v-model.number="b.settings.retry" style="width:60px" data-testid="batch-retry"></label>
      <label><input type="checkbox" v-model="b.settings.ssl" data-testid="batch-ssl"> SSL tekshirish</label>
      <button class="primary" data-testid="batch-run" :disabled="b.status === 'running'" @click="run">▶ RUN</button>
      <button data-testid="batch-stop" :disabled="b.status !== 'running'" @click="stopBatch(tab)">■ STOP</button>
    </div>

    <div class="drop-zone" :class="{ over: zone }" data-testid="batch-dropzone" @dragover.prevent="zone = true" @dragleave="zone = false" @drop="onZoneDrop">CSV/JSON faylni shu yerga tashlang</div>
    <DataPreview v-if="b.data?.rows.length" :rows="b.data.rows" />

    <div v-if="b.status !== 'idle'" style="margin-top:14px" data-testid="results-pane">
      <div style="display:flex;align-items:center;gap:8px">
        <span :class="b.status === 'done' ? 'ok' : b.status === 'error' ? 'err' : 'muted'" data-testid="batch-status">{{ b.statusText }}</span>
        <button class="ghost" @click="collapsed = !collapsed" title="Yig'ish">{{ collapsed ? '▸' : '▾' }}</button>
        <button class="ghost" data-testid="fold-all" title="Kartalarni yig'ish / yoyish" @click="foldAll(!b.results.every(r => folded[r.index]))">⇅</button>
        <span style="flex:1" />
        <button data-testid="export-json" :disabled="!b.results.length" @click="download('results.json', JSON.stringify(b.results, null, 2), 'application/json')">JSON</button>
        <button data-testid="export-csv" :disabled="!b.results.length" @click="download('results.csv', toCSV(b.results), 'text/csv')">CSV</button>
        <button data-testid="compare-open" @click="openCmp">Solishtirish</button>
        <button class="ghost" title="Yopish" data-testid="results-close" @click="b.status = 'idle'; b.results = []; tab.state!.mode = undefined">×</button>
      </div>
      <template v-if="!collapsed">
        <div style="height:6px;background:var(--bg3);border-radius:3px;margin:8px 0"><div :style="{ width: pct + '%', height: '100%', background: b.status === 'stopped' ? 'var(--warn)' : 'var(--ac)', borderRadius: '3px' }" data-testid="progress-fill" /></div>
        <div class="muted" data-testid="progress-count">{{ b.results.length }} / {{ b.total }}</div>
        <div style="display:flex;gap:16px;margin:8px 0" data-testid="stats">
          <span>Jami <b data-testid="s-total">{{ st.total }}</b></span><span class="ok">OK <b data-testid="s-ok">{{ st.ok }}</b></span><span class="err">Xato <b data-testid="s-err">{{ st.err }}</b></span>
          <span>O'rtacha <b data-testid="s-avg">{{ st.avg == null ? '—' : fmtMs(st.avg) }}</b></span>
          <span class="muted">2xx <b data-testid="s-2xx">{{ st.s2 }}</b> · 4xx <b data-testid="s-4xx">{{ st.s4 }}</b> · 5xx <b data-testid="s-5xx">{{ st.s5 }}</b></span>
        </div>
        <div v-if="last60.length" data-testid="time-chart" style="display:flex;align-items:flex-end;gap:1px;height:40px;margin-bottom:8px">
          <div v-for="(r, i) in last60" :key="i" data-testid="time-bar" :title="fmtMs(r.time)" :style="{ flex: 1, height: Math.max(2, (r.time / maxT) * 40) + 'px', background: r.error ? 'var(--err)' : 'var(--ok)' }" />
        </div>
        <div style="display:flex;gap:4px;margin-bottom:8px" data-testid="filters">
          <button v-for="f in (['all', 'success', 'error'] as const)" :key="f" :class="{ primary: b.filter === f }" :data-filter="f" @click="b.filter = f">{{ { all: 'Hammasi', success: 'Muvaffaqiyatli', error: 'Xato' }[f] }}</button>
        </div>
        <div v-for="r in visible" :key="r.index" class="result-card" data-testid="result-card" style="border:1px solid var(--bd);border-radius:6px;padding:8px;margin-bottom:6px">
          <div style="display:flex;gap:10px;align-items:center">
            <span class="status-pill" :class="badge(r.status)">{{ r.status }}</span><span>#{{ r.index }}</span><span>{{ fmtMs(r.time) }}</span><span>{{ fmtBytes(r.size) }}</span>
            <span v-if="r.retries" class="muted" data-testid="retry-badge">↻{{ r.retries }}</span>
            <span class="muted" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">{{ r.url }}</span>
            <button class="ghost" data-testid="card-toggle" title="Yig'ish" @click="folded[r.index] = !folded[r.index]">{{ folded[r.index] ? '▸' : '▾' }}</button>
            <button class="ghost" @click="toggleHdr(r.index)">Headers</button>
            <button class="ghost" data-testid="copy-resp" @click="copy(body(r))">Nusxa</button>
            <button class="ghost" data-testid="open-full" @click="full = r">⤢</button>
          </div>
          <pre v-if="hdrOpen[r.index] && !folded[r.index]" class="muted">{{ Object.entries(r.resp_headers ?? {}).map(([k, v]) => k + ': ' + v).join('\n') }}</pre>
          <pre v-if="!folded[r.index]" data-testid="card-body" style="max-height:140px;overflow:auto;margin-top:6px" v-html="highlightJson(body(r).slice(0, 100_000))" />
        </div>
      </template>
    </div>

    <div v-if="full" class="overlay" data-testid="result-full" @click.self="full = null" @keydown.esc="full = null" tabindex="0">
      <div class="dialog" style="width:80vw;max-height:85vh;overflow:auto">
        <div style="display:flex;gap:10px;align-items:center"><span class="status-pill" :class="badge(full.status)">{{ full.status }}</span><span>{{ fmtMs(full.time) }}</span><span class="muted" style="flex:1">{{ full.url }}</span>
          <button @click="copy(body(full))">Nusxa</button><button data-testid="full-txt" @click="download('result.txt', body(full))">TXT</button><button data-testid="full-close" @click="full = null">×</button></div>
        <pre style="margin-top:10px" data-testid="full-body" v-html="highlightJson(body(full).slice(0, 200_000))" />
      </div>
    </div>

    <div v-if="showCmp" class="overlay" data-testid="cmp-modal" @click.self="showCmp = false">
      <div class="dialog" style="min-width:560px">
        <div style="display:flex;gap:10px"><b style="flex:1">Run'larni solishtirish</b><button @click="showCmp = false">×</button></div>
        <p v-if="runs.length < 1" class="muted">Solishtirish uchun oldingi run kerak.</p>
        <template v-else>
          <select v-model="cmpId" data-testid="cmp-select"><option v-for="r in runs" :key="r.id" :value="r.id">{{ new Date(r.ts * 1000).toLocaleString() }} — {{ r.payload.label }} ({{ r.payload.count }})</option></select>
          <table class="kv" style="margin-top:8px" data-testid="cmp-table"><thead><tr><th>#</th><th>Oldingi</th><th>Hozirgi</th><th>Δ vaqt</th></tr></thead>
            <tbody><tr v-for="x in cmpRows" :key="x.i"><td>{{ x.i }}</td><td>{{ x.a ? x.a.status + ' · ' + fmtMs(x.a.time) : '—' }}</td><td>{{ x.b ? x.b.status + ' · ' + fmtMs(x.b.time) : '—' }}</td>
              <td>{{ x.a && x.b ? ((x.b.time - x.a.time) >= 0 ? '+' : '') + fmtMs(x.b.time - x.a.time) : '—' }}</td></tr></tbody></table>
        </template>
      </div>
    </div>
  </div>
</template>
