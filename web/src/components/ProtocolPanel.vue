<script setup lang="ts">
/** WebSocket / SSE tabi tanasi: sozlamalar (Headers, Auth, Body, Sozlamalar, Skriptlar) + xabarlar oqimi (filtr, qidiruv, kengaytirish) + yuboruvchi va shablonlar (WS). */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AuthEditor from './AuthEditor.vue'
import CodeEditor from './CodeEditor.vue'
import Icon from './Icon.vue'
import KvTable from './KvTable.vue'
import ScriptsPanel from './ScriptsPanel.vue'
import { useProtocols, type ProtoEvent } from '../stores/protocols'
import { useTabs, type Tab } from '../stores/tabs'
import { authSource } from '../lib/scope'
import { b64bytes, bytesToText, filterEvents, fmtSize, fmtTime, hexdump, isSystem, newTemplateId, oneLine, systemText, tryJson, type LogFilter } from '../lib/protocols'
import { downloadFrom } from '../lib/exporter'
import { askConfirm, showToast } from '../lib/ui'
import type { WsTemplate } from '../lib/draft'

const props = defineProps<{ tab: Tab }>()
const tabs = useTabs(), store = useProtocols()
const d = computed(() => props.tab.draft!)
const isWs = computed(() => d.value.protocol === 'ws')
const conn = computed(() => store.get(props.tab.id))
const touch = () => tabs.touch(props.tab.id)

// ── sozlamalar bo'limlari ──
const SECTIONS = computed(() => (isWs.value ? ['headers', 'auth', 'settings', 'scripts'] : ['headers', 'auth', 'body', 'settings', 'scripts']) as string[])
const LABEL: Record<string, string> = { headers: 'Headers', auth: 'Auth', body: 'Body', settings: 'Sozlamalar', scripts: 'Pre-request' }
props.tab.state ??= {}
const section = ref<string>((props.tab.state.protoSection as string) ?? 'headers')
const cfgOpen = ref(props.tab.state.protoCfgOpen !== false)
watch(section, v => { props.tab.state!.protoSection = v })
watch(cfgOpen, v => { props.tab.state!.protoCfgOpen = v })
if (!SECTIONS.value.includes(section.value)) section.value = 'headers'
const authSrc = computed(() => authSource(props.tab.ref))
const counts = computed(() => ({ headers: d.value.headers.filter(h => h.enabled && h.key.trim()).length }) as Record<string, number>)

// ── ulanish holati ──
const live = computed(() => ['connecting', 'open', 'reconnecting'].includes(conn.value.status))
const statusText = computed(() => ({ idle: 'Ulanmagan', connecting: 'Ulanilmoqda…', open: 'Ulangan', reconnecting: 'Qayta ulanilmoqda…', closed: 'Uzildi' } as const)[conn.value.status])
const statusClass = computed(() => (conn.value.status === 'open' ? 'ok' : conn.value.status === 'idle' || conn.value.status === 'closed' ? '' : 'warn'))
onMounted(() => { store.restore(props.tab) })

// ── jurnal: filtr/qidiruv ──
const saved = (props.tab.state.protoFilter ?? {}) as Partial<LogFilter> & { auto?: boolean }
const ui = ref({ dir: (saved.dir ?? 'all') as LogFilter['dir'], system: saved.system ?? true, q: saved.q ?? '', regex: !!saved.regex, auto: saved.auto ?? true, types: (saved.types ?? null) as string[] | null })
watch(ui, v => { props.tab.state!.protoFilter = { ...v } }, { deep: true })
const sseTypes = computed(() => [...new Set(conn.value.events.filter(e => e.type === 'event').map(e => e.event ?? 'message'))])
function toggleType(t: string) {
  const all = sseTypes.value
  const cur = ui.value.types ?? all
  const next = cur.includes(t) ? cur.filter(x => x !== t) : [...cur, t]
  ui.value.types = next.length === all.length ? null : next
}
const typeOn = (t: string) => ui.value.types === null || ui.value.types.includes(t)
const filtered = computed(() => filterEvents(conn.value.events, { dir: ui.value.dir, system: ui.value.system, types: ui.value.types, q: ui.value.q, regex: ui.value.regex }))
const RENDER_MAX = 1000
const shown = computed(() => filtered.value.slice(-RENDER_MAX))
const open = ref<Set<number>>(new Set())
const toggleRow = (e: ProtoEvent) => { const s = new Set(open.value); if (s.has(e.seq)) s.delete(e.seq); else s.add(e.seq); open.value = s }
const listEl = ref<HTMLElement>()
watch(() => conn.value.events.length, async () => { if (ui.value.auto) { await nextTick(); if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight } })

