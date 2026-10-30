<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useTabs, type Tab } from './stores/tabs'
import { useTree } from './stores/tree'
import { useWorkspace } from './stores/workspace'
import { useHistory } from './stores/history'
import { put, get } from './api/client'
import { askClose, closeDialog, confirmDialog, toast } from './lib/ui'
import { createRequestIn, saveAsHandler, saveTab, sendTab, openRequest } from './lib/actions'
import Sidebar from './components/Sidebar.vue'
import TabBar from './components/TabBar.vue'
import RequestEditor from './components/RequestEditor.vue'
import EnvTab from './components/EnvTab.vue'
import RunnerTab from './components/RunnerTab.vue'
import CollectionTab from './components/CollectionTab.vue'
import { post as apiPost } from './api/client'
import { parseCurl, applyCurlToDraft } from './lib/curl'
import { showToast } from './lib/ui'

const tabs = useTabs(), tree = useTree(), ws = useWorkspace(), hist = useHistory()
const ready = ref(false)
const saveAs = ref<{ tab: Tab; name: string; target: string; resolve: (ok: boolean) => void } | null>(null)
const dropping = ref(false)

const saveTargets = computed(() => tree.rows.filter(r => r.isCollection || r.folder).map(r => ({ key: `${r.collectionId}:${r.id}`, label: '　'.repeat(r.depth) + r.name })))

saveAsHandler.fn = tab => new Promise(resolve => {
  const first = saveTargets.value[0]?.key ?? ''
  saveAs.value = { tab, name: tab.draft!.name, target: first, resolve }
})
async function confirmSaveAs() {
  const s = saveAs.value!; saveAs.value = null
  const [cid, pid] = s.target.split(':')
  await createRequestIn(s.tab, cid, pid || null, s.name.trim() || 'So\'rov')
  s.resolve(true)
}
async function ensureCollection() {
  if (!tree.metas.length) await tree.createCollection('Mening collection')
}

// UI holati (tree ochiq/yopiq) — server tomonda; tablar tabs store ichida
let uiTimer: ReturnType<typeof setTimeout> | null = null
function persistTree() { if (uiTimer) clearTimeout(uiTimer); uiTimer = setTimeout(async () => { const cur = await get('/api/ui-state').catch(() => ({})); await put('/api/ui-state', { ...cur, expanded: tree.expandedOverride }).catch(() => {}) }, 400) }

function onKey(e: KeyboardEvent) {
  const mod = e.metaKey || e.ctrlKey
  const k = e.key.toLowerCase()
  if (e.ctrlKey && e.key === 'Tab') { e.preventDefault(); tabs.next(e.shiftKey ? -1 : 1) }
  else if (mod && k === 't' && e.shiftKey) { e.preventDefault(); tabs.reopenClosed() }
  else if (mod && k === 't') { e.preventDefault(); tabs.openNew() }
  else if (mod && k === 'w') { e.preventDefault(); if (tabs.activeId) tabs.close(tabs.activeId, t => askClose(`"${t.title}" saqlanmagan. Saqlansinmi?`), async t => { await saveTab(t) }) }
  else if (mod && k === 's') { e.preventDefault(); if (tabs.active) saveTab(tabs.active) }
  else if (mod && e.key === 'Enter') { e.preventDefault(); if (tabs.active?.kind === 'request') sendTab(tabs.active) }
}
// Hozircha faqat tab/daraxt yorliqlari; Cmd+T brauzerda band bo'lishi mumkin — Alt muqobili ham
onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await Promise.all([tree.load(), ws.load(), hist.load()])
  const st = await get('/api/ui-state').catch(() => ({}))
  if (st.expanded) tree.expandedOverride = st.expanded
  await tabs.restore()
  // tiklangan tablar uchun o'chirilgan elementlarni olib tashlash
  tabs.tabs.filter(t => t.kind === 'request' && t.ref && !tree.findItem(...(t.ref.split(':') as [string, string]))).forEach(t => { if (!t.dirty) tabs.dropRef(t.ref!) })
  await ensureCollection()
  ready.value = true
  const theme = localStorage.getItem('apiRunnerTheme'); if (theme) document.documentElement.dataset.theme = theme
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
import { watch } from 'vue'
watch(() => tree.expandedOverride, persistTree, { deep: true })
void openRequest

