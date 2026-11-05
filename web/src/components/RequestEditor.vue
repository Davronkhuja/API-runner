<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { sendTab, saveTab } from '../lib/actions'
import { fmtBytes, showToast } from '../lib/ui'
import { layout } from '../lib/view'
import { clampPane, drag, HANDLE, loadJSON, saveJSON } from '../lib/resize'
import KvTable from './KvTable.vue'
import CodeEditor from './CodeEditor.vue'
import ResponsePanel from './ResponsePanel.vue'
import SettingsForm from './SettingsForm.vue'
import ScriptsPanel from './ScriptsPanel.vue'
import InlineName from './InlineName.vue'
import { nameWarning, renameNode, suggestName, validateName } from '../lib/rename'
import { saveAsHandler } from '../lib/actions'
import { useWorkspace as _ws } from '../stores/workspace'
import BatchPanel from './BatchPanel.vue'
import { composeUrl, emptyKV, RAW_CT, paramsFromUrl, syncPathVars } from '../lib/draft'
import { fileInfo, guessType, isMissing, refreshFileInfo, uploadFile } from '../lib/files'
import { authSource, effectiveAuth, folderPath, scopedVars } from '../lib/scope'
import { useTree } from '../stores/tree'
import Icon from './Icon.vue'
import UrlEditor from './UrlEditor.vue'
import AuthEditor from './AuthEditor.vue'
import { applyCurlToDraft, parseCurl } from '../lib/curl'
import { generate, LANGS, snipReqFromDraft, type Lang } from '../lib/snippets'
import { esc, highlightCurl } from '../lib/highlight'