function detail(e: ProtoEvent): { text: string; kind: 'json' | 'text' | 'hex' } {
  if (e.kind === 'binary') { const u = b64bytes(e.data ?? ''); return { text: hexdump(u), kind: 'hex' } }
  const j = tryJson(e.data ?? '')
  return j !== undefined ? { text: JSON.stringify(j, null, 2), kind: 'json' } : { text: e.data ?? '', kind: 'text' }
}
const preview = (e: ProtoEvent) => (e.kind === 'binary' ? `⟨binary ${fmtSize(e.size ?? 0)}⟩ ${oneLine(bytesToText(b64bytes(e.data ?? '')).replace(/[^\x20-\x7e]/g, '·'), 120)}` : oneLine(e.data ?? ''))
function copy(e: ProtoEvent) { navigator.clipboard?.writeText(e.kind === 'binary' ? bytesToText(b64bytes(e.data ?? '')) : (e.data ?? '')); showToast('Nusxalandi', 'success') }
async function clearLog() { if (conn.value.events.length > 50 && !(await askConfirm(`${conn.value.events.length} ta yozuv tozalansinmi?`, 'Tozalash'))) return; store.clear(props.tab.id); open.value = new Set() }
const exportLog = (fmt: 'json' | 'txt') => conn.value.sessionId ? downloadFrom(`/api/protocols/${conn.value.sessionId}/export?format=${fmt}`) : showToast('Eksport uchun ulanish kerak', 'warn')

// ── yuboruvchi (WS) ──
const kind = ref<'text' | 'json' | 'binary'>((props.tab.state.protoKind as 'text' | 'json' | 'binary') ?? 'text')
const enc = ref<'base64' | 'hex'>('hex')
const msg = ref<string>((props.tab.state.protoMsg as string) ?? '')
watch([kind, msg], () => { props.tab.state!.protoKind = kind.value; props.tab.state!.protoMsg = msg.value })
const sendErr = ref('')
const jsonOk = computed(() => kind.value !== 'json' || !msg.value.trim() || /\{\{/.test(msg.value) || tryJson(msg.value) !== undefined || msg.value.trim() === 'null')
async function send() {
  sendErr.value = ''
  if (conn.value.status !== 'open') { sendErr.value = 'Ulanish ochiq emas'; return }
  if (!jsonOk.value) { sendErr.value = 'JSON noto\'g\'ri'; return }
  try { await store.send(props.tab, { kind: kind.value, data: msg.value, encoding: kind.value === 'binary' ? enc.value : undefined }) } catch (e: any) { sendErr.value = e.message }
}
function onComposeKey(e: KeyboardEvent) { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); send() } }

// ── saqlangan xabar shablonlari ──
const activeTpl = ref<string | null>(null)
const tplName = ref('')
const templates = computed(() => d.value.proto.messages)
function loadTpl(t: WsTemplate) { kind.value = t.kind; msg.value = t.data; enc.value = t.encoding; activeTpl.value = t.id; tplName.value = t.name }
function saveTpl() {
  const name = tplName.value.trim() || `Xabar ${templates.value.length + 1}`
  const cur = templates.value.find(t => t.id === activeTpl.value)
  if (cur && cur.name === name) Object.assign(cur, { kind: kind.value, data: msg.value, encoding: enc.value })                 // yangilash
  else { const t = { id: newTemplateId(), name, kind: kind.value, data: msg.value, encoding: enc.value }; templates.value.push(t); activeTpl.value = t.id }
  touch(); showToast('Shablon saqlandi — so\'rovni Saqlash orqali collection\'ga yozing', 'success')
}
function delTpl(t: WsTemplate) { d.value.proto.messages = templates.value.filter(x => x.id !== t.id); if (activeTpl.value === t.id) { activeTpl.value = null; tplName.value = '' } touch() }

// ── Body (SSE POST) ──
const bodyOn = computed(() => d.value.proto.sseMethod !== 'GET')
function setBody(v: string) { d.value.body.mode = 'raw'; d.value.body.raw = v; touch() }
</script>

