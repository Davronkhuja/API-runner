<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useTabs, type Tab } from './stores/tabs'
import { useTree } from './stores/tree'
import { useWorkspace } from './stores/workspace'
import { useHistory } from './stores/history'
import { put, get, keepalivePut } from './api/client'
import { askClose, closeDialog, confirmDialog, toast } from './lib/ui'
import { createRequestIn, saveAsHandler, saveTab, sendTab, openRequest } from './lib/actions'
import Sidebar from './components/Sidebar.vue'
import TabBar from './components/TabBar.vue'
import RequestEditor from './components/RequestEditor.vue'
import EnvTab from './components/EnvTab.vue'
import RunnerTab from './components/RunnerTab.vue'
import CollectionTab from './components/CollectionTab.vue'
import SettingsTab from './components/SettingsTab.vue'
import { post as apiPost } from './api/client'
import { parseCurl, applyCurlToDraft } from './lib/curl'
import { parseDataFile, isDataFile } from './lib/datafile'
import { showToast } from './lib/ui'

const tabs = useTabs(), tree = useTree(), ws = useWorkspace(), hist = useHistory()
const ready = ref(false)
const saveAs = ref<{ tab: Tab; name: string; target: string; resolve: (ok: boolean) => void } | null>(null)
const dropping = ref(false)
const importInput = ref<HTMLInputElement>()
const migrationWarning = ref('')
const sbHidden = ref(false)
const sbWidth = ref(280)
try { sbHidden.value = localStorage.getItem('apiRunnerSbHidden') === '1'; sbWidth.value = Number(localStorage.getItem('apiRunnerSbWidth')) || 280 } catch { /* ixtiyoriy */ }
const LS_KEYS = ['apiRunnerEnvs', 'apiRunnerActiveEnvId', 'apiRunnerEnvVars', 'apiRunnerHistory', 'apiRunnerRunHistory', 'apiRunnerUrlHistory']
/** localStorage'dan faqat O'QIYDI — hech narsa o'chirilmaydi. */
function readLocalStorage(): Record<string, string> {
  const data: Record<string, string> = {}
  try { LS_KEYS.forEach(k => { const v = localStorage.getItem(k); if (v != null) data[k] = v }) } catch { /* ixtiyoriy */ }
  return data
}
async function defaultNotice() {
  const st = await get('/api/status').catch(() => null)
  if (st?.meta?.legacy_default_migrated && !st.meta.legacy_default_notified) {
    showToast("Eski Default o'zgaruvchilar Globals'ga ko'chirildi", 'info', 8000)
    await put('/api/workspace/meta', { legacy_default_notified: true }).catch(() => {})
  }
}
async function startupChecks() {
  const st = await get('/api/status').catch(() => null)
  if (st?.migration?.status === 'rolled_back') migrationWarning.value = st.migration.message || 'Migratsiya bekor qilindi va zaxiradan tiklandi'
  // birinchi ochilishda eski brauzer ma'lumotini bir marta serverga ko'chirish (idempotent, localStorage tegilmaydi)
  if (st && !st.meta?.localstorage_imported) {
    const data = readLocalStorage()
    if (Object.keys(data).length) {
      try { await apiPost('/api/import/localstorage', { data }); await Promise.all([ws.load(), hist.load()]) } catch { /* qo'lda ⇪ bilan qayta urinish mumkin */ }
    }
  }
  await defaultNotice()
}
function toggleSidebar() { sbHidden.value = !sbHidden.value; try { localStorage.setItem('apiRunnerSbHidden', sbHidden.value ? '1' : '0') } catch { /* ixtiyoriy */ } }
function startResize(e: MouseEvent) {
  const x0 = e.clientX, w0 = sbWidth.value
  const move = (ev: MouseEvent) => { sbWidth.value = Math.max(180, Math.min(420, w0 + ev.clientX - x0)) }
  const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); try { localStorage.setItem('apiRunnerSbWidth', String(sbWidth.value)) } catch { /* ixtiyoriy */ } }
  window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
}
async function onImportFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return
  try { const r = await apiPost('/api/import', { content: await f.text() }); await tree.load(); showToast(`Import qilindi: ${r.name}`, 'success') } catch (err: any) { showToast(err.message, 'error') }
  ;(e.target as HTMLInputElement).value = ''
}
async function importLocalStorage() {
  const data = readLocalStorage()
  if (!Object.keys(data).length) return showToast("localStorage'da ko'chiriladigan ma'lumot yo'q", 'warn')
  try {
    const r = await apiPost('/api/import/localstorage', { data })
    await Promise.all([ws.load(), hist.load()])
    showToast(`Ko'chirildi: ${r.stats.environments} env, ${r.stats.history + r.stats.run_history + r.stats.url_history} tarix yozuvi`, 'success')
    await defaultNotice()
  } catch (err: any) { showToast('Import xatosi: ' + err.message, 'error') }
}
async function exportLegacy() {
  const r = await fetch('/api/export/legacy', { headers: { 'X-Session-Token': window.__API_TOKEN__ ?? '' } })
  const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = 'saved_requests.json'; a.click()
}

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

