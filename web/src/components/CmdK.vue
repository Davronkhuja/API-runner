<script setup lang="ts">
/** ⌘K: so'rov (nom/URL/metod), papka, muhit va amallar bo'yicha qidiruv. ↑↓ Enter Esc. */
import { computed, nextTick, ref, watch } from 'vue'
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { openRequest } from '../lib/actions'
import { downloadFrom } from '../lib/exporter'
import { cmdkOpen, findOpen, importOpen, sidePanel, trashOpen } from '../lib/ui'
import { toggleTheme } from '../lib/theme'
import { isFolder, type RequestItem, type TreeItem } from '../types/model'
import Icon from './Icon.vue'

const tabs = useTabs(), tree = useTree(), ws = useWorkspace()
const q = ref(''), sel = ref(0)
const input = ref<HTMLInputElement>()
interface Hit { key: string; kind: string; label: string; sub: string; method?: string; run: () => void }

const requests = computed<Hit[]>(() => {
  const out: Hit[] = []
  const walk = (cid: string, items: TreeItem[], path: string) => {
    for (const it of items) {
      if (isFolder(it)) walk(cid, it.item, path + it.name + ' / ')
      else {
        const r = it as RequestItem
        out.push({ key: `r:${cid}:${r.id}`, kind: 'request', label: r.name, sub: path + (r.request.url?.raw ?? ''), method: r.request.method, run: () => { openRequest(cid, r.id, true) } })
      }
    }
  }
  for (const m of tree.metas) { const c = tree.cols[m.id]; if (c) walk(m.id, c.item, m.name + ' / ') }
  return out
})
const others = computed<Hit[]>(() => [
  { key: 'a:new', kind: 'action', label: 'Yangi so\'rov', sub: '⌘T', run: () => { tabs.openNew() } },
  { key: 'a:settings', kind: 'action', label: 'Sozlamalar', sub: '', run: () => { tabs.open('settings', 'settings', 'Sozlamalar', { permanent: true }) } },
  { key: 'a:cookies', kind: 'action', label: 'Cookie Manager', sub: '', run: () => { tabs.open('cookies', 'cookies', 'Cookie\'lar', { permanent: true }) } },
  { key: 'a:find', kind: 'action', label: 'Find & Replace', sub: 'Workspace bo\'ylab', run: () => { findOpen.value = true } },
  { key: 'a:export-ws', kind: 'action', label: 'Eksport: workspace zaxirasi (zip)', sub: '', run: () => { downloadFrom('/api/workspace/export') } },
  { key: 'a:trash', kind: 'action', label: 'Savat', sub: '30 kun', run: () => { trashOpen.value = true } },
  { key: 'a:theme', kind: 'action', label: 'Temani almashtirish', sub: '', run: toggleTheme },
  { key: 'a:import', kind: 'action', label: 'Import (Postman, OpenAPI)', sub: '.json', run: () => { importOpen.value = true } },
  { key: 'a:runner', kind: 'action', label: 'Runner', sub: 'Collection Runner', run: () => { sidePanel.value = 'runner'; const m = tree.metas[0]; if (m) tabs.open('runner', m.id, 'Runner: ' + m.name, { permanent: true }) } },
  ...ws.environments.map<Hit>(e => ({ key: 'e:' + e.id, kind: 'env', label: e.name, sub: 'Muhit', run: () => { tabs.open('environment', e.id, e.name, { permanent: true }) } })),
])
const hits = computed(() => {
  const s = q.value.trim().toLowerCase()
  const all = [...requests.value, ...others.value]
  if (!s) return [...others.value.slice(0, 4), ...requests.value.slice(0, 8)]
  return all.filter(h => (h.label + ' ' + h.sub + ' ' + (h.method ?? '')).toLowerCase().includes(s)).slice(0, 40)
})
watch(cmdkOpen, async o => { if (o) { q.value = ''; sel.value = 0; await nextTick(); input.value?.focus() } })
watch(q, () => (sel.value = 0))
const close = () => { cmdkOpen.value = false }
function go(h?: Hit) { if (!h) return; close(); h.run() }
function key(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') { e.preventDefault(); sel.value = Math.min(hits.value.length - 1, sel.value + 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); sel.value = Math.max(0, sel.value - 1) }
  else if (e.key === 'Enter') { e.preventDefault(); go(hits.value[sel.value]) }
  else if (e.key === 'Escape') { e.preventDefault(); close() }
  nextTick(() => document.querySelector('[data-testid=cmdk-row].sel')?.scrollIntoView({ block: 'nearest' }))
}
</script>

<template>
  <div v-if="cmdkOpen" class="overlay" style="align-items:flex-start" data-testid="cmdk-overlay" @click.self="close">
    <div class="dialog cmdk" role="dialog" aria-modal="true" aria-label="Qidirish" data-testid="cmdk" @keydown="key">
      <input ref="input" v-model="q" placeholder="So'rov, papka yoki amal…" aria-label="Qidiruv" role="combobox" aria-expanded="true" aria-controls="cmdk-list" :aria-activedescendant="'cmdk-' + sel" data-testid="cmdk-input">
      <div id="cmdk-list" class="list" role="listbox">
        <button v-for="(h, i) in hits" :id="'cmdk-' + i" :key="h.key" class="row" :class="{ sel: i === sel }" role="option" :aria-selected="i === sel" data-testid="cmdk-row" tabindex="-1" @mousemove="sel = i" @click="go(h)">
          <span v-if="h.method" class="m" :class="'m-' + h.method">{{ h.method }}</span>
          <span v-else class="ico"><Icon :name="h.kind === 'env' ? 'globe' : 'bolt'" :size="14" /></span>
          <span class="name">{{ h.label }}</span><span class="muted" style="font-size:var(--fs-sm);max-width:48%;overflow:hidden;text-overflow:ellipsis">{{ h.sub }}</span>
        </button>
        <div v-if="!hits.length" class="empty" data-testid="cmdk-empty">Hech narsa topilmadi</div>
      </div>
      <div class="hint"><span><span class="kbd">↑↓</span> tanlash</span><span><span class="kbd">↵</span> ochish</span><span><span class="kbd">Esc</span> yopish</span></div>
    </div>
  </div>
</template>
