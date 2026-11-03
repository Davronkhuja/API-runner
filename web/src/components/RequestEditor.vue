<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { sendTab, saveTab } from '../lib/actions'
import { showToast } from '../lib/ui'
import KvTable from './KvTable.vue'
import CodeEditor from './CodeEditor.vue'
import ResponsePanel from './ResponsePanel.vue'
import SettingsForm from './SettingsForm.vue'
import ScriptsPanel from './ScriptsPanel.vue'
import { useWorkspace as _ws } from '../stores/workspace'
import BatchPanel from './BatchPanel.vue'
import { composeUrl, paramsFromUrl, syncPathVars } from '../lib/draft'
import { effectiveAuth, folderPath, scopedVars } from '../lib/scope'
import { useTree } from '../stores/tree'
import Icon from './Icon.vue'
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
const crumbs = computed(() => {
  const [cid, id] = (props.tab.ref ?? '').split(':')
  const col = cid ? tree.cols[cid] : undefined
  if (!col) return ['Saqlanmagan so\'rov', d.value.name || 'Yangi so\'rov']
  return [col.info.name, ...folderPath(col, id).map(f => f.name), d.value.name]
})
const counts = computed(() => ({
  params: d.value.params.filter(p => p.enabled && p.key.trim()).length, headers: d.value.headers.filter(h => h.enabled && h.key.trim()).length,
  auth: 0, body: 0, settings: Object.keys(d.value.settings ?? {}).length, batch: 0,
} as Record<string, number>))
// URL ustidagi {{o'zgaruvchi}} chiplari: matn `<input>` da (shaffof), rangli nusxasi ustida; so'rov qismi (?…) xira
const chipTip = ref<{ text: string; x: number; y: number } | null>(null)
function showTip(e: MouseEvent, text: string) { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); chipTip.value = { text, x: Math.max(8, r.left), y: r.bottom + 6 } }
const urlEl = ref<HTMLInputElement>(), urlScroll = ref(0)
const syncScroll = () => requestAnimationFrame(() => { urlScroll.value = urlEl.value?.scrollLeft ?? 0 })
const urlSegs = computed(() => {
  const known = scopedVars(props.tab.ref), out: { t: string; q: boolean; v?: { ok: boolean; title: string } }[] = []
  const url = d.value.url, qi = url.indexOf('?')
  let last = 0
  const push = (t: string, at: number, v?: { ok: boolean; title: string }) => t && out.push({ t, q: qi >= 0 && at >= qi, v })
  for (const m of url.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)) {
    push(url.slice(last, m.index), last)
    const name = m[1], kv = known[name]
    push(m[0], m.index!, kv ? { ok: true, title: `${name} → ${kv.scope}: ${kv.secret ? '••••' : kv.value}` } : name.startsWith('$') ? { ok: true, title: `${name} → dinamik (har so'rovda yangi)` } : { ok: false, title: `${name} — aniqlanmagan o'zgaruvchi` })
    last = m.index! + m[0].length
  }
  push(url.slice(last), last)
  return out
})
const lang = ref<Lang>('curl')
const curlText = computed(() => {
  if (!curlOpen.value) return ''
  try { return generate(lang.value, snipReqFromDraft(d.value, props.tab.ref)) } catch (e: any) { return `// Kod hosil qilib bo'lmadi: ${e.message}` }
})
const curlHtml = computed(() => (lang.value === 'curl' ? highlightCurl(curlText.value) : esc(curlText.value)))
const inheritNote = computed(() => { const t = effectiveAuth(d.value.auth, props.tab.ref).type; return t === 'none' ? 'Meros: ota papka/collection auth\'i yo\'q — Auth yuborilmaydi.' : `Meros: ${t} (ota papka/collection)` })
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
const autoCT = computed(() => ({ json: 'application/json', graphql: 'application/json', binary: 'application/octet-stream', form: 'application/x-www-form-urlencoded', multipart: 'multipart/form-data' } as Record<string, string>)[d.value.body.mode] ?? '')
const effectiveCT = computed(() => (d.value.body.mode === 'json' || d.value.body.mode === 'raw') && d.value.body.contentType ? d.value.body.contentType : autoCT.value)
function onEsc(e: KeyboardEvent) { if (e.key === 'Escape' && curlOpen.value) curlOpen.value = false }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
// Editor / javob ajratgichi (vertikal)
const respH = ref<number | null>(null)
function startResize(e: PointerEvent) {
  const startY = e.clientY, startH = respEl.value?.offsetHeight ?? 200
  const move = (ev: PointerEvent) => { respH.value = Math.max(80, startH + (startY - ev.clientY)) }
  const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
  window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
}
function nudge(dy: number) { respH.value = Math.max(80, (respH.value ?? respEl.value?.offsetHeight ?? 200) + dy) }
function copyCurl() { navigator.clipboard?.writeText(curlText.value); showToast('Nusxalandi', 'success') }
function beautify() {
  try { d.value.body.raw = JSON.stringify(JSON.parse(d.value.body.raw), null, 2); touch() } catch { showToast('JSON noto\'g\'ri — formatlab bo\'lmadi', 'warn') }
}
const showHist = ref(false)
const hideHist = () => { setTimeout(() => (showHist.value = false), 150) }
const reqEl = ref<HTMLElement>(), respEl = ref<HTMLElement>()
const binInput = ref<HTMLInputElement>()
async function pickBinary(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  const fd = new FormData(); fd.append('file', f)
  try {
    const r = await fetch('/upload_temp', { method: 'POST', body: fd, headers: { 'X-Session-Token': window.__API_TOKEN__ ?? '' } }).then(x => x.json())
    d.value.body.file = { path: r.path, name: r.name }; touch()
  } catch { showToast('Fayl yuklanmadi', 'error') }
}