<template>
  <div class="proto" :data-testid="'proto-' + d.protocol">
    <section class="proto-cfg" :class="{ collapsed: !cfgOpen }">
      <div class="sec-tabs" role="tablist" aria-label="Ulanish sozlamalari">
        <button v-for="s in SECTIONS" :key="s" role="tab" :aria-selected="section === s && cfgOpen" :class="{ on: section === s && cfgOpen }" :data-psection="s" @click="section = s; cfgOpen = true">{{ LABEL[s] }}<span v-if="counts[s]" class="badge">{{ counts[s] }}</span></button>
        <span style="flex:1" />
        <button class="ghost" :aria-expanded="cfgOpen" data-testid="proto-cfg-toggle" @click="cfgOpen = !cfgOpen"><Icon :name="cfgOpen ? 'chevron-up' : 'chevron-down'" :size="14" />{{ cfgOpen ? "Yig'ish" : 'Sozlamalar' }}</button>
      </div>
      <div v-show="cfgOpen" class="proto-cfg-body scroll">
        <KvTable v-if="section === 'headers'" :rows="d.headers" testid="proto-headers" @change="touch" />
        <AuthEditor v-else-if="section === 'auth'" :auth="d.auth" allow-inherit :scope-ref="tab.ref" :source="authSrc" @change="touch" />
        <div v-else-if="section === 'body'" class="proto-body">
          <p class="muted" style="margin:0 0 8px">SSE sukut bo'yicha GET; ayrim API'lar (masalan LLM oqimlari) POST/PUT bilan tana qabul qiladi. Metodni «Sozlamalar» da tanlang.</p>
          <p v-if="!bodyOn" class="muted" data-testid="proto-body-off">Metod GET — tana yuborilmaydi.</p>
          <CodeEditor v-else :model-value="d.body.raw" lang="json" testid="proto-body" label="SSE so'rov tanasi" placeholder='{ "stream": true }' @update:model-value="setBody" />
        </div>
        <div v-else-if="section === 'settings'" class="proto-settings" data-testid="proto-settings">
          <template v-if="isWs">
            <label class="bf"><span class="bl">Subprotokollar (vergul bilan)</span><input v-model="d.proto.subprotocols" placeholder="chat, json.v1" data-testid="proto-subprotocols" aria-label="Subprotokollar" @input="touch"></label>
            <label class="bf"><span class="bl">Ping oralig'i, s (0 — sukut)</span><input type="number" min="0" v-model.number="d.proto.pingInterval" data-testid="proto-ping" aria-label="Ping oralig'i" @input="touch"></label>
          </template>
          <template v-else>
            <label class="bf"><span class="bl">Metod</span><select v-model="d.proto.sseMethod" data-testid="proto-sse-method" aria-label="SSE metodi" @change="touch"><option>GET</option><option>POST</option><option>PUT</option></select></label>
            <label class="bf"><span class="bl">Last-Event-ID (boshlang'ich)</span><input v-model="d.proto.lastEventId" placeholder="42" data-testid="proto-last-id" aria-label="Last-Event-ID" @input="touch"></label>
          </template>
          <fieldset class="proto-rc"><legend>Avtomatik qayta ulanish</legend>
            <label class="chk"><input type="checkbox" v-model="d.proto.reconnect.enabled" data-testid="proto-rc-enabled" @change="touch">Uzilganda qayta ulanish</label>
            <template v-if="d.proto.reconnect.enabled">
              <label class="bf"><span class="bl">Boshlang'ich kechikish, ms</span><input type="number" min="50" step="100" v-model.number="d.proto.reconnect.delay_ms" data-testid="proto-rc-delay" aria-label="Kechikish" @input="touch"></label>
              <label class="bf"><span class="bl">Maks. urinishlar (0 — cheksiz)</span><input type="number" min="0" max="100" v-model.number="d.proto.reconnect.max_attempts" data-testid="proto-rc-max" aria-label="Maksimal urinishlar" @input="touch"></label>
              <label v-if="isWs" class="chk"><input type="checkbox" v-model="d.proto.reconnect.always" data-testid="proto-rc-always" @change="touch">Server toza yopganda ham</label>
              <p class="muted" style="margin:0;font-size:var(--fs-sm)">Kechikish har urinishda ikki baravar oshadi (30 s gacha){{ isWs ? '' : "; server `retry:` yuborsa — shu qiymat" }}. 2 s dan uzoq turgan ulanishdan keyin hisob yangilanadi.</p>
            </template>
          </fieldset>
        </div>
        <ScriptsPanel v-else :scripts="d.scripts" scope="request" @change="touch" />
      </div>
    </section>

    <section class="proto-log" aria-label="Xabarlar oqimi">
      <div class="proto-bar" role="toolbar" aria-label="Oqim boshqaruvi">
        <span class="status-pill" :class="statusClass" data-testid="proto-status" role="status">{{ statusText }}</span>
        <span class="muted proto-counts" data-testid="proto-counts"><Icon name="chevron-down" :size="12" /> {{ conn.counts.in }} · {{ fmtSize(conn.counts.bytes_in) }}<template v-if="isWs"> &nbsp; <Icon name="chevron-up" :size="12" /> {{ conn.counts.out }} · {{ fmtSize(conn.counts.bytes_out) }}</template><template v-if="conn.counts.errors"> &nbsp;<span class="err">⚠ {{ conn.counts.errors }}</span></template></span>
        <span style="flex:1" />
        <div v-if="isWs" class="seg-group" role="group" aria-label="Yo'nalish filtri">
          <button v-for="f in ([['all', 'Hammasi'], ['in', 'Kiruvchi'], ['out', 'Chiquvchi']] as const)" :key="f[0]" class="seg" :class="{ on: ui.dir === f[0] }" :aria-pressed="ui.dir === f[0]" :data-dir="f[0]" @click="ui.dir = f[0]">{{ f[1] }}</button>
        </div>
        <label class="chk sm"><input type="checkbox" v-model="ui.system" data-testid="proto-system">Tizim</label>
        <input v-model="ui.q" class="proto-search" type="search" placeholder="Qidirish…" aria-label="Xabarlarda qidirish" data-testid="proto-search">
        <button class="sm" :class="{ on: ui.regex }" :aria-pressed="ui.regex" title="Regex" data-testid="proto-regex" @click="ui.regex = !ui.regex">.*</button>
        <button class="sm" :aria-pressed="ui.auto" title="Oxirgisiga avtomatik o'tish" data-testid="proto-auto" :class="{ on: ui.auto }" @click="ui.auto = !ui.auto">↓ Avto</button>
        <button class="sm" data-testid="proto-clear" @click="clearLog">Tozalash</button>
        <button class="sm" data-testid="proto-export-json" title="Jurnalni JSON sifatida yuklash" :disabled="!conn.sessionId" @click="exportLog('json')">JSON</button>
        <button class="sm" data-testid="proto-export-txt" title="Jurnalni matn sifatida yuklash" :disabled="!conn.sessionId" @click="exportLog('txt')">TXT</button>
      </div>
      <div v-if="!isWs && sseTypes.length > 1" class="proto-types" role="group" aria-label="Event turi filtri" data-testid="proto-types">
        <span class="muted">Event turi:</span>
        <button v-for="t in sseTypes" :key="t" class="chip" :class="{ on: typeOn(t) }" :aria-pressed="typeOn(t)" :data-type="t" @click="toggleType(t)">{{ t }}</button>
      </div>
      <p v-if="conn.lost && live" class="state-error" role="alert" style="margin:0;padding:6px 12px">Server bilan oqim uzildi. Sahifani yangilang yoki qayta ulaning.</p>
      <div ref="listEl" class="proto-list scroll" data-testid="proto-list" tabindex="0" aria-label="Xabarlar ro'yxati">
        <p v-if="!conn.events.length" class="proto-empty muted" data-testid="proto-empty">{{ isWs ? 'Ulanib, xabar yuboring — qabul qilingan va yuborilgan xabarlar shu yerda ko\'rinadi.' : 'Ulaning — serverdan kelgan event\'lar shu yerda ko\'rinadi.' }}</p>
        <p v-else-if="!filtered.length" class="proto-empty muted" data-testid="proto-nomatch">Filtr bo'yicha yozuv yo'q ({{ conn.events.length }} ta yashirilgan).</p>
        <p v-if="filtered.length > RENDER_MAX" class="proto-more muted">Oxirgi {{ RENDER_MAX }} ta ko'rsatilmoqda ({{ filtered.length }} dan) — qidiruv yoki eksport orqali hammasiga yeting.</p>
        <template v-for="e in shown" :key="e.seq">
          <div v-if="isSystem(e)" class="plog sys" :class="e.type" data-testid="proto-sys" :data-type="e.type">
            <span class="t">{{ fmtTime(e.ts) }}</span><span class="ic" aria-hidden="true">{{ e.type === 'error' ? '⚠' : e.type === 'open' ? '●' : e.type === 'comment' ? ':' : '○' }}</span><span class="tx">{{ systemText(e) }}</span>
          </div>
          <div v-else class="plog msg" :class="[e.dir ?? 'in', { sel: open.has(e.seq) }]" data-testid="proto-msg" :data-dir="e.dir ?? 'in'" role="button" tabindex="0" :aria-expanded="open.has(e.seq)" @click="toggleRow(e)" @keydown.enter="toggleRow(e)">
            <span class="t">{{ fmtTime(e.ts) }}</span>
            <span class="ic" :title="e.dir === 'out' ? 'Yuborilgan' : 'Qabul qilingan'" aria-hidden="true">{{ e.dir === 'out' ? '↑' : '↓' }}</span>
            <span v-if="e.type === 'event'" class="tag" data-testid="proto-etype">{{ e.event }}</span><span v-else-if="e.kind === 'binary'" class="tag">binary</span>
            <span v-if="e.id" class="muted eid" :title="'event id'">#{{ e.id }}</span>
            <span class="tx">{{ preview(e) }}</span>
            <span class="sz muted">{{ fmtSize(e.size ?? 0) }}</span>
            <div v-if="open.has(e.seq)" class="pdetail" data-testid="proto-detail" @click.stop>
              <pre :class="detail(e).kind">{{ detail(e).text }}</pre>
              <button class="sm" data-testid="proto-copy" @click="copy(e)">Nusxa</button>
            </div>
          </div>
        </template>
      </div>
      <div v-if="isWs" class="proto-compose" data-testid="proto-compose">
        <div class="proto-tpls" data-testid="proto-templates" role="group" aria-label="Saqlangan xabarlar">
          <span class="muted">Shablonlar:</span>
          <span v-for="t in templates" :key="t.id" class="tpl" :class="{ on: activeTpl === t.id }"><button class="chip" data-testid="proto-tpl" :title="oneLine(t.data, 80)" @click="loadTpl(t)">{{ t.name }}</button><button class="ghost x" :aria-label="`${t.name} shablonini o'chirish`" data-testid="proto-tpl-del" @click="delTpl(t)">×</button></span>
          <span v-if="!templates.length" class="muted" data-testid="proto-tpl-empty">hali yo'q</span>
        </div>
        <div class="proto-compose-row">
          <div class="seg-group" role="group" aria-label="Xabar turi">
            <button v-for="k in (['text', 'json', 'binary'] as const)" :key="k" class="seg" :class="{ on: kind === k }" :aria-pressed="kind === k" :data-kind="k" @click="kind = k">{{ { text: 'Matn', json: 'JSON', binary: 'Binary' }[k] }}</button>
          </div>
          <select v-if="kind === 'binary'" v-model="enc" class="sm" aria-label="Binary kodlash" data-testid="proto-enc"><option value="hex">hex (00 ff 10)</option><option value="base64">base64</option></select>
          <span style="flex:1" />
          <input v-model="tplName" class="tpl-name" placeholder="Shablon nomi" aria-label="Shablon nomi" data-testid="proto-tpl-name">
          <button class="sm" data-testid="proto-tpl-save" :disabled="!msg.trim()" @click="saveTpl">{{ activeTpl && templates.some(t => t.id === activeTpl && t.name === tplName.trim()) ? 'Shablonni yangilash' : 'Shablon sifatida saqlash' }}</button>
        </div>
        <div class="proto-compose-box" @keydown="onComposeKey">
          <textarea v-if="kind === 'binary'" v-model="msg" class="proto-ta" spellcheck="false" placeholder="00 ff 10 a0" aria-label="Binary xabar" data-testid="proto-compose-text" />
          <CodeEditor v-else :key="kind" v-model="msg" :lang="kind === 'json' ? 'json' : 'raw'" testid="proto-compose-text" label="Yuboriladigan xabar" :placeholder="kind === 'json' ? '{ &quot;type&quot;: &quot;ping&quot;, &quot;id&quot;: &quot;{{$guid}}&quot; }' : 'Xabar matni… ({{o\'zgaruvchi}} ishlatish mumkin)'" />
          <button class="primary proto-send" data-testid="proto-send" :disabled="conn.status !== 'open' || !msg.trim()" aria-keyshortcuts="Control+Enter Meta+Enter" @click="send"><Icon name="send" :size="14" />Yuborish <span class="muted kb">⌘↵</span></button>
        </div>
        <p v-if="!jsonOk" class="state-error" role="alert" data-testid="proto-json-err" style="margin:4px 0 0;padding:4px 10px">JSON noto'g'ri</p>
        <p v-if="sendErr" class="state-error" role="alert" data-testid="proto-send-err" style="margin:4px 0 0;padding:4px 10px">{{ sendErr }}</p>
      </div>
    </section>
  </div>
</template>
