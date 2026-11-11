<script setup lang="ts">
/** Kengaytirilgan tarix (docs/design/History.dc.html): kunlar bo'yicha guruhlash, host/path, ×N, status filtri, ikki yozuv javobini solishtirish. */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { get } from '../api/client'
import { useHistory, type HistoryEntry } from '../stores/history'
import { openFromHistory } from '../lib/history'
import { saveAsHandler } from '../lib/actions'
import { useTabs } from '../stores/tabs'
import { askConfirm, fmtBytes, fmtMs } from '../lib/ui'
import HistoryList from './HistoryList.vue'
import StateBlock from './StateBlock.vue'
import { fetchStored } from '../lib/responses'
import { bodyLines, diffStats, headerDiff, lineDiff } from '../lib/diff'

const open = defineModel<boolean>({ required: true })
const hist = useHistory(), tabs = useTabs()
const all = ref<HistoryEntry[]>([])
const listEl = ref<InstanceType<typeof HistoryList>>()
const picked = ref<number[]>([])             // solishtirish uchun belgilangan yozuv id'lari (A, B)
const sel = ref<number | null>(null)
const ignore = ref(true)

const loadErr = ref('')
async function load() { loadErr.value = ''; try { all.value = await get('/api/history?kind=request&limit=300') } catch (e: any) { loadErr.value = e.message || 'Tarixni o\'qib bo\'lmadi'; return }; if (sel.value && !all.value.some(h => h.id === sel.value)) sel.value = null; picked.value = picked.value.filter(id => all.value.some(h => h.id === id)) }
watch(open, v => { if (v) { load(); listEl.value?.reset(); picked.value = []; sel.value = null } })
watch(() => hist.items, () => { if (open.value) load() })
const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape' && open.value) open.value = false }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

const statusOf = (h: HistoryEntry) => h.payload.status
const cls = (s: any) => (s === undefined || s === null ? '' : typeof s === 'number' ? (s < 400 ? 'ok' : s < 500 ? 'warn' : 'err') : 'err')
const when = (ts: number) => new Date(ts * 1000).toLocaleString()
const parts = (url: string) => { try { const u = new URL(url); return { host: u.host, path: u.pathname + u.search } } catch { return { host: '', path: url } } }
const fullUrl = (p: any) => {
  const qs = (p.params ?? []).filter((x: any) => x.name).map((x: any) => `${encodeURIComponent(x.name)}=${encodeURIComponent(x.value ?? '')}`).join('&')
  return qs && !String(p.url).includes('?') ? `${p.url}?${qs}` : p.url
}
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
async function clearAll() { if (await askConfirm("Butun so'rovlar tarixi tozalansinmi?", 'Tozalash')) { await hist.clear('request'); await load(); sel.value = null; picked.value = [] } }
async function removeOne(id: number) { await hist.remove(id); await load() }
</script>

<template>
  <template v-if="open">
    <div class="drawer-backdrop" data-testid="drawer-backdrop" @click="open = false" />
    <aside class="hist-drawer hist-wide" role="dialog" aria-modal="true" aria-label="So'rovlar tarixi" data-testid="history-drawer">
      <div class="hx-list">
        <StateBlock v-if="loadErr" kind="error" :text="loadErr" testid="hd-error" @retry="load" />
        <HistoryList ref="listEl" :entries="all" :selected="sel" :picked="picked" selectable @select="h => (sel = h.id)" @pick="togglePick" @remove="removeOne">
          <template #head>
            <div style="display:flex;align-items:center;gap:8px"><b style="flex:1;font-size:var(--fs-lg)">Tarix</b>
              <button class="sm" data-testid="hd-clear" @click="clearAll">Tozalash…</button>
              <button class="ghost" aria-label="Yopish" data-testid="hd-close" @click="open = false">×</button></div>
          </template>
        </HistoryList>
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
            <span class="m" :class="'m-' + current.payload.method" style="font-size:var(--fs-sm)">{{ current.payload.method }}</span>
            <b class="mono" data-testid="hd-det-path">{{ parts(fullUrl(current.payload)).path }}</b><span class="muted">{{ parts(fullUrl(current.payload)).host }}</span>
            <span style="flex:1" />
            <button data-testid="hd-open" @click="openInTab(current)">Tabda ochish</button>
            <button data-testid="hd-save" @click="saveToCollection(current)">Collection'ga saqlash</button>
          </div>
          <div class="hx-card" style="max-width:420px"><span class="status-pill" :class="cls(statusOf(current))">{{ statusOf(current) ?? '—' }}</span><b>{{ when(current.ts) }}</b>
            <span class="muted" style="margin-left:auto">{{ current.payload.time != null ? fmtMs(current.payload.time) : '—' }} · {{ current.payload.size != null ? fmtBytes(current.payload.size) : '—' }}</span></div>
          <pre v-if="bodyOf(current)" class="hx-body" data-testid="hd-body">{{ bodyOf(current) }}</pre>
          <p v-else class="muted">Javob matni saqlanmagan.</p>
          <p class="muted" style="font-size:var(--fs-sm)">Ikki yozuvni solishtirish uchun ro'yxatda ikkita katakchani belgilang.</p>
        </template>
        <div v-else class="empty" data-testid="hd-placeholder">Yozuvni tanlang yoki solishtirish uchun ikkitasini belgilang.</div>
      </div>
    </aside>
  </template>
</template>