const props = defineProps<{ tab: Tab }>()
const wsStore = _ws()
const tabs = useTabs(), ws = useWorkspace(), hist = useHistory()
const d = computed(() => props.tab.draft!)
const section = computed({ get: () => props.tab.activeSection ?? 'params', set: v => (props.tab.activeSection = v) })
const touch = () => tabs.touch(props.tab.id)
const curlOpen = ref(false)
/** Skript xatolari + muvaffaqiyatsiz testlar (qator belgilash uchun). */
const scriptIssues = computed(() => {
  const sc = props.tab.response?.scripts
  return sc ? [...(sc.errors ?? []), ...(sc.tests ?? []).filter((t: any) => !t.passed && t.error).map((t: any) => ({ ...t.error, origin: t.origin }))] : []
})
const SECTIONS = ['params', 'headers', 'auth', 'body', 'scripts', 'settings', 'batch'] as const
const onSectionKey = (e: KeyboardEvent) => {
  const i = SECTIONS.indexOf(section.value as any), n = SECTIONS.length
  const to = e.key === 'ArrowRight' ? SECTIONS[(i + 1) % n] : e.key === 'ArrowLeft' ? SECTIONS[(i - 1 + n) % n] : null
  if (to) { e.preventDefault(); section.value = to; nextTick(() => document.querySelector<HTMLElement>(`[data-section=${to}]`)?.focus()) }
}
const tree = useTree()
const [refCid, refId] = (props.tab.ref ?? '').split(':') as [string, string | undefined]
const renamingCrumb = ref(false)
watch(() => tabs.renameRequest, id => { if (id === props.tab.id) { tabs.renameRequest = null; if (props.tab.ref) renamingCrumb.value = true; else askSave() } })
const askSave = () => { saveAsHandler.fn?.(props.tab) }
const crumbs = computed(() => {
  const [cid, id] = (props.tab.ref ?? '').split(':')
  const col = cid ? tree.cols[cid] : undefined
  if (!col) return ['Saqlanmagan so\'rov', d.value.name || 'Yangi so\'rov']
  return [col.info.name, ...folderPath(col, id).map(f => f.name), (tree.findItem(cid, id) as any)?.name ?? d.value.name]
})
const counts = computed(() => ({
  params: d.value.params.filter(p => p.enabled && p.key.trim()).length, headers: d.value.headers.filter(h => h.enabled && h.key.trim()).length,
  auth: 0, body: 0, settings: Object.keys(d.value.settings ?? {}).length, batch: 0,
} as Record<string, number>))
// URL maydoni — bir qatorli CodeMirror (UrlEditor); {{o'zgaruvchi}} chiplari shu yerdan baholanadi
const chipTip = ref<{ text: string; x: number; y: number } | null>(null)
const urlEl = ref<InstanceType<typeof UrlEditor>>()
function urlVar(name: string) {
  const kv = scopedVars(props.tab.ref)[name]
  if (kv) return { ok: true, title: `${name} → ${kv.scope}: ${kv.secret ? '••••' : kv.value}` }
  return name.startsWith('$') ? { ok: true, title: `${name} → dinamik (har so'rovda yangi)` } : { ok: false, title: `${name} — aniqlanmagan o'zgaruvchi` }
}
watch(() => JSON.stringify(scopedVars(props.tab.ref)), () => nextTick(() => urlEl.value?.rebuild()))
const lang = ref<Lang>('curl')
const curlText = computed(() => {
  if (!curlOpen.value) return ''
  try { return generate(lang.value, snipReqFromDraft(d.value, props.tab.ref)) } catch (e: any) { return `// Kod hosil qilib bo'lmadi: ${e.message}` }
})
const curlHtml = computed(() => (lang.value === 'curl' ? highlightCurl(curlText.value) : esc(curlText.value)))
const authSrc = computed(() => authSource(props.tab.ref))
// {{o'zgaruvchi}} chiplari: scope va qiymat hoverda, aniqlanmagani qizil
const urlNames = computed(() => new Set([...d.value.url.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)].map(m => m[1])))
const extraVars = computed(() => usedVars.value.filter(v => !urlNames.value.has(v.name)))
const usedVars = computed(() => {
  const dd = d.value, text = [dd.url, dd.body.raw, ...dd.headers.flatMap(h => [h.key, h.value]), ...dd.params.flatMap(p => [p.key, p.value]), dd.auth.token, dd.auth.user, dd.auth.pass, dd.auth.custom].join('\n')
  const known = scopedVars(props.tab.ref)
  return [...new Set([...text.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)].map(m => m[1]))].map(name => {
    const v = known[name]
    if (v) return { name, ok: true, title: `${v.scope}: ${v.secret ? '••••' : v.value}` }
    if (name.startsWith('$')) return { name, ok: true, title: 'Dinamik o\'zgaruvchi (har so\'rovda yangi)' }
    return { name, ok: false, title: 'Aniqlanmagan o\'zgaruvchi' }
  })
})
const autoCT = computed(() => (d.value.body.mode === 'raw' && RAW_CT[d.value.body.rawLang ?? 'text']) || (({ json: 'application/json', graphql: 'application/json', binary: d.value.body.file.name ? guessType(d.value.body.file.name) : 'application/octet-stream', form: 'application/x-www-form-urlencoded', multipart: 'multipart/form-data' } as Record<string, string>)[d.value.body.mode] ?? ''))
const effectiveCT = computed(() => (d.value.body.mode === 'json' || d.value.body.mode === 'raw') && d.value.body.contentType ? d.value.body.contentType : autoCT.value)
function onEsc(e: KeyboardEvent) { if (e.key === 'Escape' && curlOpen.value) curlOpen.value = false }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
// So'rov / javob ajratgichi: javob ulushi (foiz) har joylashuv uchun alohida saqlanadi; har ikki qism kamida 120px
const SPLIT_KEY = 'apirunner.split.v1'
const ratios = reactive(loadJSON(SPLIT_KEY, { stack: 0.5, side: 0.5 }))
const workEl = ref<HTMLElement>(), workSize = ref(0), respMax = ref(false)
const avail = computed(() => Math.max(0, workSize.value - HANDLE))
const respPx = computed(() => clampPane(avail.value, ratios[layout.value] * avail.value))
const respStyle = computed(() => (respMax.value ? {} : layout.value === 'side' ? { flex: 'none', width: respPx.value + 'px' } : { flex: 'none', height: respPx.value + 'px' }))
let ro: ResizeObserver | undefined
const measure = () => { const w = workEl.value; if (w) workSize.value = layout.value === 'side' ? w.clientWidth : w.clientHeight }
onMounted(() => { measure(); ro = new ResizeObserver(measure); if (workEl.value) ro.observe(workEl.value) })
onBeforeUnmount(() => ro?.disconnect())
watch(layout, () => nextTick(measure))
const setResp = (px: number) => { ratios[layout.value] = avail.value ? clampPane(avail.value, px) / avail.value : 0.5 }
function startResize(e: PointerEvent) {
  const start = respPx.value
  respMax.value = false
  drag(e, layout.value === 'side' ? 'x' : 'y', d => setResp(start - d), () => saveJSON(SPLIT_KEY, ratios))
}
function nudge(delta: number) { respMax.value = false; setResp(respPx.value + delta); saveJSON(SPLIT_KEY, ratios) }
function resetSplit() { respMax.value = false; ratios[layout.value] = 0.5; saveJSON(SPLIT_KEY, ratios) }
function copyCurl() { navigator.clipboard?.writeText(curlText.value); showToast('Nusxalandi', 'success') }
function beautify() {
  try { d.value.body.raw = JSON.stringify(JSON.parse(d.value.body.raw), null, 2); touch() } catch { showToast('JSON noto\'g\'ri — formatlab bo\'lmadi', 'warn') }
}
const showHist = ref(false)
const hideHist = () => { setTimeout(() => (showHist.value = false), 150) }
const reqEl = ref<HTMLElement>(), respEl = ref<HTMLElement>()
const binInput = ref<HTMLInputElement>()
const binOver = ref(false)
async function setBinary(f: File) {
  try { const u = await uploadFile(f); d.value.body.file = { path: u.ref, name: u.name }; touch() }
  catch (e: any) { showToast('Fayl yuklanmadi: ' + (e?.message ?? ''), 'error') }
}
async function pickBinary(e: Event) {
  const el = e.target as HTMLInputElement, f = el.files?.[0]
  el.value = ''
  if (f) await setBinary(f)
}
function onBinDrop(e: DragEvent) { binOver.value = false; const f = e.dataTransfer?.files?.[0]; if (f) setBinary(f) }
const binMissing = computed(() => !!d.value.body.file.path && isMissing(d.value.body.file.path))
const binSize = computed(() => { const i = fileInfo[d.value.body.file.path]; return i ? fmtBytes(i.size) : '' })
watch(() => d.value.body.mode === 'binary' ? d.value.body.file.path : '', p => { if (p) refreshFileInfo([p]) }, { immediate: true })