// URL ↔ Params ikki tomonlama sinxron
function onUrlInput() { d.value.params = paramsFromUrl(d.value.url, d.value.params); d.value.pathVars = syncPathVars(d.value.url, d.value.pathVars); touch() }
function onParamsChange() { d.value.url = composeUrl(d.value.url, d.value.params); touch() }
// cURL paste (to'liq parser — paritet bandi; hozir minimal)
function onPaste(e: ClipboardEvent) {
  const parsed = parseCurl(e.clipboardData?.getData('text') ?? '')
  if (!parsed) return
  e.preventDefault()
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
      <template v-for="(c, i) in crumbs" :key="i"><span v-if="i">/</span><span :class="{ cur: i === crumbs.length - 1 }">{{ c }}</span></template>
      <div style="flex:1" />
      <button class="sm" data-testid="save" :disabled="!tab.dirty && !!tab.ref" aria-keyshortcuts="Control+S Meta+S" @click="saveTab(tab)"><Icon name="save" :size="14" />Saqlash <span class="muted" style="font-size:11px">⌘S</span></button>
      <button class="sm" data-testid="curl-btn" title="Kod namunasi (cURL, Python, JS, Go, ...)" @click="curlOpen = true">&lt;/&gt; Kod</button>
    </div>
    <div class="urlbar" style="position:relative">
      <div class="urlfield">
        <select v-model="d.method" data-testid="method" aria-label="HTTP metod" :class="'m-' + d.method" @change="touch">
          <option v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']" :key="m" :class="'m-' + m">{{ m }}</option>
        </select>
        <div class="urlwrap">
          <input ref="urlEl" v-model="d.url" class="hl" data-testid="url" aria-label="So'rov URL" spellcheck="false" autocomplete="off" placeholder="https://api.example.com/endpoint/{{id}}  yoki  curl '...' ni bu yerga joylashtiring"
                 @input="onUrlInput(); syncScroll()" @paste="onPaste" @focus="showHist = true; hist.load(); syncScroll()" @blur="hideHist" @scroll="syncScroll" @keyup="syncScroll" @click="syncScroll"
                 @keydown.enter="sendTab(tab)">
          <div class="hlx" aria-hidden="true"><div class="in" :style="{ transform: `translateX(${-urlScroll}px)` }"><template v-for="(g, i) in urlSegs" :key="i"
            ><span v-if="g.v" class="chip" :class="g.v.ok ? 'var-ok' : 'var-undef undef'" data-testid="var-chip" :data-tip="g.v.title" :aria-label="g.v.title" @mouseenter="showTip($event, g.v.title)" @mouseleave="chipTip = null" @mousedown.prevent="urlEl?.focus()">{{ g.t }}</span
            ><span v-else :class="{ q: g.q }">{{ g.t }}</span></template></div></div>
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
    <div class="sections" data-testid="sections" role="tablist" aria-label="So'rov bo'limlari" @keydown="onSectionKey">
      <button v-for="s in SECTIONS" :key="s" role="tab" :aria-selected="section === s" :tabindex="section === s ? 0 : -1" :class="{ on: section === s }" :data-section="s" @click="section = s">
        {{ { params: 'Params', headers: 'Headers', auth: 'Auth', body: 'Body', scripts: 'Scripts', settings: 'Sozlamalar', batch: 'Batch / Runner' }[s] }}<span v-if="counts[s]" class="badge">{{ counts[s] }}</span><span v-if="s === 'scripts' && (d.scripts.pre.trim() || d.scripts.test.trim())" class="dot-mark" aria-label="skript bor" data-testid="scripts-dot" />
      </button>
      <div style="flex:1" />
      <button data-testid="sections-cookies" class="ghost sm" style="height:26px;margin:0" @click="tabs.open('cookies', 'cookies', 'Cookie\'lar', { permanent: true })">Cookie'lar</button>
    </div>
    <div class="editor" :class="{ tall: section === 'scripts' }" ref="reqEl" @scroll="tab.scroll.req = ($event.target as HTMLElement).scrollTop">
      <template v-if="section === 'params'">
        <KvTable :rows="d.params" files testid="params-table" @change="onParamsChange" />
        <div v-if="d.pathVars.length" data-testid="path-vars" style="margin-top:12px">
          <b>Path variables</b>
          <table class="kv"><tbody><tr v-for="pv in d.pathVars" :key="pv.key"><td style="width:160px"><code>:{{ pv.key }}</code></td><td><input v-model="pv.value" placeholder="Qiymat" data-testid="path-var-val" @input="touch"></td></tr></tbody></table>
        </div>
      </template>
      <KvTable v-else-if="section === 'headers'" :rows="d.headers" testid="headers-table" @change="touch" />
      <AuthEditor v-else-if="section === 'auth'" :auth="d.auth" allow-inherit :inherit-note="inheritNote" :scope-ref="tab.ref" @change="touch" />
      <ScriptsPanel v-else-if="section === 'scripts'" :scripts="d.scripts" scope="request" :errors="scriptIssues" :goto="tab.state?.scriptGoto" @change="touch" />
      <div v-else-if="section === 'settings'" data-testid="req-settings">
        <p class="muted">Faqat shu so'rov uchun qayta belgilash; "Sukut" — global sozlama (⚙ Sozlamalar).</p>
        <SettingsForm :model="d.settings" :fallback="wsStore.settings" @change="touch" />
      </div>
      <BatchPanel v-else-if="section === 'batch'" :tab="tab" />
      <div v-else data-testid="body-panel">
        <select v-model="d.body.mode" data-testid="body-mode" @change="touch">
          <option value="none">none</option><option value="json">JSON</option><option value="raw">Raw</option><option value="form">x-www-form-urlencoded</option><option value="multipart">form-data</option><option value="binary">binary</option><option value="graphql">GraphQL</option>
        </select>
        <button v-if="d.body.mode === 'json'" data-testid="beautify" style="margin-left:8px" @click="beautify" title="Cmd/Ctrl+B">Beautify</button>
        <input v-if="d.body.mode !== 'none' && d.body.mode !== 'form' && d.body.mode !== 'multipart' && d.body.mode !== 'graphql'" v-model="d.body.contentType" :placeholder="autoCT || 'Content-Type'" style="margin-left:8px;width:220px" data-testid="content-type" @input="touch">
        <span v-if="effectiveCT" class="muted" style="margin-left:8px" data-testid="content-type-auto">Content-Type: {{ effectiveCT }}</span>
        <CodeEditor v-if="d.body.mode === 'json' || d.body.mode === 'raw'" :key="d.body.mode" v-model="d.body.raw" :lang="d.body.mode === 'json' ? 'json' : 'raw'" testid="body-raw" placeholder='{ "key": "{{value}}" }' class="body-editor" @update:model-value="touch" @beautify="beautify" />
        <div v-else-if="d.body.mode === 'binary'" data-testid="binary-panel" style="margin-top:8px">
          <button @click="binInput?.click()">Fayl tanlash…</button><input ref="binInput" type="file" hidden data-testid="binary-file" @change="pickBinary">
          <span v-if="d.body.file.name" data-testid="binary-name"> 📎 {{ d.body.file.name }} <button class="ghost" aria-label="Faylni olib tashlash" data-testid="binary-clear" @click="d.body.file = { path: '', name: '' }; touch()">×</button></span>
          <span v-else class="muted"> Fayl tanlanmagan</span>
        </div>
        <div v-else-if="d.body.mode === 'graphql'" data-testid="graphql-panel" style="margin-top:8px">
          <b>Query</b><CodeEditor v-model="d.body.gql.query" lang="raw" testid="gql-query" placeholder="query { users { id name } }" class="body-editor" style="height:160px" @update:model-value="touch" />
          <b>Variables (JSON)</b><CodeEditor v-model="d.body.gql.variables" lang="json" testid="gql-vars" placeholder='{ "id": 1 }' class="body-editor" style="height:90px" @update:model-value="touch" />
        </div>
        <KvTable v-else-if="d.body.mode === 'form'" :rows="d.body.fields" testid="form-table" @change="touch" />
        <KvTable v-else-if="d.body.mode === 'multipart'" :rows="d.body.fields" files testid="formdata-table" @change="touch" />
      </div>
    </div>
    <div class="v-resizer" data-testid="resp-resizer" role="separator" aria-orientation="horizontal" aria-label="Javob paneli balandligi" tabindex="0" @pointerdown.prevent="startResize" @keydown.up.prevent="nudge(24)" @keydown.down.prevent="nudge(-24)" />
    <section class="resp" ref="respEl" data-testid="response" aria-label="Javob" :style="respH ? { flex: 'none', height: respH + 'px' } : {}" @scroll="tab.scroll.resp = ($event.target as HTMLElement).scrollTop">
      <ResponsePanel :tab="tab" />
    </section>
  </div>
  <div v-if="curlOpen" class="overlay" @click.self="curlOpen = false"><div class="dialog" role="dialog" aria-modal="true" aria-label="Kod namunasi" style="width:640px" data-testid="curl-drawer">
    <div style="display:flex;gap:8px;align-items:center"><b style="flex:1">Kod</b><select v-model="lang" aria-label="Til" data-testid="snippet-lang"><option v-for="l in LANGS" :key="l[0]" :value="l[0]">{{ l[1] }}</option></select><button data-testid="curl-copy" @click="copyCurl">Nusxa</button><button @click="curlOpen = false">×</button></div>
    <pre style="margin-top:10px" data-testid="curl-output" v-html="curlHtml" /></div></div>
</template>