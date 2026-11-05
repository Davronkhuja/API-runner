<script setup lang="ts">
/** Kengaytirilgan tarix (docs/design/History.dc.html): kunlar bo'yicha guruhlash, host/path, ×N, status filtri, ikki yozuv javobini solishtirish. */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { get } from '../api/client'
import { useHistory, type HistoryEntry } from '../stores/history'
import { openFromHistory } from '../lib/history'
import { saveAsHandler } from '../lib/actions'
import { useTabs } from '../stores/tabs'
import { askConfirm, fmtBytes, fmtMs } from '../lib/ui'
import { fetchStored } from '../lib/responses'
import { bodyLines, diffStats, headerDiff, lineDiff } from '../lib/diff'

const open = defineModel<boolean>({ required: true })
const hist = useHistory(), tabs = useTabs()
const all = ref<HistoryEntry[]>([])
const q = ref('')
const filter = ref<'all' | '2xx' | '4xx' | '5xx' | 'err'>('all')
const picked = ref<number[]>([])             // solishtirish uchun belgilangan yozuv id'lari (A, B)
const sel = ref<number | null>(null)
const expanded = ref<Set<number>>(new Set())           // ×N qatorlari: ichidagi alohida yozuvlarni ko'rsatish
const ignore = ref(true)

async function load() { all.value = await get('/api/history?kind=request&limit=300'); if (sel.value && !all.value.some(h => h.id === sel.value)) sel.value = null; picked.value = picked.value.filter(id => all.value.some(h => h.id === id)) }
watch(open, v => { if (v) { load(); q.value = ''; filter.value = 'all'; picked.value = []; sel.value = null } })
watch(() => hist.items, () => { if (open.value) load() })
const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape' && open.value) open.value = false }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

