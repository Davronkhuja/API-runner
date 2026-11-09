<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useTabs, type Tab } from './stores/tabs'
import { useTree } from './stores/tree'
import { useWorkspace } from './stores/workspace'
import { useHistory } from './stores/history'
import { put, get, keepalivePut } from './api/client'
import { askClose, closeDialog, confirmDialog, findOpen, importOpen, toast, trashOpen } from './lib/ui'
import { suggestName } from './lib/rename'
import { clamp, drag } from './lib/resize'
import { createRequestIn, saveAsHandler, saveTab, sendTab, openRequest } from './lib/actions'
import Sidebar from './components/Sidebar.vue'
import TabBar from './components/TabBar.vue'
import RequestEditor from './components/RequestEditor.vue'
import EnvTab from './components/EnvTab.vue'
import RunnerTab from './components/RunnerTab.vue'
import RunGuard from './components/RunGuard.vue'
import ExampleTab from './components/ExampleTab.vue'
import RestartOverlay from './components/RestartOverlay.vue'
import FindReplaceDialog from './components/FindReplaceDialog.vue'
import TrashDialog from './components/TrashDialog.vue'
import VarPopup from './components/VarPopup.vue'
import SetVarPopover from './components/SetVarPopover.vue'
import Dialog from './components/Dialog.vue'
import ImportDialog from './components/ImportDialog.vue'
import CollectionTab from './components/CollectionTab.vue'
import SettingsTab from './components/SettingsTab.vue'
import CookiesTab from './components/CookiesTab.vue'
import { post as apiPost } from './api/client'
import { readLocalStorage, defaultNotice } from './lib/migrate'
import { activity, cmdkOpen, showToast } from './lib/ui'
import AppHeader from './components/AppHeader.vue'
import IconRail from './components/IconRail.vue'
import StatusBar from './components/StatusBar.vue'
import ConsolePanel from './components/ConsolePanel.vue'
import Welcome from './components/Welcome.vue'
import Icon from './components/Icon.vue'
import CmdK from './components/CmdK.vue'
import { parseCurl, applyCurlToDraft } from './lib/curl'
import { parseDataFile, isDataFile } from './lib/datafile'
import HistoryDrawer from './components/HistoryDrawer.vue'

const tabs = useTabs(), tree = useTree(), ws = useWorkspace(), hist = useHistory()
// Brauzer tab sarlavhasi: davom etayotgan ish bo'lsa "● Runner 12/18 — API Runner"
const busyTitle = computed(() => {
  const sending = tabs.tabs.filter(t => t.response?.loading).length
  const parts = [...Object.values(activity), ...(sending ? ['Yuborilmoqda'] : [])]
  return parts.length ? `● ${parts[0]}${parts.length > 1 ? ` (+${parts.length - 1})` : ''} — API Runner` : 'API Runner'
})
watch(busyTitle, t => { document.title = t }, { immediate: true })
const ready = ref(false)
const saveAs = ref<{ tab: Tab; name: string; target: string; resolve: (ok: boolean) => void } | null>(null)
const dropping = ref(false)
const histOpen = ref(false)
function openHist() { hist.load(); histOpen.value = true }
const migrationWarning = ref('')
const sbHidden = ref(false)
const sbWidth = ref(284)
try { sbHidden.value = localStorage.getItem('apiRunnerSbHidden') === '1'; sbWidth.value = Number(localStorage.getItem('apiRunnerSbWidth')) || 284 } catch { /* ixtiyoriy */ }
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
// Yon panel kengligi: 180..min(420, oyna yarmi); oyna o'zgarganda clamp qayta hisoblanadi
const sbMax = () => Math.max(180, Math.min(420, Math.floor(window.innerWidth / 2)))
const sbClamp = (w: number) => clamp(w, 180, sbMax())
const saveSb = () => { try { localStorage.setItem('apiRunnerSbWidth', String(sbWidth.value)) } catch { /* ixtiyoriy */ } }
function startResize(e: PointerEvent) { const w0 = sbWidth.value; drag(e, 'x', d => { sbWidth.value = sbClamp(w0 + d) }, saveSb) }
function sbNudge(d: number) { sbWidth.value = sbClamp(sbWidth.value + d); saveSb() }
function sbReset() { sbWidth.value = sbClamp(284); saveSb() }
const onWinResize = () => { sbWidth.value = sbClamp(sbWidth.value) }
onMounted(() => { onWinResize(); window.addEventListener('resize', onWinResize) })
onBeforeUnmount(() => window.removeEventListener('resize', onWinResize))
const saveTargets = computed(() => tree.rows.filter(r => r.isCollection || r.folder).map(r => ({ key: `${r.collectionId}:${r.id}`, label: '　'.repeat(r.depth) + r.name })))

