<script setup lang="ts">
/** Tarix ro'yxati: YAGONA komponent (Sidebar paneli va kengaytirilgan Tarix oynasi): kunlar bo'yicha guruh, host va path alohida, status pill, vaqt, ×N, filtr va qidiruv. */
import { computed, ref } from 'vue'
import type { HistoryEntry } from '../stores/history'

const props = withDefaults(defineProps<{ entries: HistoryEntry[]; selected?: number | null; picked?: number[]; selectable?: boolean; rowTestid?: string; emptyText?: string; tp?: string }>(), { selectable: false, rowTestid: 'hd-row', tp: 'hd', picked: () => [] })
const emit = defineEmits<{ select: [h: HistoryEntry]; pick: [id: number]; remove: [id: number] }>()
const q = ref('')
const filter = ref<'all' | '2xx' | '4xx' | '5xx' | 'err'>('all')
const expanded = ref<Set<number>>(new Set())

/** Tarixdagi URL: so'rov yuborilganda query alohida `params` da turadi — to'liq ko'rinish uchun birlashtiriladi. */
const fullUrl = (p: any) => {
  const qs = (p.params ?? []).filter((x: any) => x.name).map((x: any) => `${encodeURIComponent(x.name)}=${encodeURIComponent(x.value ?? '')}`).join('&')
  return qs && !String(p.url).includes('?') ? `${p.url}?${qs}` : p.url
}
// bir xil so'rov: metod + to'liq URL + so'rov tanasi (v2.3.8 yozuvlarida `body` — javob matni, shuning uchun hisobga olinmaydi)
const reqKey = (p: any) => `${p.method} ${fullUrl(p)} ${p.resp_headers !== undefined ? '' : p.body ?? ''}`
const parts = (url: string) => { try { const u = new URL(url); return { host: u.host, path: u.pathname + u.search } } catch { return { host: '', path: url } } }
const statusOf = (h: HistoryEntry) => h.payload.status
const cls = (s: any) => (s === undefined || s === null ? '' : typeof s === 'number' ? (s < 400 ? 'ok' : s < 500 ? 'warn' : 'err') : 'err')
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
interface Row { h: HistoryEntry; n: number; host: string; path: string; members: HistoryEntry[] }
const groups = computed(() => {
  const rows: Row[] = []
  for (const h of props.entries.filter(passes)) {
    const last = rows[rows.length - 1]
    if (last && reqKey(last.h.payload) === reqKey(h.payload) && dayLabel(last.h.ts) === dayLabel(h.ts)) { last.n++; last.members.push(h); continue }
    rows.push({ h, n: 1, ...parts(fullUrl(h.payload)), members: [h] })
  }
  const out: { day: string; rows: Row[] }[] = []
  for (const r of rows) { const d = dayLabel(r.h.ts); const g = out[out.length - 1]; if (g && g.day === d) g.rows.push(r); else out.push({ day: d, rows: [r] }) }
  return out
})
function toggleExpand(id: number) { const n = new Set(expanded.value); n.has(id) ? n.delete(id) : n.add(id); expanded.value = n }
defineExpose({ reset: () => { q.value = ''; filter.value = 'all' } })
</script>

<template>
  <div class="hl" data-testid="history-list-comp">
    <div class="hx-top">
      <slot name="head" />
      <input v-model="q" aria-label="Tarixdan qidirish" placeholder="URL, metod yoki status bo'yicha qidirish" :data-testid="`${tp}-search`">
      <div class="hx-pills" role="group" aria-label="Status filtri">
        <button v-for="f in ([['all', 'Hammasi'], ['2xx', '2xx'], ['4xx', '4xx'], ['5xx', '5xx'], ['err', 'Xato']] as const)" :key="f[0]" class="pill" :class="{ on: filter === f[0] }" :aria-pressed="filter === f[0]" :data-filter="f[0]" @click="filter = f[0]">{{ f[1] }}</button>
      </div>
    </div>
    <div class="hx-scroll">
      <div v-for="g in groups" :key="g.day" :data-testid="`${tp}-group`">
        <div class="hx-day" :data-testid="`${tp}-day`">{{ g.day }}</div>
        <template v-for="r in g.rows" :key="r.h.id">
          <div class="hx-item" :class="{ on: selected === r.h.id, plain: !selectable }" :data-testid="rowTestid" @click="emit('select', r.h)">
            <input v-if="selectable" type="checkbox" aria-label="Solishtirish uchun tanlash" :data-testid="`${tp}-pick`" :checked="picked.includes(r.h.id)" @click.stop="emit('pick', r.h.id)">
            <button class="hx-main" :title="r.path + ' · ' + r.host" @click.stop="emit('select', r.h)">
              <span class="m" :class="'m-' + r.h.payload.method">{{ r.h.payload.method }}</span>
              <span class="hx-url"><span class="hx-path" :data-testid="`${tp}-path`">{{ r.path }}</span><span class="hx-host muted" :data-testid="`${tp}-host`">{{ r.host }}<template v-if="r.n > 1"> · <b :data-testid="`${tp}-repeat`">×{{ r.n }}</b></template></span></span>
              <span class="hx-st"><span class="status-pill" :class="cls(statusOf(r.h))" :data-testid="`${tp}-status`">{{ statusOf(r.h) ?? '—' }}</span><span class="muted">{{ clock(r.h.ts) }}</span></span>
            </button>
            <button class="ghost hx-x" aria-label="Tarixdan o'chirish" :data-testid="`${tp}-remove`" @click.stop="emit('remove', r.h.id)">×</button>
          </div>
          <template v-if="selectable">
            <button v-if="r.n > 1" class="linkbtn hx-expand" :data-testid="`${tp}-expand`" :aria-expanded="expanded.has(r.h.id)" @click="toggleExpand(r.h.id)">{{ expanded.has(r.h.id) ? '▾ yig\'ish' : `▸ ${r.n} ta yozuvni ko'rsatish (solishtirish uchun)` }}</button>
            <template v-if="r.n > 1 && expanded.has(r.h.id)">
              <div v-for="m in r.members" :key="m.id" class="hx-item hx-sub" :class="{ on: selected === m.id }" :data-testid="`${tp}-sub`" @click="emit('select', m)">
                <input type="checkbox" aria-label="Solishtirish uchun tanlash" :data-testid="`${tp}-pick-sub`" :checked="picked.includes(m.id)" @click.stop="emit('pick', m.id)">
                <button class="hx-main" @click.stop="emit('select', m)"><span /><span class="hx-url"><span class="hx-host muted">{{ when(m.ts) }}</span></span>
                  <span class="hx-st"><span class="status-pill" :class="cls(statusOf(m))">{{ statusOf(m) ?? '—' }}</span></span></button><span />
              </div>
            </template>
          </template>
        </template>
      </div>
      <div v-if="!groups.length" class="empty" :data-testid="`${tp}-empty`">{{ entries.length ? "Filtr bo'yicha yozuv yo'q" : (emptyText ?? "Hali tarix yo'q") }}</div>
    </div>
  </div>
</template>