/** Params'dagi 📎 / sudrab tashlash: fayl Body → form-data'ga yangi File qatori bo'lib qo'shiladi (kalit — Params qatori nomi, bo'sh bo'lsa "file"). */
async function attachToBody(i: number, files: File[]) {
  if (!files.length) return
  try {
    const row = i >= 0 ? d.value.params[i] : null
    const key = row?.key?.trim() || 'file'
    const up = []
    for (const f of files) up.push(await uploadFile(f))
    const fields = d.value.body.mode === 'multipart' ? d.value.body.fields.filter(f => f.key || f.value || f.files?.length) : []
    for (const u of up) fields.push({ key, value: '', enabled: true, kind: 'file', files: [{ ref: u.ref, name: u.name }] })
    fields.push(emptyKV())
    d.value.body.fields = fields
    d.value.body.mode = 'multipart'
    if (row) d.value.params.splice(i, 1)
    d.value.url = composeUrl(d.value.url, d.value.params)
    touch(); section.value = 'body'
    showToast("Fayl Body → form-data'ga qo'shildi", 'success')
  } catch (e: any) { showToast('Fayl yuklanmadi: ' + (e?.message ?? ''), 'error') }
}

// Body turi: segmentli tugmalar (maketdagidek). "raw" segmenti JSON/Text formatini alohida select bilan tanlaydi.
const BODY_SEGS = [{ id: 'none', label: 'none' }, { id: 'multipart', label: 'form-data' }, { id: 'form', label: 'urlencoded' }, { id: 'raw', label: 'raw' }, { id: 'binary', label: 'binary' }, { id: 'graphql', label: 'GraphQL' }] as const
const segOn = (id: string) => (id === 'raw' ? d.value.body.mode === 'json' || d.value.body.mode === 'raw' : d.value.body.mode === id)
function setMode(id: (typeof BODY_SEGS)[number]['id']) {
  d.value.body.mode = id === 'raw' ? (d.value.body.mode === 'raw' ? 'raw' : 'json') : id
  touch()
}
const fmt = computed(() => (d.value.body.mode === 'json' ? 'json' : (d.value.body.rawLang ?? 'text') === 'text' ? 'raw' : d.value.body.rawLang!))
function setFormat(v: string) {
  if (v === 'json') d.value.body.mode = 'json'
  else { d.value.body.mode = 'raw'; d.value.body.rawLang = v === 'raw' ? 'text' : (v as 'html' | 'javascript') }
  touch()
}
function stepMode(dir: number) {
  const i = BODY_SEGS.findIndex(m => segOn(m.id))
  setMode(BODY_SEGS[(i + dir + BODY_SEGS.length) % BODY_SEGS.length].id)
  nextTick(() => document.querySelector<HTMLElement>('[data-testid=body-mode] [aria-checked=true]')?.focus())
}
/** POST/PUT tanlanganda (tana hali tanlanmagan bo'lsa) — raw JSON sukut bo'yicha. */
function onMethodChange() {
  if ((d.value.method === 'POST' || d.value.method === 'PUT') && d.value.body.mode === 'none') d.value.body.mode = 'json'
  touch()
}

