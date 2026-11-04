<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Icon from './Icon.vue'
import { applyScriptResult, scriptsFor } from '../lib/scripts'
import { logRequest, logResponse, push as pushLog } from '../lib/console'
import { activity, askRunGuard, fmtMs } from '../lib/ui'
import { isProd } from '../lib/envkind'
import { useTree } from '../stores/tree'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { post } from '../api/client'
import { draftFromItem } from '../lib/draft'
import { prepareAuth, specFor } from '../lib/scope'
import { parseDataFile, isDataFile } from '../lib/datafile'
import DataPreview from './DataPreview.vue'
import { isFolder, type RequestItem, type TreeItem } from '../types/model'

const props = defineProps<{ tab: Tab }>()
const tree = useTree(), tabs = useTabs(), ws = useWorkspace()
props.tab.state ??= {}
const st = props.tab.state!      // reaktiv proksi (??= xom obyektni qaytaradi)
st.order ??= null; st.checked ??= {}; st.data ??= null; st.log ??= []; st.filter ??= 'all'; st.iterations ??= null; st.delay ??= 0; st.stopOnError ??= false
const [cid, fid] = props.tab.ref!.split(':')          // collection yoki papka (cid:fid) doirasi
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
  const known = order.filter(id => byId.has(id)).map(id => byId.get(id)!)
  return [...known, ...base.value.filter(x => !order.includes(x.id))]
})
// Sukut: faqat GET belgilangan (qo'lda belgilangani saqlanadi)
const isOn = (id: string) => st.checked[id] ?? items.value.find(x => x.id === id)?.method === 'GET'

const dragId = ref<string | null>(null)
const overIdx = ref<number | null>(null)
function drop(idx: number) {
  if (!dragId.value) return
  const ids = items.value.map(x => x.id)
  const from = ids.indexOf(dragId.value)
  ids.splice(from, 1)
  ids.splice(from < idx ? idx - 1 : idx, 0, dragId.value)
  st.order = ids
  dragId.value = overIdx.value = null
  tabs.touch(props.tab.id)
}

// Data fayl (CSV/JSON) — Bosqich 4 da iteratsiyalar bilan bog'lanadi
function loadData(name: string, text: string) {
  try { st.data = { name, rows: parseDataFile(name, text) } } catch { st.data = null }
  tabs.touch(props.tab.id)
}
defineExpose({ loadData })
;(props.tab as any)._loadData = loadData

const zone = ref(false)
const fileEl = ref<HTMLInputElement>()
async function onZoneDrop(e: DragEvent) {
  zone.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f && isDataFile(f)) { e.preventDefault(); e.stopPropagation(); loadData(f.name, await f.text()) }
}
async function onPick(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) loadData(f.name, await f.text()); (e.target as HTMLInputElement).value = '' }

const running = ref(false)
let stopFlag = false
const enabled = computed(() => items.value.filter(x => isOn(x.id)))
const rowsCount = computed(() => st.data?.rows?.length ?? 0)
const iterations = computed(() => Math.max(1, Number(st.iterations) || rowsCount.value || 1))
const getOnlyRun = ref(false)          // RunGuard: Prod'da faqat GET
const planned = computed(() => iterations.value * (getOnlyRun.value ? enabled.value.filter(x => x.method === 'GET').length : enabled.value.length))
const log = computed<any[]>(() => st.log)
const done = computed(() => log.value.length)
const okCount = computed(() => log.value.filter(r => typeof r.status === 'number' && r.status < 400).length)
const skippedCount = computed(() => log.value.filter(r => r.status === 'SKIPPED').length)
const failCount = computed(() => done.value - okCount.value - skippedCount.value)
const avg = computed(() => (done.value ? Math.round(log.value.reduce((n, r) => n + (r.time ?? 0), 0) / done.value * 1000) : 0))
const pct = computed(() => (planned.value ? Math.min(100, Math.round(done.value / planned.value * 100)) : 0))
const filtered = computed(() => log.value.filter(r => st.filter === 'all' || (st.filter === 'ok') === (typeof r.status === 'number' && r.status < 400) && r.status !== 'SKIPPED'))
const stat = (s: any) => (typeof s === 'number' && s < 400 ? 'ok' : s === 'SKIPPED' ? '' : 'err')
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
const strRow = (row: Record<string, unknown>) => Object.fromEntries(Object.entries(row ?? {}).map(([k, v]) => [k, v == null ? '' : String(v)]))