/** Tarixdagi URL: so'rov yuborilganda query alohida `params` da turadi — to'liq ko'rinish uchun birlashtiriladi. */
const fullUrl = (p: any) => {
  const qs = (p.params ?? []).filter((x: any) => x.name).map((x: any) => `${encodeURIComponent(x.name)}=${encodeURIComponent(x.value ?? '')}`).join('&')
  return qs && !String(p.url).includes('?') ? `${p.url}?${qs}` : p.url
}
// bir xil so'rov: metod + to'liq URL + so'rov tanasi (v2.3.8 yozuvlarida `body` — javob matni, shuning uchun hisobga olinmaydi)
const reqKey = (p: any) => `${p.method} ${fullUrl(p)} ${p.resp_headers !== undefined ? '' : p.body ?? ''}`
const parts = (url: string) => { try { const u = new URL(url); return { host: u.host, path: u.pathname + u.search } } catch { return { host: '', path: url } } }
const statusOf = (h: HistoryEntry) => h.payload.status
const cls = (s: any) => (s === undefined || s === null ? '' : typeof s === 'number' ? (s < 300 ? 'ok' : s < 400 ? 'ok' : s < 500 ? 'warn' : 'err') : 'err')
const when = (ts: number) => new Date(ts * 1000).toLocaleString()
const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
function dayLabel(ts: number) {
  const d = new Date(ts * 1000), t = new Date(), y = new Date(); y.setDate(t.getDate() - 1)
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString()
  return same(d, t) ? 'Bugun' : same(d, y) ? 'Kecha' : d.toLocaleDateString()
}
const passes = (h: HistoryEntry) => {
  const s = statusOf(h), n = typeof s === 'number' ? s : 0
  const okF = filter.value === 'all' || (filter.value === '2xx' && n >= 200 && n < 300) || (filter.value === '4xx' && n >= 400 && n < 500) || (filter.value === '5xx' && n >= 500) || (filter.value === 'err' && typeof s !== 'number')
  const t = q.value.trim().toLowerCase()
  return okF && (!t || `${h.payload.method} ${fullUrl(h.payload)} ${s}`.toLowerCase().includes(t))
}
// ketma-ket bir xil so'rovlar (metod + URL) bitta qatorga "×N" bo'lib birlashadi; ko'rsatiladigan — eng yangisi
interface Row { h: HistoryEntry; n: number; host: string; path: string; ids: number[]; members: HistoryEntry[] }
const groups = computed(() => {
  const rows: Row[] = []
  for (const h of all.value.filter(passes)) {
    const last = rows[rows.length - 1]
    if (last && reqKey(last.h.payload) === reqKey(h.payload) && dayLabel(last.h.ts) === dayLabel(h.ts)) { last.n++; last.ids.push(h.id); last.members.push(h); continue }
    rows.push({ h, n: 1, ...parts(fullUrl(h.payload)), ids: [h.id], members: [h] })
  }
  const out: { day: string; rows: Row[] }[] = []
  for (const r of rows) { const d = dayLabel(r.h.ts); const g = out[out.length - 1]; if (g && g.day === d) g.rows.push(r); else out.push({ day: d, rows: [r] }) }
  return out
})
function togglePick(id: number) {
  picked.value = picked.value.includes(id) ? picked.value.filter(x => x !== id) : [...picked.value.slice(-1), id]    // eng ko'pi bilan ikkita (A, B)
  sel.value = id
}
const current = computed(() => all.value.find(h => h.id === sel.value) ?? null)
// A — eskirog'i, B — yangirog'i (tanlash tartibidan qat'i nazar): "nima o'zgardi" o'qilishi tabiiy bo'lsin
const pair = computed(() => picked.value.map(id => all.value.find(h => h.id === id)).filter(Boolean).sort((x, y) => x!.ts - y!.ts) as HistoryEntry[])
const A = computed(() => pair.value[0])
const B = computed(() => pair.value[1])
const comparing = computed(() => !!A.value && !!B.value)
// Javob matni tarix yozuvida emas, serverda bitta nusxada (`response_id`); eski yozuvlarda `payload.body` bor
const loaded = ref<Record<number, { body: string; headers: Record<string, string> }>>({})
async function ensure(h?: HistoryEntry) {
  if (!h || loaded.value[h.id]) return
  const p = h.payload
  if (!p.response_id && p.resp_headers !== undefined) { loaded.value[h.id] = { body: p.body ?? '', headers: p.resp_headers }; return }      // v2.3.8 yozuvlari: matn yozuvning o'zida (`body` — javob)
  const st = p.response_id ? await fetchStored(p.response_id) : null
  loaded.value[h.id] = { body: st?.body ?? '', headers: st?.headers ?? {} }
}
const bodyOf = (h?: HistoryEntry) => (h ? loaded.value[h.id]?.body ?? '' : '')
const headersOf = (h?: HistoryEntry) => (h ? loaded.value[h.id]?.headers ?? {} : {})
watch(() => [A.value, B.value, current.value], () => { ensure(A.value); ensure(B.value); ensure(current.value ?? undefined) }, { immediate: true })
const diff = computed(() => (comparing.value ? lineDiff(bodyLines(bodyOf(A.value), ignore.value), bodyLines(bodyOf(B.value), ignore.value)) : []))
const stats = computed(() => diffStats(diff.value))
const hdrs = computed(() => (comparing.value ? headerDiff(headersOf(A.value), headersOf(B.value), ignore.value) : []))

function openInTab(h: HistoryEntry) { openFromHistory(h); open.value = false }
function saveToCollection(h: HistoryEntry) {
  openFromHistory(h); open.value = false
  const t = tabs.active
  if (t) saveAsHandler.fn?.(t)
}
function toggleExpand(id: number) { const n = new Set(expanded.value); n.has(id) ? n.delete(id) : n.add(id); expanded.value = n }
async function clearAll() { if (await askConfirm("Butun so'rovlar tarixi tozalansinmi?", 'Tozalash')) { await hist.clear('request'); await load(); sel.value = null; picked.value = [] } }
async function removeOne(id: number) { await hist.remove(id); await load() }
</script>