saveAsHandler.fn = tab => new Promise(resolve => {
  const first = saveTargets.value[0]?.key ?? ''
  const d = tab.draft!, urlLike = /^(https?:\/\/|\{\{)/i.test(d.name.trim())
  const guess = d.url.trim() ? suggestName(d.url) : d.name           // nomi berilmagan/URL bo'lsa — host'siz path
  saveAs.value = { tab, name: urlLike || d.name === "Yangi so'rov" ? guess : d.name, target: first, resolve }
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
  else if (mod && k === 'k') { e.preventDefault(); cmdkOpen.value = !cmdkOpen.value }
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
/** Fayl: CSV / massiv-JSON — Runner data fayli; qolgani Postman/OpenAPI import. */
async function handleFile(file: File) {
  const text = await file.text()
  if (isDataFile(file) && (!/\.json$/i.test(file.name) || text.trimStart().startsWith('['))) return openRunnerWithData(file.name, text)
  try {
    const r = await apiPost('/api/import', { content: text })
    await tree.load()
    showToast(`Import qilindi: ${r.name}`, 'success')
  } catch (err: any) { showToast(err.message, 'error') }
}
const clickImport = () => { importOpen.value = true }
async function onWindowDrop(e: DragEvent) {
  dropping.value = false
  const dt = e.dataTransfer
  if (!dt) return
  const file = dt.files?.[0]
  if (file) { e.preventDefault(); return handleFile(file) }
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

</script>

<template>
  <div v-if="ready && migrationWarning" class="toast" style="position:static;background:var(--err);color:var(--on-accent);border-radius:0;padding:8px 14px" data-testid="migration-warning" role="alert">⚠ {{ migrationWarning }}</div>
  <div class="app" data-testid="app" :class="{ 'dropzone-active': dropping }" @dragover="onWindowDragOver" @dragleave="dropping = false" @drop="onWindowDrop" v-if="ready">
    <AppHeader />
    <div class="shell">
      <IconRail />
      <div v-show="!sbHidden" class="sb-wrap" :style="{ width: sbWidth + 'px' }" data-testid="sb-wrap"><Sidebar @open-history="openHist" /><div class="sb-resizer" data-testid="sb-resizer" role="separator" aria-orientation="vertical" aria-label="Panel kengligi" tabindex="0" :aria-valuenow="sbWidth" @pointerdown="startResize" @dblclick="sbReset" @keydown.left.prevent="sbNudge(-16)" @keydown.right.prevent="sbNudge(16)" /></div>
      <div class="main">
        <div style="display:flex;align-items:stretch">
          <button class="ib" aria-label="Yon panelni yashirish/ko'rsatish" :aria-pressed="!sbHidden" title="Yon panel" data-testid="sb-toggle" style="margin:3px 4px;flex-shrink:0" @click="toggleSidebar"><Icon name="sidebar" :size="16" /></button>
          <div style="flex:1;min-width:0"><TabBar /></div>
        </div>
        <template v-if="tabs.active">
          <RequestEditor v-if="tabs.active.kind === 'request' && tabs.active.draft" :key="tabs.active.id" :tab="tabs.active" />
          <EnvTab v-else-if="tabs.active.kind === 'environment'" :key="tabs.active.id" :tab="tabs.active" />
          <RunnerTab v-else-if="tabs.active.kind === 'runner'" :key="tabs.active.id" :tab="tabs.active" />
          <SettingsTab v-else-if="tabs.active.kind === 'settings'" :key="tabs.active.id" />
          <CookiesTab v-else-if="tabs.active.kind === 'cookies'" :key="tabs.active.id" />
          <ExampleTab v-else-if="tabs.active.kind === 'example'" :key="tabs.active.id" :tab="tabs.active" />
          <CollectionTab v-else-if="tabs.active.kind === 'collection'" :key="tabs.active.id" :tab="tabs.active" />
        </template>
        <Welcome v-else @import="clickImport" @import-file="handleFile" />
      </div>
    </div>
    <ConsolePanel />
    <StatusBar />

    <Dialog v-if="closeDialog" title="Saqlanmagan o'zgarishlar" testid="close-dialog" width="440px" @close="closeDialog.resolve('cancel')">
      <p style="margin:0">{{ closeDialog.title }}</p>
      <template #footer>
        <button data-testid="dlg-cancel" @click="closeDialog.resolve('cancel')">Bekor qilish</button>
        <button data-testid="dlg-discard" @click="closeDialog.resolve('discard')">Saqlamaslik</button>
        <button class="primary" data-testid="dlg-save" data-autofocus @click="closeDialog.resolve('save')">Saqlash</button>
      </template>
    </Dialog>
    <Dialog v-if="confirmDialog" title="Tasdiqlash" testid="confirm-dialog" width="460px" top @close="confirmDialog.resolve(false)">
      <p style="margin:0;line-height:1.5">{{ confirmDialog.msg }}</p>
      <template #footer>
        <button @click="confirmDialog.resolve(false)">Bekor qilish</button>
        <button class="primary" data-testid="confirm-ok" data-autofocus @click="confirmDialog.resolve(true)">{{ confirmDialog.ok }}</button>
      </template>
    </Dialog>
    <RunGuard />
    <RestartOverlay />
    <VarPopup />
    <SetVarPopover />
    <ImportDialog v-if="importOpen" @close="importOpen = false" />
    <FindReplaceDialog v-if="findOpen" @close="findOpen = false" />
    <TrashDialog v-if="trashOpen" @close="trashOpen = false" />
    <Dialog v-if="saveAs" title="So'rovni saqlash" testid="saveas-dialog" width="460px" @close="saveAs.resolve(false); saveAs = null">
      <label class="dlg-field"><span>Nomi</span><input v-model="saveAs.name" style="width:100%" data-testid="saveas-name" data-autofocus @keydown.enter="confirmSaveAs"></label>
      <label class="dlg-field"><span>Qayerga</span><select v-model="saveAs.target" style="width:100%" data-testid="saveas-target"><option v-for="o in saveTargets" :key="o.key" :value="o.key">{{ o.label }}</option></select></label>
      <template #footer>
        <button @click="saveAs.resolve(false); saveAs = null">Bekor qilish</button>
        <button class="primary" data-testid="saveas-ok" @click="confirmSaveAs">Saqlash</button>
      </template>
    </Dialog>
    <div v-if="toast" class="toast" data-testid="toast">{{ toast.msg }}</div>
  </div>
  <div v-else class="empty">Yuklanmoqda…</div>
  <HistoryDrawer v-model="histOpen" />
  <CmdK />
</template>