/** Prod faol bo'lsa avval RunGuard; keyin run(). */
async function start() {
  let onlyGet = false
  if (isProd(ws.activeEnv)) {
    const counts: Record<string, number> = {}
    for (const x of enabled.value) counts[x.method] = (counts[x.method] ?? 0) + iterations.value
    const a = await askRunGuard(ws.activeEnv!.name, counts)
    if (!a) return
    onlyGet = a === 'get'
  }
  await run(onlyGet)
}
async function run(onlyGet = false) {
  running.value = true; stopFlag = false; st.log = []; getOnlyRun.value = onlyGet
  const list = onlyGet ? enabled.value.filter(x => x.method === 'GET') : enabled.value
  const names = new Map<string, number>()
  list.forEach((x, i) => { if (!names.has(x.name)) names.set(x.name, i) })        // setNextRequest: shu nomli birinchi so'rov
  const total = iterations.value
  let steps = 0
  const maxSteps = Number((window as any).__MAX_RUN_STEPS) || 1000      // testlar uchun o'zgartirish mumkin
  outer: for (let it = 1; it <= total; it++) {
    const dataRow = rowsCount.value ? st.data.rows[(it - 1) % rowsCount.value] : {}
    const row = strRow(dataRow)
    let i = 0
    while (i < list.length) {
      if (stopFlag) break outer
      if (++steps > maxSteps) { pushLog({ level: 'error', text: `setNextRequest tsikli ${maxSteps} qadamdan oshdi — run to'xtatildi (cheksiz tsikl himoyasi)` }); break outer }
      const x = list[i]
      const ref_ = `${cid}:${x.id}`, draft = draftFromItem(x.item)
      let res: any
      try {
        await prepareAuth(draft, ref_, row)
        const spec = specFor(draft, ref_, row); spec.timeout = 30
        const scripts = scriptsFor(ref_, draft.scripts, x.name)
        if (scripts) Object.assign(spec, { scripts, ref: ref_, row: dataRow, scripts_info: { iteration: it - 1, iterationCount: total, requestName: x.name, requestId: x.id } })
        logRequest(spec.method, draft.url)
        res = await post('/run_one', spec)
        logResponse(res)
        await applyScriptResult(res.scripts, { ref: ref_ })
      } catch (e: any) { res = { status: 'ERR', time: 0, response: e.message }; pushLog({ level: 'error', text: `${x.name}: ${e.message}` }) }
      st.log.push({ iter: it, id: x.id, method: x.method, name: x.name, status: res.status, time: res.time ?? 0 })
      if (st.stopOnError && !(typeof res.status === 'number' && res.status < 400) && res.status !== 'SKIPPED') break outer
      if (st.delay > 0) await sleep(Number(st.delay))
      const sc = res.scripts
      if (sc?.next_set) {                                  // Postman: setNextRequest(nom) — o'sha so'rovga o'tadi, null — run to'xtaydi
        if (sc.next_request === null) break outer
        const j = names.get(sc.next_request)
        if (j === undefined) { pushLog({ level: 'error', text: `setNextRequest: «${sc.next_request}» nomli (tanlangan) so'rov topilmadi — run to'xtatildi` }); break outer }
        i = j
        continue
      }
      i++
    }
  }
  running.value = false
}
const stop = () => { stopFlag = true }
watch([running, done, planned], () => { if (running.value) activity[props.tab.id] = `Runner ${done.value}/${planned.value}`; else delete activity[props.tab.id] }, { immediate: true })
onBeforeUnmount(() => delete activity[props.tab.id])
const when = new Date().toLocaleString([], { hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="runner" data-testid="runner-tab">
    <aside class="cfg scroll" aria-label="Runner sozlamalari">
      <div style="display:flex;flex-direction:column;gap:6px">
        <span class="lbl">Collection</span>
        <div class="panel-box" style="padding:8px 12px;font-weight:500" data-testid="runner-collection">{{ scopeName }}</div>
      </div>

      <div style="display:flex;flex-direction:column;gap:6px">
        <div style="display:flex;align-items:center;justify-content:space-between"><span class="lbl">So'rovlar tartibi</span><span class="muted" style="font-size:12px" data-testid="runner-selcount">{{ enabled.length }} / {{ items.length }} tanlangan</span></div>
        <div class="panel-box" style="padding:4px" role="list">
          <div v-for="(x, i) in items" :key="x.id" class="req" data-testid="runner-item" role="listitem" draggable="true" :class="{ 'drop-before': overIdx === i }"
               @dragstart="dragId = x.id" @dragover.prevent="overIdx = i" @dragleave="overIdx = null" @drop.prevent="drop(i)" @dragend="dragId = overIdx = null">
            <span class="grip" aria-hidden="true"><Icon name="grip" :size="14" /></span>
            <input type="checkbox" :checked="isOn(x.id)" :aria-label="`${x.name} — Runner'ga qo'shish`" @change="st.checked[x.id] = ($event.target as HTMLInputElement).checked">
            <span class="m" :class="'m-' + x.method" style="width:46px;font:700 10.5px var(--font-mono)">{{ x.method }}</span>
            <span class="name" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span class="muted">{{ x.path }}</span>{{ x.name }}</span>
          </div>
          <div v-if="!items.length" class="empty" style="padding:16px">Collection'da so'rov yo'q</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">
        <label style="display:flex;flex-direction:column;gap:6px"><span class="lbl">Iteratsiyalar</span><input type="number" min="1" :placeholder="String(rowsCount || 1)" v-model.number="st.iterations" data-testid="runner-iterations" @input="tabs.touch(tab.id)"></label>
        <label style="display:flex;flex-direction:column;gap:6px"><span class="lbl">Kechikish, ms</span><input type="number" min="0" v-model.number="st.delay" data-testid="runner-delay" @input="tabs.touch(tab.id)"></label>
      </div>

      <div style="display:flex;flex-direction:column;gap:6px">
        <span class="lbl">Ma'lumot fayli</span>
        <div v-if="st.data" style="display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:var(--subtle)">
          <span style="width:30px;height:30px;border-radius:7px;background:var(--ok-bg);color:var(--ok);display:flex;align-items:center;justify-content:center;font:700 9.5px var(--font-ui)">{{ /\.json$/i.test(st.data.name) ? 'JSON' : 'CSV' }}</span>
          <span style="flex:1;min-width:0"><span style="display:block;font-weight:500;overflow:hidden;text-overflow:ellipsis" data-testid="runner-data-info">{{ st.data.name }}: {{ st.data.rows.length }} qator</span><span class="muted" style="display:block;font-size:12px">{{ Object.keys(st.data.rows[0] ?? {}).join(', ') }}</span></span>
          <button class="ib" aria-label="Faylni olib tashlash" data-testid="runner-data-clear" @click="st.data = null; tabs.touch(tab.id)"><Icon name="x" :size="15" /></button>
        </div>
        <div v-else class="drop-zone" :class="{ over: zone }" data-testid="runner-dropzone" @dragover.prevent="zone = true" @dragleave="zone = false" @drop="onZoneDrop">
          <span data-testid="runner-data-info" class="muted">CSV/JSON ni shu yerga tashlang</span><br><button class="sm" style="margin-top:6px" data-testid="runner-file-btn" @click="fileEl?.click()">Tanlash…</button>
          <input ref="fileEl" type="file" accept=".csv,.json" hidden data-testid="runner-file" @change="onPick">
        </div>
        <DataPreview v-if="st.data?.rows?.length" :rows="st.data.rows" :limit="3" />
      </div>

      <label style="display:flex;align-items:center;gap:10px"><input type="checkbox" v-model="st.stopOnError" data-testid="runner-stop-on-error" @change="tabs.touch(tab.id)">Birinchi xatoda to'xtash</label>

      <div style="margin-top:auto">
        <button v-if="running" class="stop" data-testid="runner-stop" @click="stop">To'xtatish</button>
        <button v-else class="go" data-testid="runner-run" :disabled="!planned" @click="start"><Icon name="play" :size="15" />Ishga tushirish · {{ planned }} so'rov</button>
      </div>
    </aside>

    <section class="out" aria-label="Natijalar">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <div><h1 style="margin:0;font-size:18px;font-weight:700">{{ scopeName }} — Runner</h1><p class="muted" style="margin:2px 0 0;font-size:12.5px">{{ log.length ? `Bugun, ${when} · ${iterations} iteratsiya` : 'Hali ishga tushirilmagan' }}</p></div>
      </div>
      <div>
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:6px"><span data-testid="runner-progress-label">{{ running ? 'Bajarilmoqda…' : (log.length ? 'Tugadi' : 'Tayyor') }} · {{ done }} / {{ planned }}</span><span>{{ pct }}%</span></div>
        <div class="progress" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100" aria-label="Bajarilish"><div :style="{ width: pct + '%' }" /></div>
      </div>
      <div class="stat-cards">
        <div class="stat"><div class="lbl">Bajarildi</div><div class="v" data-testid="runner-s-done">{{ done }}<small> / {{ planned }}</small></div></div>
        <div class="stat"><div class="lbl">Muvaffaqiyatli</div><div class="v ok" data-testid="runner-s-ok">{{ okCount }}</div></div>
        <div class="stat"><div class="lbl">Xato</div><div class="v err" data-testid="runner-s-fail">{{ failCount }}</div></div>
        <div class="stat"><div class="lbl">O'rtacha vaqt</div><div class="v" data-testid="runner-s-avg">{{ avg }}<small> ms</small></div></div>
      </div>
      <div class="result-table">
        <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border)">
          <div class="seg-group" role="group" aria-label="Filtr">
            <button v-for="f in ([['all', 'Hammasi'], ['ok', 'Muvaffaqiyatli'], ['err', 'Xato']] as const)" :key="f[0]" class="seg" :class="{ on: st.filter === f[0] }" :aria-pressed="st.filter === f[0]" :data-filter="f[0]" @click="st.filter = f[0]">{{ f[1] }}</button>
          </div>
        </div>
        <div class="res head"><span>Iter.</span><span>Metod</span><span>So'rov</span><span>Status</span><span>Vaqt</span></div>
        <div class="scroll" style="flex:1;overflow-y:auto" data-testid="runner-results">
          <div v-for="(r, i) in filtered" :key="i" class="res" data-testid="runner-row">
            <span class="muted" style="font-family:var(--font-mono)">#{{ r.iter }}</span>
            <span class="m" :class="'m-' + r.method" style="font:700 10.5px var(--font-mono)">{{ r.method }}</span>
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</span>
            <span><span class="status-pill" :class="stat(r.status)" data-testid="runner-result">{{ r.status }}</span></span>
            <span style="font:400 12.5px var(--font-mono)">{{ fmtMs(r.time) }}</span>
          </div>
          <div v-if="!filtered.length" class="empty" data-testid="runner-empty">{{ log.length ? 'Bu filtr bo\'yicha natija yo\'q' : 'Natijalar shu yerda chiqadi' }}</div>
        </div>
      </div>
    </section>
  </div>
</template>