<template>
  <template v-if="open">
    <div class="drawer-backdrop" data-testid="drawer-backdrop" @click="open = false" />
    <aside class="hist-drawer hist-wide" role="dialog" aria-modal="true" aria-label="So'rovlar tarixi" data-testid="history-drawer">
      <div class="hx-list">
        <div class="hx-top">
          <div style="display:flex;align-items:center;gap:8px"><b style="flex:1;font-size:14px">Tarix</b>
            <button class="sm" data-testid="hd-clear" @click="clearAll">Tozalash…</button>
            <button class="ghost" aria-label="Yopish" data-testid="hd-close" @click="open = false">×</button></div>
          <input v-model="q" aria-label="Tarixdan qidirish" placeholder="URL, metod yoki status bo'yicha qidirish" data-testid="hd-search">
          <div class="hx-pills" role="group" aria-label="Status filtri">
            <button v-for="f in ([['all', 'Hammasi'], ['2xx', '2xx'], ['4xx', '4xx'], ['5xx', '5xx'], ['err', 'Xato']] as const)" :key="f[0]" class="pill" :class="{ on: filter === f[0] }" :aria-pressed="filter === f[0]" :data-filter="f[0]" @click="filter = f[0]">{{ f[1] }}</button>
          </div>
        </div>
        <div class="hx-scroll">
          <div v-for="g in groups" :key="g.day" data-testid="hd-group">
            <div class="hx-day" data-testid="hd-day">{{ g.day }}</div>
            <template v-for="r in g.rows" :key="r.h.id">
            <div class="hx-item" :class="{ on: sel === r.h.id }" data-testid="hd-row" role="button" tabindex="0" @click="sel = r.h.id" @keydown.enter="sel = r.h.id">
              <input type="checkbox" aria-label="Solishtirish uchun tanlash" data-testid="hd-pick" :checked="picked.includes(r.h.id)" @click.stop="togglePick(r.h.id)">
              <span class="m" :class="'m-' + r.h.payload.method">{{ r.h.payload.method }}</span>
              <span class="hx-url"><span class="hx-path" data-testid="hd-path">{{ r.path }}</span><span class="hx-host muted" data-testid="hd-host">{{ r.host }}<template v-if="r.n > 1"> · <b data-testid="hd-repeat">×{{ r.n }}</b></template></span></span>
              <span class="hx-st"><span class="status-pill" :class="cls(statusOf(r.h))" data-testid="hd-status">{{ statusOf(r.h) ?? '—' }}</span><span class="muted">{{ clock(r.h.ts) }}</span></span>
              <button class="ghost" aria-label="Tarixdan o'chirish" data-testid="hd-remove" @click.stop="removeOne(r.h.id)">×</button>
            </div>
            <button v-if="r.n > 1" class="linkbtn hx-expand" data-testid="hd-expand" :aria-expanded="expanded.has(r.h.id)" @click="toggleExpand(r.h.id)">{{ expanded.has(r.h.id) ? '▾ yig\'ish' : `▸ ${r.n} ta yozuvni ko'rsatish (solishtirish uchun)` }}</button>
            <template v-if="r.n > 1 && expanded.has(r.h.id)">
              <div v-for="m in r.members" :key="m.id" class="hx-item hx-sub" :class="{ on: sel === m.id }" data-testid="hd-sub" role="button" tabindex="0" @click="sel = m.id" @keydown.enter="sel = m.id">
                <input type="checkbox" aria-label="Solishtirish uchun tanlash" data-testid="hd-pick-sub" :checked="picked.includes(m.id)" @click.stop="togglePick(m.id)">
                <span /><span class="hx-url"><span class="hx-host muted">{{ when(m.ts) }}</span></span>
                <span class="hx-st"><span class="status-pill" :class="cls(statusOf(m))">{{ statusOf(m) ?? '—' }}</span></span><span />
              </div>
            </template>
            </template>
          </div>
          <div v-if="!groups.length" class="empty" data-testid="hd-empty">{{ all.length ? "Filtr bo'yicha yozuv yo'q" : "Hali tarix yo'q" }}</div>
        </div>
      </div>

      <div class="hx-main" data-testid="hd-detail">
        <template v-if="comparing">
          <div class="hx-cmp-head">
            <div v-for="(h, i) in [A!, B!]" :key="h.id" class="hx-card" :data-testid="'hd-card-' + 'AB'[i]">
              <span class="status-pill" :class="cls(statusOf(h))">{{ statusOf(h) ?? '—' }}</span><b>{{ 'AB'[i] }} · {{ when(h.ts) }}</b>
              <span class="muted" style="margin-left:auto">{{ h.payload.time != null ? fmtMs(h.payload.time) : '—' }} · {{ h.payload.size != null ? fmtBytes(h.payload.size) : '—' }}</span>
            </div>
          </div>
          <div class="hx-statline">
            <span class="chip-add" data-testid="hd-add">+{{ stats.add }} qator</span><span class="chip-del" data-testid="hd-del">−{{ stats.del }} qator</span>
            <span class="muted" data-testid="hd-hdiff">Headers: {{ hdrs.length }} farq{{ ignore ? ' (Date va o\'zgaruvchan sarlavhalar chiqarib tashlandi)' : '' }}</span>
            <span style="flex:1" />
            <label class="muted" style="display:flex;align-items:center;gap:6px"><input v-model="ignore" type="checkbox" data-testid="hd-ignore">Vaqt va ID maydonlarini e'tiborsiz qoldirish</label>
          </div>
          <div class="hx-diff" data-testid="hd-diff">
            <div v-for="(d, i) in diff" :key="i" class="hx-dl" :class="d.type" data-testid="hd-diff-line">
              <span class="n">{{ d.a ?? d.b }}</span><span class="mk">{{ d.type === 'add' ? '+' : d.type === 'del' ? '−' : '' }}</span><span class="t">{{ d.text }}</span>
            </div>
            <div v-if="!diff.length" class="empty">Javoblar bo'sh</div>
          </div>
          <p v-if="loaded[A!.id] && loaded[B!.id] && !bodyOf(A) && !bodyOf(B)" class="muted" data-testid="hd-nobody">Bu yozuvlarda javob matni saqlanmagan (eski tarix) — faqat yangi so'rovlarda solishtirish mumkin.</p>
        </template>
        <template v-else-if="current">
          <div class="hx-det-head">
            <span class="m" :class="'m-' + current.payload.method" style="font-size:12px">{{ current.payload.method }}</span>
            <b class="mono" data-testid="hd-det-path">{{ parts(fullUrl(current.payload)).path }}</b><span class="muted">{{ parts(fullUrl(current.payload)).host }}</span>
            <span style="flex:1" />
            <button data-testid="hd-open" @click="openInTab(current)">Tabda ochish</button>
            <button data-testid="hd-save" @click="saveToCollection(current)">Collection'ga saqlash</button>
          </div>
          <div class="hx-card" style="max-width:420px"><span class="status-pill" :class="cls(statusOf(current))">{{ statusOf(current) ?? '—' }}</span><b>{{ when(current.ts) }}</b>
            <span class="muted" style="margin-left:auto">{{ current.payload.time != null ? fmtMs(current.payload.time) : '—' }} · {{ current.payload.size != null ? fmtBytes(current.payload.size) : '—' }}</span></div>
          <pre v-if="bodyOf(current)" class="hx-body" data-testid="hd-body">{{ bodyOf(current) }}</pre>
          <p v-else class="muted">Javob matni saqlanmagan.</p>
          <p class="muted" style="font-size:12px">Ikki yozuvni solishtirish uchun ro'yxatda ikkita katakchani belgilang.</p>
        </template>
        <div v-else class="empty" data-testid="hd-placeholder">Yozuvni tanlang yoki solishtirish uchun ikkitasini belgilang.</div>
      </div>
    </aside>
  </template>
</template>