// Fayllarni (Postman collection, OpenAPI, CSV) va cURL matnini oynaga tashlab import qilish
function onWindowDragOver(e: DragEvent) {
  const t = e.dataTransfer?.types ?? []
  if (t.includes('Files')) { e.preventDefault(); dropping.value = true }
}
async function onWindowDrop(e: DragEvent) {
  dropping.value = false
  const dt = e.dataTransfer
  if (!dt) return
  const file = dt.files?.[0]
  if (file) {
    e.preventDefault()
    const text = await file.text()
    if (/\.csv$/i.test(file.name) || /text\/csv/.test(file.type)) return openRunnerWithData(file.name, text)
    try {
      const r = await apiPost('/api/import', { content: text })
      await tree.load()
      showToast(`Import qilindi: ${r.name}`, 'success')
    } catch (err: any) { showToast(err.message, 'error') }
    return
  }
  const txt = dt.getData('text/plain')
  if (txt && !e.defaultPrevented) {
    const p = parseCurl(txt)
    if (p) { e.preventDefault(); const t = tabs.openNew(); applyCurlToDraft(t.draft!, p); tabs.touch(t.id) }
  }
}
function openRunnerWithData(name: string, text: string) {
  const cid = tree.metas[0]?.id
  if (!cid) return
  const t = tabs.open('runner', cid, 'Runner: ' + tree.cols[cid].info.name, { permanent: true })
  t.state ??= {}
  const rows = /\.json$/i.test(name) ? JSON.parse(text) : text.split(/\r?\n/).filter(l => l.trim()).slice(1).map(l => l.split(','))
  t.state.data = { name, rows }
  tabs.touch(t.id)
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = next
  try { localStorage.setItem('apiRunnerTheme', next) } catch { /* ixtiyoriy */ }
}
</script>

<template>
  <div class="app" data-testid="app" :class="{ 'dropzone-active': dropping }" @dragover="onWindowDragOver" @dragleave="dropping = false" @drop="onWindowDrop" v-if="ready">
    <Sidebar />
    <div class="main">
      <div style="display:flex;align-items:stretch"><div style="flex:1;min-width:0"><TabBar /></div><button class="ghost" title="Tema" data-testid="theme" style="border-radius:0" @click="toggleTheme">◐</button></div>
      <template v-if="tabs.active">
        <RequestEditor v-if="tabs.active.kind === 'request' && tabs.active.draft" :key="tabs.active.id" :tab="tabs.active" />
        <EnvTab v-else-if="tabs.active.kind === 'environment'" :key="tabs.active.id" :tab="tabs.active" />
        <RunnerTab v-else-if="tabs.active.kind === 'runner'" :key="tabs.active.id" :tab="tabs.active" />
        <CollectionTab v-else-if="tabs.active.kind === 'collection'" :key="tabs.active.id" :tab="tabs.active" />
      </template>
      <div v-else class="empty" data-testid="no-tabs">
        <p>Tab ochiq emas</p><button class="primary" @click="tabs.openNew()">Yangi so'rov</button>
      </div>
    </div>
    <div class="version" data-testid="version">v{{ ws.version }}</div>

    <div v-if="closeDialog" class="overlay"><div class="dialog" data-testid="close-dialog">
      <p>{{ closeDialog.title }}</p>
      <div class="btns">
        <button data-testid="dlg-cancel" @click="closeDialog.resolve('cancel')">Bekor qilish</button>
        <button data-testid="dlg-discard" @click="closeDialog.resolve('discard')">Saqlamaslik</button>
        <button class="primary" data-testid="dlg-save" @click="closeDialog.resolve('save')">Saqlash</button>
      </div></div></div>
    <div v-if="confirmDialog" class="overlay"><div class="dialog" data-testid="confirm-dialog">
      <p>{{ confirmDialog.msg }}</p>
      <div class="btns"><button @click="confirmDialog.resolve(false)">Bekor qilish</button><button class="primary" data-testid="confirm-ok" @click="confirmDialog.resolve(true)">{{ confirmDialog.ok }}</button></div></div></div>
    <div v-if="saveAs" class="overlay"><div class="dialog" data-testid="saveas-dialog">
      <b>So'rovni saqlash</b>
      <p><input v-model="saveAs.name" style="width:100%" data-testid="saveas-name" @keydown.enter="confirmSaveAs"></p>
      <p><select v-model="saveAs.target" style="width:100%" data-testid="saveas-target"><option v-for="o in saveTargets" :key="o.key" :value="o.key">{{ o.label }}</option></select></p>
      <div class="btns"><button @click="saveAs.resolve(false); saveAs = null">Bekor qilish</button><button class="primary" data-testid="saveas-ok" @click="confirmSaveAs">Saqlash</button></div></div></div>
    <div v-if="toast" class="toast" data-testid="toast">{{ toast.msg }}</div>
  </div>
  <div v-else class="empty">Yuklanmoqda…</div>
</template>