// UI holati (tree ochiq/yopiq) — server tomonda (PUT kalitlar bo'yicha birlashtiriladi); tablar tabs store ichida
let uiTimer: ReturnType<typeof setTimeout> | null = null
function persistTree() { if (uiTimer) clearTimeout(uiTimer); uiTimer = setTimeout(flushTree, 300) }
function flushTree() { if (uiTimer) { clearTimeout(uiTimer); uiTimer = null; put('/api/ui-state', { expanded: tree.expandedOverride }).catch(() => {}) } }
function flushTreeOnUnload() { if (uiTimer) { clearTimeout(uiTimer); uiTimer = null; keepalivePut('/api/ui-state', { expanded: tree.expandedOverride }) } }

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
  window.addEventListener('pagehide', flushTreeOnUnload)
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flushTreeOnUnload() })
  await Promise.all([tree.load(), ws.load(), hist.load()])
  const st = await get('/api/ui-state').catch(() => ({}))
  if (st.expanded) tree.expandedOverride = st.expanded
  await tabs.restore()
  await startupChecks()
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
    if (isDataFile(file) && (!/\.json$/i.test(file.name) || text.trimStart().startsWith('['))) return openRunnerWithData(file.name, text)
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
  try { t.state.data = { name, rows: parseDataFile(name, text) } } catch (err: any) { showToast('Fayl o\'qilmadi: ' + err.message, 'error') }
  tabs.touch(t.id)
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = next
  try { localStorage.setItem('apiRunnerTheme', next) } catch { /* ixtiyoriy */ }
}
</script>

<template>
  <div v-if="ready && migrationWarning" class="toast" style="position:static;background:var(--err);color:#fff;border-radius:0;padding:8px 14px" data-testid="migration-warning">⚠ {{ migrationWarning }}</div>
  <div class="app" data-testid="app" :class="{ 'dropzone-active': dropping }" @dragover="onWindowDragOver" @dragleave="dropping = false" @drop="onWindowDrop" v-if="ready">
    <div v-show="!sbHidden" :style="{ width: sbWidth + 'px' }" style="display:flex;position:relative" data-testid="sb-wrap"><Sidebar style="width:100%" /><div class="sb-resizer" data-testid="sb-resizer" @mousedown="startResize" /></div>
    <div class="main">
      <div style="display:flex;align-items:stretch">
        <button class="ghost" style="border-radius:0" data-testid="sb-toggle" title="Sidebar" @click="toggleSidebar">☰</button>
        <div style="flex:1;min-width:0"><TabBar /></div>
        <select :value="ws.activeEnvId ?? ''" data-testid="env-select" style="max-width:160px;margin:3px" @change="ws.setActive(($event.target as HTMLSelectElement).value || null)">
          <option value="">Muhit yo'q</option><option v-for="e in ws.environments" :key="e.id" :value="e.id">{{ e.name }}</option>
        </select>
        <button class="ghost" style="border-radius:0" data-testid="import-btn" title="Postman/OpenAPI import" @click="importInput?.click()">⤒</button>
        <input ref="importInput" type="file" accept=".json" hidden data-testid="import-file" @change="onImportFile">
        <button class="ghost" style="border-radius:0" data-testid="ls-import" title="Brauzer (localStorage) ma'lumotlarini serverga ko'chirish" @click="importLocalStorage">⇪</button>
        <button class="ghost" style="border-radius:0" data-testid="export-legacy" title="saved_requests.json formatiga eksport (orqaga qaytish)" @click="exportLegacy">⤓</button>
        <button class="ghost" style="border-radius:0" data-testid="settings-btn" title="Sozlamalar → Zaxiralar" @click="tabs.open('settings', 'settings', 'Sozlamalar', { permanent: true })">⚙</button>
        <button class="ghost" title="Tema" data-testid="theme" style="border-radius:0" @click="toggleTheme">◐</button>
      </div>
      <template v-if="tabs.active">
        <RequestEditor v-if="tabs.active.kind === 'request' && tabs.active.draft" :key="tabs.active.id" :tab="tabs.active" />
        <EnvTab v-else-if="tabs.active.kind === 'environment'" :key="tabs.active.id" :tab="tabs.active" />
        <RunnerTab v-else-if="tabs.active.kind === 'runner'" :key="tabs.active.id" :tab="tabs.active" />
        <SettingsTab v-else-if="tabs.active.kind === 'settings'" :key="tabs.active.id" />
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