// URL ↔ Params ikki tomonlama sinxron
function onUrlInput() { d.value.params = paramsFromUrl(d.value.url, d.value.params); d.value.pathVars = syncPathVars(d.value.url, d.value.pathVars); touch() }
function onParamsChange() { d.value.url = composeUrl(d.value.url, d.value.params); touch() }
// cURL paste (to'liq parser — paritet bandi; hozir minimal)
function onUrlPaste(text: string, prevent: () => void) {
  const parsed = parseCurl(text)
  if (!parsed) return
  prevent()
  applyCurlToDraft(d.value, parsed)
  d.value.pathVars = syncPathVars(d.value.url, [])
  touch()
}
const urlHist = computed(() => hist.urls.map(h => h.payload).filter((p: any) => p?.url && p.url.toLowerCase().includes(d.value.url.toLowerCase())).slice(0, 8))

// Scroll holatini tabda saqlash/tiklash
watch(() => props.tab.id, async () => { await nextTick(); if (reqEl.value) reqEl.value.scrollTop = props.tab.scroll.req; if (respEl.value) respEl.value.scrollTop = props.tab.scroll.resp }, { immediate: true })
</script>

<template>
  <div style="display:flex;flex-direction:column;flex:1;min-height:0" data-testid="request-editor">
    <div class="crumbs" data-testid="crumbs">
      <template v-for="(c, i) in crumbs" :key="i"><span v-if="i">/</span>
        <InlineName v-if="i === crumbs.length - 1" v-model:editing="renamingCrumb" class="cur" testid="crumb-rename" :value="c" :unsaved="!tab.ref" :warn="v => nameWarning(refCid, refId ?? null, v)" :suggest="suggestName" :validate="v => validateName(refCid, refId ?? null, v)" :commit="v => renameNode(refCid, refId ?? null, v)" label="So'rov nomi" @unsaved="askSave" />
        <span v-else>{{ c }}</span></template>
      <div style="flex:1" />
      <button class="sm" data-testid="save" :disabled="!tab.dirty && !!tab.ref" aria-keyshortcuts="Control+S Meta+S" @click="saveTab(tab)"><Icon name="save" :size="14" />Saqlash <span class="muted" style="font-size:11px">⌘S</span></button>
      <button class="sm" data-testid="curl-btn" title="Kod namunasi (cURL, Python, JS, Go, ...)" @click="curlOpen = true">&lt;/&gt; Kod</button>
    </div>
    <div class="urlbar" style="position:relative">
      <div class="urlfield">
        <select v-model="d.method" data-testid="method" aria-label="HTTP metod" :class="'m-' + d.method" @change="onMethodChange">
          <option v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']" :key="m" :class="'m-' + m">{{ m }}</option>
        </select>
        <div class="urlwrap">
          <UrlEditor ref="urlEl" v-model="d.url" :vars="urlVar" placeholder="https://api.example.com/endpoint/{{id}}  yoki  curl '...' ni bu yerga joylashtiring"
                     @input="onUrlInput" @paste="onUrlPaste" @focus="showHist = true; hist.load()" @blur="hideHist" @enter="sendTab(tab)" @tip="chipTip = $event" />
        </div>
      </div>
      <div v-if="showHist && urlHist.length" class="menu" style="position:absolute;left:18px;top:42px;right:150px" data-testid="url-history" role="listbox">
        <button v-for="(h, i) in urlHist" :key="i" role="option" @mousedown.prevent="d.method = h.method; d.url = h.url; d.pathVars = syncPathVars(d.url, d.pathVars); touch()"><b class="m" :class="'m-' + h.method" style="font:700 11px var(--font-mono);width:52px;text-align:left">{{ h.method }}</b> {{ h.url }}</button>
      </div>
      <button class="primary" data-testid="send" :disabled="tab.response?.loading" aria-keyshortcuts="Control+Enter Meta+Enter" @click="sendTab(tab)"><Icon name="send" :size="15" />{{ tab.response?.loading ? 'Yuborilmoqda…' : 'Yuborish' }}</button>
    </div>
    <div v-if="chipTip" class="tip-pop" role="tooltip" data-testid="chip-tip" :style="{ left: chipTip.x + 'px', top: chipTip.y + 'px' }">{{ chipTip.text }}</div>
    <div v-if="extraVars.length" class="var-chips" data-testid="var-chips"><span>Boshqa o'zgaruvchilar:</span>
      <span v-for="v in extraVars" :key="v.name" class="var-chip" :class="v.ok ? 'var-ok' : 'var-undef'" data-testid="var-chip" :title="v.title">{{ v.name }}</span>
    </div>
    <div ref="workEl" class="work" :class="{ side: layout === 'side', maxed: respMax }" data-testid="work">
    <div class="req-pane">
    <div class="sections" data-testid="sections" role="tablist" aria-label="So'rov bo'limlari" @keydown="onSectionKey">
      <button v-for="s in SECTIONS" :key="s" role="tab" :aria-selected="section === s" :tabindex="section === s ? 0 : -1" :class="{ on: section === s }" :data-section="s" @click="section = s">
        {{ { params: 'Params', headers: 'Headers', auth: 'Auth', body: 'Body', scripts: 'Scripts', settings: 'Sozlamalar', batch: 'Batch / Runner' }[s] }}<span v-if="counts[s]" class="badge">{{ counts[s] }}</span><span v-if="s === 'scripts' && (d.scripts.pre.trim() || d.scripts.test.trim())" class="dot-mark" aria-label="skript bor" data-testid="scripts-dot" />
      </button>
      <div style="flex:1" />
      <button data-testid="sections-cookies" class="ghost sm" style="height:26px;margin:0" @click="tabs.open('cookies', 'cookies', 'Cookie\'lar', { permanent: true })">Cookie'lar</button>
    </div>
    <div class="editor" :class="{ tall: section === 'scripts' }" ref="reqEl" @scroll="tab.scroll.req = ($event.target as HTMLElement).scrollTop">
      <template v-if="section === 'params'">
        <KvTable :rows="d.params" quick-attach testid="params-table" @change="onParamsChange" @attach="attachToBody" />
        <div v-if="d.pathVars.length" data-testid="path-vars" style="margin-top:12px">
          <b>Path variables</b>
          <table class="kv"><tbody><tr v-for="pv in d.pathVars" :key="pv.key"><td style="width:160px"><code>:{{ pv.key }}</code></td><td><input v-model="pv.value" placeholder="Qiymat" data-testid="path-var-val" @input="touch"></td></tr></tbody></table>
        </div>
      </template>
      <KvTable v-else-if="section === 'headers'" :rows="d.headers" testid="headers-table" @change="touch" />
      <AuthEditor v-else-if="section === 'auth'" :auth="d.auth" allow-inherit :source="authSrc" :scope-ref="tab.ref" @change="touch" />
      <ScriptsPanel v-else-if="section === 'scripts'" :scripts="d.scripts" scope="request" :errors="scriptIssues" :goto="tab.state?.scriptGoto" @change="touch" />
      <div v-else-if="section === 'settings'" data-testid="req-settings">
        <p class="muted">Faqat shu so'rov uchun qayta belgilash; "Sukut" — global sozlama (⚙ Sozlamalar).</p>
        <SettingsForm :model="d.settings" :fallback="wsStore.settings" @change="touch" />
      </div>
      <BatchPanel v-else-if="section === 'batch'" :tab="tab" />
      <div v-else data-testid="body-panel">
        <div class="seg-group body-seg" role="radiogroup" aria-label="Body turi" data-testid="body-mode" :data-value="d.body.mode" @keydown.left.prevent="stepMode(-1)" @keydown.right.prevent="stepMode(1)">
          <button v-for="m in BODY_SEGS" :key="m.id" class="seg" :class="{ on: segOn(m.id) }" role="radio" :aria-checked="segOn(m.id)" :tabindex="segOn(m.id) ? 0 : -1" :data-mode="m.id" @click="setMode(m.id)">{{ m.label }}</button>
        </div>
        <select v-if="d.body.mode === 'json' || d.body.mode === 'raw'" :value="fmt" class="body-fmt" aria-label="Body formati" data-testid="body-format" @change="setFormat(($event.target as HTMLSelectElement).value)">
          <option value="json">JSON</option><option value="raw">Text</option><option value="html">HTML</option><option value="javascript">JavaScript</option>
        </select>
        <button v-if="d.body.mode === 'json'" data-testid="beautify" style="margin-left:8px" @click="beautify" title="Cmd/Ctrl+B">Beautify</button>
        <input v-if="d.body.mode !== 'none' && d.body.mode !== 'form' && d.body.mode !== 'multipart' && d.body.mode !== 'graphql'" v-model="d.body.contentType" :placeholder="autoCT || 'Content-Type'" style="margin-left:8px;width:220px" data-testid="content-type" @input="touch">
        <span v-if="effectiveCT" class="muted" style="margin-left:8px" data-testid="content-type-auto">Content-Type: {{ effectiveCT }}</span>
        <CodeEditor v-if="d.body.mode === 'json' || d.body.mode === 'raw'" :key="fmt" v-model="d.body.raw" :lang="fmt === 'json' ? 'json' : fmt === 'html' ? 'html' : fmt === 'javascript' ? 'javascript' : 'raw'" testid="body-raw" placeholder='{ "key": "{{value}}" }' class="body-editor" @update:model-value="touch" @beautify="beautify" />
        <div v-else-if="d.body.mode === 'binary'" data-testid="binary-panel" class="bin-zone" :class="{ over: binOver, missing: binMissing }" style="margin-top:8px"
             @dragover.prevent="binOver = true" @dragleave="binOver = false" @drop.prevent="onBinDrop">
          <template v-if="d.body.file.path">
            <Icon name="file" :size="18" />
            <span class="bin-info"><b data-testid="binary-name">{{ d.body.file.name }}</b>
              <span v-if="binMissing" class="fd-miss" data-testid="binary-missing" role="alert">topilmadi, qayta tanlang</span>
              <span v-else class="muted" data-testid="binary-size">{{ binSize }}</span></span>
            <button class="linkbtn" data-testid="binary-replace" @click="binInput?.click()">Almashtirish</button>
            <button class="ghost" aria-label="Faylni olib tashlash" data-testid="binary-clear" @click="d.body.file = { path: '', name: '' }; touch()">×</button>
          </template>
          <template v-else><span class="muted">Faylni shu yerga tashlang yoki</span><button data-testid="binary-pick" @click="binInput?.click()">Fayl tanlash…</button></template>
          <input ref="binInput" type="file" hidden data-testid="binary-file" @change="pickBinary">
        </div>
        <div v-else-if="d.body.mode === 'graphql'" data-testid="graphql-panel" style="margin-top:8px">
          <b>Query</b><CodeEditor v-model="d.body.gql.query" lang="raw" testid="gql-query" placeholder="query { users { id name } }" class="body-editor" style="height:160px" @update:model-value="touch" />
          <b>Variables (JSON)</b><CodeEditor v-model="d.body.gql.variables" lang="json" testid="gql-vars" placeholder='{ "id": 1 }' class="body-editor" style="height:90px" @update:model-value="touch" />
        </div>
        <KvTable v-else-if="d.body.mode === 'form'" :rows="d.body.fields" testid="form-table" @change="touch" />
        <KvTable v-else-if="d.body.mode === 'multipart'" :rows="d.body.fields" formdata testid="formdata-table" @change="touch" />
      </div>
    </div>
    </div>
    <div class="v-resizer" data-testid="resp-resizer" role="separator" :aria-orientation="layout === 'side' ? 'vertical' : 'horizontal'" :aria-valuenow="Math.round(ratios[layout] * 100)" aria-valuemin="0" aria-valuemax="100" aria-label="Javob paneli o'lchami (ikki marta bosish — 50/50)" tabindex="0" @pointerdown="startResize" @dblclick="resetSplit" @keydown.up.prevent="nudge(24)" @keydown.down.prevent="nudge(-24)" @keydown.left.prevent="nudge(24)" @keydown.right.prevent="nudge(-24)">
      <button class="resize-max" data-testid="resp-maximize" :aria-pressed="respMax" :title="respMax ? 'So\'rov panelini qaytarish' : 'Javobni to\'liq ochish'" :aria-label="respMax ? 'So\'rov panelini qaytarish' : 'Javobni to\'liq ochish'" @pointerdown.stop @dblclick.stop @click="respMax = !respMax"><Icon :name="respMax ? 'chevron-down' : 'chevron-up'" :size="13" /></button>
    </div>
    <section class="resp" ref="respEl" data-testid="response" aria-label="Javob" :style="respStyle" @scroll="tab.scroll.resp = ($event.target as HTMLElement).scrollTop">
      <ResponsePanel :tab="tab" />
    </section>
    </div>
  </div>
  <div v-if="curlOpen" class="overlay" @click.self="curlOpen = false"><div class="dialog" role="dialog" aria-modal="true" aria-label="Kod namunasi" style="width:640px" data-testid="curl-drawer">
    <div style="display:flex;gap:8px;align-items:center"><b style="flex:1">Kod</b><select v-model="lang" aria-label="Til" data-testid="snippet-lang"><option v-for="l in LANGS" :key="l[0]" :value="l[0]">{{ l[1] }}</option></select><button data-testid="curl-copy" @click="copyCurl">Nusxa</button><button @click="curlOpen = false">×</button></div>
    <pre style="margin-top:10px" data-testid="curl-output" v-html="curlHtml" /></div></div>
</template>