<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTree } from '../stores/tree'
import { useTabs, type Tab } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { post } from '../api/client'
import { draftFromItem } from '../lib/draft'
import { specFor } from '../lib/scope'
import { parseDataFile, isDataFile } from '../lib/datafile'
import DataPreview from './DataPreview.vue'
import { isFolder, type RequestItem, type TreeItem } from '../types/model'

const props = defineProps<{ tab: Tab }>()
const tree = useTree(), tabs = useTabs(), ws = useWorkspace()
props.tab.state ??= {}
const st = props.tab.state!      // reaktiv proksi (??= xom obyektni qaytaradi)
st.order ??= null; st.checked ??= {}; st.results ??= {}; st.data ??= null
const cid = props.tab.ref!

function flat(items: TreeItem[], path = ''): { id: string; name: string; method: string; path: string; item: RequestItem }[] {
  return items.flatMap(i => isFolder(i) ? flat(i.item, path + i.name + ' / ') : [{ id: i.id, name: i.name, method: i.request.method, path, item: i }])
}
const base = computed(() => flat(tree.cols[cid]?.item ?? []))
const items = computed(() => {
  const order: string[] | null = st.order
  if (!order) return base.value
  const byId = new Map(base.value.map(x => [x.id, x]))
  const known = order.filter(id => byId.has(id)).map(id => byId.get(id)!)
  return [...known, ...base.value.filter(x => !order.includes(x.id))]
})
const isOn = (id: string) => st.checked[id] !== false

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
async function onZoneDrop(e: DragEvent) {
  zone.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f && isDataFile(f)) { e.preventDefault(); e.stopPropagation(); loadData(f.name, await f.text()) }
}
const running = ref(false)
async function run() {
  running.value = true
  st.results = {}
  for (const x of items.value) {
    if (!isOn(x.id)) continue
    st.results[x.id] = { status: '…' }
    const draft = draftFromItem(x.item)
    try {
      const spec = specFor(draft, `${cid}:${x.id}`); spec.timeout = 30
      const r = await post('/run_one', spec)
      st.results[x.id] = { status: r.status, time: r.time }
    } catch (e: any) { st.results[x.id] = { status: 'ERR' } }
  }
  running.value = false
}
</script>

<template>
  <div class="editor" data-testid="runner-tab">
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
      <b>{{ tree.cols[cid]?.info.name }}</b>
      <button class="primary" data-testid="runner-run" :disabled="running" @click="run">▶ Ishga tushirish</button>
      <span class="muted" data-testid="runner-data-info">{{ st.data ? `${st.data.name}: ${st.data.rows.length} qator` : 'Data fayl yo\'q (CSV/JSON ni shu oynaga tashlang)' }}</span>
    </div>
    <div class="drop-zone" :class="{ over: zone }" data-testid="runner-dropzone" @dragover.prevent="zone = true" @dragleave="zone = false" @drop="onZoneDrop">CSV/JSON faylni shu yerga tashlang</div>
    <DataPreview v-if="st.data?.rows?.length" :rows="st.data.rows" />
    <div v-for="(x, i) in items" :key="x.id" class="row" data-testid="runner-item" draggable="true" :class="{ 'drop-before': overIdx === i }"
         @dragstart="dragId = x.id" @dragover.prevent="overIdx = i" @dragleave="overIdx = null" @drop.prevent="drop(i)" @dragend="dragId = overIdx = null">
      <span class="grip">⋮⋮</span>
      <input type="checkbox" :checked="isOn(x.id)" @change="st.checked[x.id] = ($event.target as HTMLInputElement).checked">
      <span class="m" :class="'m-' + x.method">{{ x.method }}</span>
      <span class="name"><span class="muted">{{ x.path }}</span>{{ x.name }}</span>
      <span v-if="st.results[x.id]" :class="typeof st.results[x.id].status === 'number' && st.results[x.id].status < 400 ? 'ok' : 'err'" data-testid="runner-result">{{ st.results[x.id].status }}</span>
    </div>
    <div v-if="!items.length" class="empty">Collection'da so'rov yo'q</div>
  </div>
</template>
