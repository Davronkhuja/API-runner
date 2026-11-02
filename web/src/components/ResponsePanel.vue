<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { requestFromDraft } from '../lib/draft'
import { esc, highlightJson } from '../lib/highlight'
import { jsonPath } from '../lib/jsonpath'
import { showToast } from '../lib/ui'
import { parseSetCookie } from '../lib/cookies'

const props = defineProps<{ tab: Tab }>()
const tree = useTree()
const r = computed(() => props.tab.response)
const view = ref<'body' | 'headers' | 'cookies'>('body')
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
const prettyHtml = computed(() => (search.value ? lines.value.map((l, i) => markLine(l, i)).join('\n') : (mode.value === 'pretty' && typeof shown.value !== 'string' ? highlightJson(text.value) : esc(text.value))))

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
const copy = () => { navigator.clipboard?.writeText(text.value); showToast('Nusxalandi', 'success') }
</script>

<template>
  <div data-testid="resp-panel">
    <div class="rp-bar" data-testid="resp-bar">
      <button :class="{ on: view === 'body' }" data-testid="rp-body-tab" @click="view = 'body'">Body</button>
      <button :class="{ on: view === 'headers' }" data-testid="rp-headers-tab" @click="view = 'headers'">Headers ({{ headers.length }})</button>
      <button :class="{ on: view === 'cookies' }" data-testid="rp-cookies-tab" @click="view = 'cookies'">Cookies ({{ setCookies.length }})</button>
      <template v-if="view === 'body'">
        <span class="rp-sep" />
        <button v-for="m in (['pretty', 'raw', 'preview'] as const)" :key="m" :class="{ on: mode === m }" :data-mode="m" :disabled="m === 'preview' && !isHtml" @click="mode = m">{{ { pretty: 'Pretty', raw: 'Raw', preview: 'Preview' }[m] }}</button>
      </template>
      <span style="flex:1" />
      <span v-if="r?.example" class="muted" data-testid="rp-example-label">Namuna: {{ r.example }}</span>
      <select v-if="examples.length" data-testid="examples-select" @change="loadExample"><option value="">Namunalar ({{ examples.length }})</option><option v-for="(e, i) in examples" :key="i" :value="i">{{ e.name }}</option></select>
      <button data-testid="save-example" title="Javobni so'rovga namuna sifatida saqlash" @click="saveExample">Save as Example</button>
      <button class="ghost" data-testid="rp-copy" @click="copy">Nusxa</button>
    </div>

    <template v-if="view === 'body'">
      <div v-if="mode !== 'preview'" class="rp-tools">
        <input v-model="search" placeholder="Qidirish…" data-testid="rp-search" style="width:170px" @keydown.enter.exact.prevent="step(1)" @keydown.shift.enter.prevent="step(-1)">
        <template v-if="search"><span class="muted" data-testid="rp-count">{{ hits.length ? cur + 1 : 0 }} / {{ hits.length }}</span>
          <button class="ghost" data-testid="rp-prev" @click="step(-1)">↑</button><button class="ghost" data-testid="rp-next" @click="step(1)">↓</button></template>
        <input v-model="jpath" :disabled="parsed === undefined" :placeholder="parsed === undefined ? 'JSONPath (faqat JSON javobda)' : 'JSONPath: $.items[?(@.price<10)].name'" data-testid="rp-jsonpath" style="flex:1;min-width:200px;font-family:ui-monospace,monospace">
        <span v-if="jpResult.error" class="err" data-testid="rp-jp-error">{{ jpResult.error }}</span>
        <span v-else-if="jpResult.value" class="muted" data-testid="rp-jp-count">{{ jpResult.value.length }} natija</span>
      </div>
      <iframe v-if="mode === 'preview'" sandbox="" :srcdoc="String(r?.response ?? '')" data-testid="rp-preview" class="rp-frame" />
      <div v-else-if="virtual" ref="box" class="vlist" data-testid="resp-body" :data-virtual="true" :style="{ height: H + 'px' }" @scroll="top = ($event.target as HTMLElement).scrollTop">
        <div :style="{ height: lines.length * LH + 'px', position: 'relative' }"><div :style="{ transform: `translateY(${start * LH}px)` }">
          <div v-for="l in slice" :key="l.n" class="vline" :style="{ height: LH + 'px', lineHeight: LH + 'px' }" v-html="l.html" /></div></div>
      </div>
      <pre v-else data-testid="resp-body" v-html="prettyHtml" />
      <div v-if="virtual" class="muted" data-testid="rp-virtual-note">{{ lines.length }} qator (virtual scroll)</div>
    </template>

    <table v-else-if="view === 'cookies'" class="kv" data-testid="rp-cookies"><thead><tr><th style="text-align:left">Nom</th><th style="text-align:left">Qiymat</th><th style="text-align:left">Domen</th><th style="text-align:left">Yo'l</th><th style="text-align:left">Muddat</th><th style="text-align:left">Bayroqlar</th></tr></thead><tbody>
      <tr v-for="c in setCookies" :key="c.name" data-testid="rp-cookie-row"><td><b>{{ c.name }}</b></td><td style="word-break:break-all">{{ c.value }}</td><td>{{ c.domain }}</td><td>{{ c.path }}</td><td>{{ c.expires || (c.maxAge ? c.maxAge + ' s' : 'sessiya') }}</td><td>{{ [c.httpOnly && 'HttpOnly', c.secure && 'Secure', c.sameSite && 'SameSite=' + c.sameSite].filter(Boolean).join(' · ') }}</td></tr>
      <tr v-if="!setCookies.length"><td colspan="6" class="muted">Bu javob cookie o'rnatmadi</td></tr>
    </tbody></table>
    <table v-else class="kv" data-testid="rp-headers"><tbody>
      <tr v-for="[k, v] in headers" :key="k"><td style="width:240px"><b>{{ k }}</b></td><td style="word-break:break-all">{{ v }}</td></tr>
      <tr v-if="!headers.length"><td class="muted">Header yo'q</td></tr>
    </tbody></table>
  </div>
</template>
