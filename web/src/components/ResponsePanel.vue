<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { downloadBlob, extFor, fetchRawBlob, MAX_STORED } from '../lib/responses'
import type { Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { requestFromDraft } from '../lib/draft'
import { esc, highlightJson } from '../lib/highlight'
import { jsonPath } from '../lib/jsonpath'
import { fmtBytes, fmtMs, showToast } from '../lib/ui'
import Icon from './Icon.vue'
import { sendTab } from '../lib/actions'
import { parseSetCookie } from '../lib/cookies'
import { openScriptAt, type ScriptResult } from '../lib/scripts'

const props = defineProps<{ tab: Tab }>()
const tree = useTree()
const r = computed(() => props.tab.response)
const view = ref<'body' | 'headers' | 'cookies' | 'tests'>('body')
const sc = computed(() => (r.value?.scripts ?? null) as ScriptResult | null)
const tests = computed(() => sc.value?.tests ?? [])
const passed = computed(() => tests.value.filter(t => t.passed && !t.skipped).length)
const failed = computed(() => tests.value.filter(t => !t.passed).length)
const skipped = computed(() => tests.value.filter(t => t.skipped).length)
const scopeLabel = (o: any) => ({ collection: 'Collection', folder: 'Papka', request: "So'rov" } as Record<string, string>)[o?.scope] ?? ''
const kindLabel = (o: any) => (o?.kind === 'prerequest' ? 'Pre-request' : o?.kind === 'test' ? 'Tests' : '')
const setCookies = computed(() => ((r.value?.set_cookies ?? []) as string[]).map(parseSetCookie))
const mode = ref<'pretty' | 'raw' | 'preview'>('pretty')
const search = ref(''), cur = ref(0), jpath = ref('')

const headers = computed<[string, string][]>(() => Object.entries(r.value?.resp_headers ?? {}) as [string, string][])
const ctype = computed(() => (headers.value.find(([k]) => k.toLowerCase() === 'content-type')?.[1] ?? '').toLowerCase())
const isHtml = computed(() => ctype.value.includes('html'))
const parsed = computed(() => (r.value && typeof r.value.response !== 'string' ? r.value.response : undefined))

// JSONPath: faqat JSON javobda; natija massiv sifatida ko'rsatiladi
const jpResult = computed<{ value?: any; error?: string }>(() => {
  const p = jpath.value.trim()
  if (!p || parsed.value === undefined) return {}
  try { return { value: jsonPath(parsed.value, p) } } catch (e: any) { return { error: e.message } }
})
const shown = computed<unknown>(() => (jpResult.value.value !== undefined ? jpResult.value.value : r.value?.response))
const text = computed(() => {
  const v = shown.value
  if (v === undefined || v === null) return v === null ? 'null' : ''
  if (typeof v === 'string') return v
  return mode.value === 'raw' && jpResult.value.value === undefined ? JSON.stringify(v) : JSON.stringify(v, null, 2)
})

const lines = computed(() => text.value.split('\n'))
const LH = 18, VIRTUAL_FROM = 1500
const virtual = computed(() => lines.value.length > VIRTUAL_FROM)

// qidiruv: mos kelishlar ro'yxati (qator, tartib raqami)
const rx = computed(() => (search.value ? new RegExp(search.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi') : null))
const hits = computed(() => {
  const out: number[] = []   // har bir mos kelish uchun qator raqami
  if (!rx.value) return out
  lines.value.forEach((l, i) => { for (const _ of l.matchAll(rx.value!)) out.push(i) })
  return out
})
const firstHit = computed(() => {                 // qator -> shu qatordagi birinchi mos kelishning global tartibi
  const m = new Map<number, number>()
  hits.value.forEach((ln, idx) => { if (!m.has(ln)) m.set(ln, idx) })
  return m
})
function markLine(line: string, ln: number): string {
  if (!rx.value) return esc(line)
  let idx = firstHit.value.get(ln) ?? -1, last = 0, out = ''
  for (const m of line.matchAll(rx.value)) {
    out += esc(line.slice(last, m.index)) + `<mark class="${idx === cur.value ? 'cur' : ''}">${esc(m[0])}</mark>`
    last = m.index! + m[0].length; idx++
  }
  return out + esc(line.slice(last))
}
// har qator alohida `.rl` (CSS counter bilan qator raqami: nusxa olinganda raqamlar kirmaydi)
const prettyHtml = computed(() => {
  const html = search.value ? lines.value.map((l, i) => markLine(l, i)).join('\n') : (mode.value === 'pretty' && typeof shown.value !== 'string' ? highlightJson(text.value) : esc(text.value))
  return html.split('\n').map(l => `<span class="rl">${l}</span>`).join('')
})

function step(d: number) {
  if (!hits.value.length) return
  cur.value = (cur.value + d + hits.value.length) % hits.value.length
  reveal()
}
async function reveal() {
  await nextTick()
  if (virtual.value) { const ln = hits.value[cur.value]; if (box.value) box.value.scrollTop = Math.max(0, ln * LH - 80) }
  else document.querySelector('[data-testid=resp-body] mark.cur')?.scrollIntoView({ block: 'center' })
}
watch([search, text], () => { cur.value = 0; if (search.value) reveal() })

// virtual scroll
const box = ref<HTMLElement>()
const top = ref(0), H = 420
const start = computed(() => Math.max(0, Math.floor(top.value / LH) - 20))
const end = computed(() => Math.min(lines.value.length, Math.ceil((top.value + H) / LH) + 20))
const slice = computed(() => lines.value.slice(start.value, end.value).map((l, i) => ({ n: start.value + i, html: search.value ? markLine(l, start.value + i) : (typeof shown.value !== 'string' && mode.value === 'pretty' ? highlightJson(l) : esc(l)) })))

// Examples
const item = computed<any>(() => { const [c, i] = (props.tab.ref ?? '').split(':'); return c && i ? tree.findItem(c, i) : null })
const examples = computed<any[]>(() => item.value?.response ?? [])
async function saveExample() {
  const [cid, id] = (props.tab.ref ?? '').split(':')
  if (!cid || !id || !item.value) return showToast('Avval so\'rovni saqlang (Namuna so\'rovga bog\'lanadi)', 'warn')
  const resp = r.value, d = props.tab.draft!
  const body = typeof resp.response === 'string' ? resp.response : JSON.stringify(resp.response, null, 2)
  const ex = {
    name: `${resp.status} ${d.method} · ${new Date().toLocaleTimeString()}`, originalRequest: requestFromDraft(d), status: String(resp.status), code: Number(resp.status) || 0,
    header: Object.entries(resp.resp_headers ?? {}).map(([key, value]) => ({ key, value })), body, _postman_previewlanguage: typeof resp.response === 'string' ? 'text' : 'json',
  }
  await tree.updateItem(cid, id, { response: [...examples.value, ex] })
  showToast('Namuna saqlandi', 'success')
}
function loadExample(e: Event) {
  const i = Number((e.target as HTMLSelectElement).value)
  ;(e.target as HTMLSelectElement).value = ''
  const ex = examples.value[i]
  if (!ex) return
  let body: any = ex.body
  try { body = JSON.parse(ex.body) } catch { /* matn */ }
  props.tab.response = { status: ex.code || ex.status, response: body, time: 0, size: (ex.body ?? '').length, url: '', resp_headers: Object.fromEntries((ex.header ?? []).map((h: any) => [h.key, h.value])), example: ex.name }
}
const STATUS: Record<number, string> = { 200: 'OK', 201: 'Created', 202: 'Accepted', 204: 'No Content', 301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 405: 'Method Not Allowed', 409: 'Conflict', 422: 'Unprocessable Entity', 429: 'Too Many Requests', 500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable', 504: 'Gateway Timeout' }
const statusText = computed(() => (typeof r.value?.status === 'number' ? STATUS[r.value.status] ?? '' : ''))
const pillClass = computed(() => (typeof r.value?.status === 'number' && r.value.status < 400 ? 'ok' : 'err'))
const timing = computed(() => { const t = r.value?.timing; return `DNS — · Ulanish (connect) ${fmtMs(t?.connect)} · TLS ${fmtMs(t?.tls)} · TTFB ${fmtMs(t?.ttfb)}` })
// Binary javob (rasm, PDF…): serverdagi nusxadan blob sifatida olinadi va Preview'da ko'rsatiladi
const blobUrl = ref(''), blobType = ref('')
async function loadBlob() {
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
  blobUrl.value = ''
  const id = r.value?.response_id
  if (!id || !r.value?.binary) return
  const b = await fetchRawBlob(id)
  if (b) { blobType.value = b.type; blobUrl.value = URL.createObjectURL(b) }
}
watch(() => [r.value?.response_id, r.value?.binary], loadBlob, { immediate: true })
onBeforeUnmount(() => { if (blobUrl.value) URL.revokeObjectURL(blobUrl.value) })
const isImage = computed(() => blobType.value.startsWith('image/')), isPdf = computed(() => blobType.value === 'application/pdf')
async function saveFile() {
  if (r.value?.binary && r.value.response_id) { const b = await fetchRawBlob(r.value.response_id); if (b) downloadBlob(b, 'javob.' + extFor(ctype.value)) }
  else downloadBlob(new Blob([text.value]), 'javob.' + (typeof r.value?.response === 'string' ? 'txt' : 'json'))
}
const hq = ref('')
const shownHeaders = computed(() => { const q = hq.value.trim().toLowerCase(); return q ? headers.value.filter(([k, v]) => (k + ' ' + v).toLowerCase().includes(q)) : headers.value })
function copyHeaders(rows: [string, string][]) { navigator.clipboard?.writeText(rows.map(([k, v]) => `${k}: ${v}`).join('\n')); showToast(rows.length === 1 ? 'Header nusxalandi' : `${rows.length} ta header nusxalandi`, 'success') }
const copy = () => { navigator.clipboard?.writeText(text.value); showToast('Nusxalandi', 'success') }
</script>

<template>
  <div v-if="!r" class="empty-state" data-testid="resp-empty">
    <Icon name="inbox" :size="34" />
    <strong>Javob shu yerda chiqadi</strong>
    <span style="font-size:var(--fs-md)">«Yuborish» tugmasini yoki <span class="kbd">⌘</span> + <span class="kbd">↵</span> ni bosing</span>
  </div>
  <div v-else-if="r.loading" class="empty-state state-loading" role="status" data-testid="resp-loading"><span class="spinner" aria-hidden="true" /><strong>Yuborilmoqda…</strong></div>
  <div v-else data-testid="resp-panel" style="display:flex;flex-direction:column">
    <div class="rp-bar" data-testid="resp-bar">
      <button :class="{ on: view === 'body' }" data-testid="rp-body-tab" @click="view = 'body'">Body</button>
      <button :class="{ on: view === 'headers' }" data-testid="rp-headers-tab" @click="view = 'headers'">Headers ({{ headers.length }})</button>
      <button :class="{ on: view === 'cookies' }" data-testid="rp-cookies-tab" @click="view = 'cookies'">Cookies ({{ setCookies.length }})</button>
      <button :class="{ on: view === 'tests' }" data-testid="rp-tests-tab" @click="view = 'tests'">Testlar<span class="badge" :class="{ 'badge-err': failed || sc?.errors?.length }" data-testid="rp-tests-badge">{{ tests.length ? `${passed}/${tests.length - skipped}` : (sc?.errors?.length ? '!' : '0') }}</span></button>
      <template v-if="view === 'body'">
        <span class="rp-sep" />
        <div class="seg-group" role="group" aria-label="Ko'rinish">
          <button v-for="m in (['pretty', 'raw', 'preview'] as const)" :key="m" class="seg" :class="{ on: mode === m }" :aria-pressed="mode === m" :data-mode="m" :disabled="m === 'preview' && !isHtml" @click="mode = m">{{ { pretty: 'Pretty', raw: 'Raw', preview: 'Preview' }[m] }}</button>
        </div>
      </template>
      <span style="flex:1" />
      <div class="resp-meta">
        <span class="status-pill" :class="pillClass"><span data-testid="resp-status">{{ r.status }}</span><span v-if="statusText">{{ statusText }}</span></span>
        <span class="tipwrap muted" tabindex="0" data-testid="resp-timing" :aria-label="timing"><b data-testid="resp-time">{{ fmtMs(r.time) }}</b><span class="tip" role="tooltip">{{ timing }}</span></span>
        <span class="muted"><b data-testid="resp-size">{{ fmtBytes(r.size ?? 0) }}</b></span>
      </div>
      <span v-if="r?.example" class="muted" data-testid="rp-example-label">Namuna: {{ r.example }}</span>
      <select v-if="examples.length" class="sm" aria-label="Namunalar" data-testid="examples-select" @change="loadExample"><option value="">Namunalar ({{ examples.length }})</option><option v-for="(e, i) in examples" :key="i" :value="i">{{ e.name }}</option></select>
      <button class="sm" data-testid="save-example" title="Javobni so'rovga namuna sifatida saqlash" @click="saveExample">Save as Example</button>
      <button class="ib" data-testid="rp-copy" aria-label="Javobni nusxalash" title="Nusxa" @click="copy"><Icon name="copy" :size="16" /></button>
    </div>

    <div v-if="view === 'body' && r.binary" class="resp-binary" data-testid="resp-binary">
      <img v-if="isImage && blobUrl" :src="blobUrl" alt="Javob rasmi" class="resp-img" data-testid="resp-image">
      <iframe v-else-if="isPdf && blobUrl" :src="blobUrl" title="PDF javob" class="resp-pdf" data-testid="resp-pdf" />
      <div v-else class="resp-bin-card"><Icon name="file" :size="28" /><b>{{ ctype || 'binary' }}</b><span class="muted">{{ fmtBytes(r.size ?? 0) }} — ko'rsatib bo'lmaydigan tur</span></div>
      <div class="resp-bin-bar"><span class="muted" data-testid="resp-bin-info">{{ ctype }} · {{ fmtBytes(r.size ?? 0) }}</span><button class="sm" data-testid="rp-save-file" @click="saveFile">Faylga saqlash</button></div>
    </div>
    <template v-else-if="view === 'body'">
      <div v-if="r.restored && r.stored_truncated" class="resp-trunc" role="status" data-testid="resp-trunc-banner">
        <b>To'liq javob saqlanmagan ({{ fmtBytes(r.size ?? 0) }})</b><span>— birinchi {{ fmtBytes(MAX_STORED) }} ko'rsatilmoqda.</span>
        <button class="sm" data-testid="rp-save-file" @click="saveFile">Faylga saqlash</button><button class="sm primary" data-testid="resp-resend" @click="sendTab(tab)">Qayta yuborish</button>
      </div>
      <div v-if="mode !== 'preview'" class="rp-tools">
        <input v-model="search" placeholder="Qidirish…" data-testid="rp-search" style="width:170px" @keydown.enter.exact.prevent="step(1)" @keydown.shift.enter.prevent="step(-1)">
        <template v-if="search"><span class="muted" data-testid="rp-count" aria-live="polite">{{ hits.length ? cur + 1 : 0 }} / {{ hits.length }}</span>
          <button class="ib" data-testid="rp-prev" aria-label="Oldingi moslik" @click="step(-1)"><Icon name="chevron-up" :size="15" /></button><button class="ib" data-testid="rp-next" aria-label="Keyingi moslik" @click="step(1)"><Icon name="chevron-down" :size="15" /></button></template>
        <input v-model="jpath" :disabled="parsed === undefined" :placeholder="parsed === undefined ? 'JSONPath (faqat JSON javobda)' : 'JSONPath: $.items[?(@.price<10)].name'" data-testid="rp-jsonpath" style="flex:1;min-width:200px;font-family:ui-monospace,monospace">
        <span v-if="jpResult.error" class="err" data-testid="rp-jp-error">{{ jpResult.error }}</span>
        <span v-else-if="jpResult.value" class="muted" data-testid="rp-jp-count">{{ jpResult.value.length }} natija</span>
      </div>
      <div v-if="r?.truncated && r.response === undefined" class="resp-missing state-empty" data-testid="resp-not-saved" role="status">
        <b>Javob saqlanmagan</b><span>Sahifa yangilangach javob matni xotirada qolmaydi (holat, o'lcham va sarlavhalar saqlanadi).</span>
        <button class="sm primary" data-testid="resp-resend" @click="sendTab(tab)">Qayta yuborish</button>
      </div>
      <div v-else-if="text === '' && (r.size ?? 0) === 0" class="resp-empty-body" data-testid="resp-empty-body">Javob tanasi bo'sh <span class="muted">({{ r.status }}, 0 bayt)</span></div>
      <iframe v-else-if="mode === 'preview'" sandbox="" :srcdoc="String(r?.response ?? '')" data-testid="rp-preview" class="rp-frame" />
      <div v-else-if="virtual" ref="box" class="vlist" data-testid="resp-body" tabindex="0" role="region" aria-label="Javob matni" :data-virtual="true" :style="{ height: H + 'px' }" @scroll="top = ($event.target as HTMLElement).scrollTop">
        <div :style="{ height: lines.length * LH + 'px', position: 'relative' }"><div :style="{ transform: `translateY(${start * LH}px)` }">
          <div v-for="l in slice" :key="l.n" class="vline" :style="{ height: LH + 'px', lineHeight: LH + 'px' }" v-html="l.html" /></div></div>
      </div>
      <pre v-else data-testid="resp-body" v-html="prettyHtml" />
      <div v-if="virtual" class="muted" data-testid="rp-virtual-note">{{ lines.length }} qator (virtual scroll)</div>
    </template>

    <div v-else-if="view === 'tests'" data-testid="rp-tests" style="display:flex;flex-direction:column;gap:6px">
      <div class="rp-tools" data-testid="rp-tests-tools"><span class="muted" style="font-size:var(--fs-sm)">{{ tests.length ? `${passed} o'tdi · ${failed} yiqildi${skipped ? ' · ' + skipped + ' o\'tkazildi' : ''}` : 'Testlar yo\'q' }}</span></div>
      <div v-if="sc && sc.available === false" class="script-off" role="alert" data-testid="rp-scripts-off"><b>Skriptlar o'chiq.</b> {{ sc.message }} — <code>{{ sc.install }}</code></div>
      <div v-else-if="!sc" class="muted" data-testid="rp-tests-none">Bu so'rovda (yoki ota papka/collection'da) skript yo'q. <b>Scripts</b> bo'limida <i>Tests</i> skripti yozing.</div>
      <template v-else>
        <div class="muted" data-testid="tests-summary" style="font-size:var(--fs-md)"><b class="ok">{{ passed }} o'tdi</b> · <b :class="failed ? 'err' : 'muted'">{{ failed }} muvaffaqiyatsiz</b><template v-if="skipped"> · {{ skipped }} o'tkazildi</template> · {{ tests.length }} ta test</div>
        <div v-for="(t, i) in tests" :key="i" class="test-row" :data-status="t.skipped ? 'skip' : t.passed ? 'pass' : 'fail'" data-testid="test-row">
          <span class="status-pill" :class="t.skipped ? '' : t.passed ? 'ok' : 'err'" style="font-size:var(--fs-xs);padding:2px 8px">{{ t.skipped ? 'SKIP' : t.passed ? 'PASS' : 'FAIL' }}</span>
          <span style="flex:1;min-width:0"><span data-testid="test-name">{{ t.name }}</span>
            <span v-if="t.error" class="err" style="display:block;font:var(--fs-sm) var(--font-mono)" data-testid="test-error">{{ t.error.name }}: {{ t.error.message }}<button v-if="t.error.line" class="ghost sm" style="height:20px" data-testid="test-error-link" @click="openScriptAt(tab, t.error)">qator {{ t.error.line }}</button></span></span>
          <span class="muted origin" data-testid="test-origin">{{ scopeLabel(t.origin) }}</span>
        </div>
        <div v-if="sc.errors.length" class="h-label" style="margin-top:10px">Skript xatolari</div>
        <div v-for="(e, i) in sc.errors" :key="'e' + i" class="script-error" data-testid="script-error">
          <div><span class="status-pill err" style="font-size:var(--fs-xs);padding:2px 8px">{{ e.name }}</span> <span data-testid="script-error-msg">{{ e.message }}</span></div>
          <div class="muted" style="font-size:var(--fs-sm);margin-top:2px"><span data-testid="script-error-origin">{{ scopeLabel(e.origin) }}{{ e.origin.name ? ' «' + e.origin.name + '»' : '' }} · {{ kindLabel(e.origin) }}</span>
            <button v-if="e.line" class="ghost sm" style="height:20px" data-testid="script-error-link" @click="openScriptAt(tab, e)">qator {{ e.line }} ↗</button></div>
          <details v-if="e.stack"><summary class="muted" style="cursor:pointer;font-size:var(--fs-sm)">stack trace</summary><pre data-testid="script-error-stack" style="margin-top:4px">{{ e.stack }}</pre></details>
        </div>
        <div v-if="sc.skipped" class="muted" data-testid="rp-skipped">So'rov <code>pm.execution.skipRequest()</code> bilan o'tkazib yuborildi.</div>
        <div v-if="sc.next_set" class="muted" data-testid="rp-next">Keyingi so'rov: <code>{{ sc.next_request === null ? 'null (run to\'xtaydi)' : sc.next_request }}</code></div>
      </template>
    </div>
    <template v-else-if="view === 'cookies'">
      <div class="rp-tools" data-testid="rp-cookies-tools"><span class="muted" style="font-size:var(--fs-sm)">{{ setCookies.length }} ta cookie o'rnatildi</span></div>
          <table class="kv" data-testid="rp-cookies"><thead><tr><th style="text-align:left">Nom</th><th style="text-align:left">Qiymat</th><th style="text-align:left">Domen</th><th style="text-align:left">Yo'l</th><th style="text-align:left">Muddat</th><th style="text-align:left">Bayroqlar</th></tr></thead><tbody>
      <tr v-for="c in setCookies" :key="c.name" data-testid="rp-cookie-row"><td><b>{{ c.name }}</b></td><td style="word-break:break-all">{{ c.value }}</td><td>{{ c.domain }}</td><td>{{ c.path }}</td><td>{{ c.expires || (c.maxAge ? c.maxAge + ' s' : 'sessiya') }}</td><td>{{ [c.httpOnly && 'HttpOnly', c.secure && 'Secure', c.sameSite && 'SameSite=' + c.sameSite].filter(Boolean).join(' · ') }}</td></tr>
      <tr v-if="!setCookies.length"><td colspan="6" class="muted">Bu javob cookie o'rnatmadi</td></tr>
    </tbody></table>
    </template>
    <template v-else>
      <div class="rp-tools" data-testid="rp-headers-tools">
        <input v-model="hq" placeholder="Header qidirish…" aria-label="Header qidirish" data-testid="rp-headers-search" style="width:220px">
        <span class="muted" style="font-size:var(--fs-sm)">{{ shownHeaders.length }} / {{ headers.length }}</span>
        <span style="flex:1" />
        <button class="sm" data-testid="rp-headers-copy-all" @click="copyHeaders(shownHeaders)">Hammasini nusxalash</button>
      </div>
      <table class="kv rp-headers" data-testid="rp-headers"><colgroup><col style="width:240px"><col><col style="width:36px"></colgroup><tbody>
        <tr v-for="[k, v] in shownHeaders" :key="k" data-testid="rp-header-row"><td class="hk"><b>{{ k }}</b></td><td class="hv">{{ v }}</td>
          <td><button class="ib" :aria-label="`${k} nusxalash`" title="Nusxa" data-testid="rp-header-copy" @click="copyHeaders([[k, v]])"><Icon name="copy" :size="14" /></button></td></tr>
        <tr v-if="!headers.length"><td colspan="3" class="muted">Header yo'q</td></tr>
        <tr v-else-if="!shownHeaders.length"><td colspan="3" class="muted">Filtr bo'yicha header yo'q</td></tr>
      </tbody></table>
    </template>
  </div>
</template>
