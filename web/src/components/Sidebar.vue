<script setup lang="ts">
import { kindLabel } from '../lib/envkind'
import Dialog from './Dialog.vue'
import HistoryList from './HistoryList.vue'
import NameCleanDialog from './NameCleanDialog.vue'
import { dismissOffer, urlNamedItems } from '../lib/nameclean'
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { useTree, rowKey, dropPositionFor, type Row } from '../stores/tree'
import { useTabs } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { openFromHistory } from '../lib/history'
import { openRequest } from '../lib/actions'
import { askConfirm, showToast, sidePanel } from '../lib/ui'
import Icon from './Icon.vue'
import { authName, hasRealAuth, openNodeTab } from '../lib/nodes'
import { nameWarning, renameNode, suggestName, validateName } from '../lib/rename'
import { exId, ensureExampleIds, openExample } from '../lib/examples'
import { isFolder, type DropPosition, type RequestItem, type TreeItem } from '../types/model'
import { draftFromItem } from '../lib/draft'

const tree = useTree(), tabs = useTabs(), ws = useWorkspace(), hist = useHistory()
defineEmits<{ 'open-history': [] }>()
const panel = sidePanel
const body = ref<HTMLElement>()
const menu = ref<{ x: number; y: number; row: Row } | null>(null)
const moveDlg = ref<{ keys: string[] } | null>(null)
const moveTarget = ref('')
const renaming = ref<string | null>(null)
const renameVal = ref('')

// ── Drag & drop ──
const dragKeys = ref<string[]>([])
const drop = ref<{ key: string; pos: DropPosition } | null>(null)
let hoverTimer: ReturnType<typeof setTimeout> | null = null
let scrollRaf = 0
let scrollDir = 0
const keyOf = (r: Row) => rowKey(r.collectionId, r.id)

function onDragStart(e: DragEvent, r: Row) {
  if (r.isCollection) { e.preventDefault(); return }
  const k = keyOf(r)
  dragKeys.value = tree.dragSet(k)
  e.dataTransfer!.effectAllowed = 'copyMove'
  e.dataTransfer!.setData('text/plain', dragKeys.value.join(','))
}
function onDragOver(e: DragEvent, r: Row) {
  if (!dragKeys.value.length) return
  const el = e.currentTarget as HTMLElement
  const pos = r.isCollection ? 'inside' : dropPositionFor(e.clientY - el.getBoundingClientRect().top, el.offsetHeight, r.folder)
  const k = keyOf(r)
  if (!tree.canDrop(dragKeys.value, k, pos)) { drop.value = null; return }
  e.preventDefault()
  e.dataTransfer!.dropEffect = e.altKey ? 'copy' : 'move'
  if (drop.value?.key !== k || drop.value.pos !== pos) {
    drop.value = { key: k, pos }
    if (hoverTimer) clearTimeout(hoverTimer)
    // papka ustida biroz ushlab turilsa — avtomatik ochiladi
    if (r.folder && !r.expanded && pos === 'inside') hoverTimer = setTimeout(() => tree.setExpanded(k, true), 600)
  }
}
async function onDrop(e: DragEvent) {
  e.preventDefault()
  const d = drop.value
  stopScroll()
  if (!d || !dragKeys.value.length) return reset()
  const keys = dragKeys.value, copy = e.altKey
  reset()
  try { await tree.move(keys, d.key, d.pos, copy) } catch (err: any) { showToast(err.message, 'error') }
}
function reset() { dragKeys.value = []; drop.value = null; if (hoverTimer) clearTimeout(hoverTimer); stopScroll() }
// uzun ro'yxatda chetga yaqinlashganda avtomatik scroll
function onContainerDragOver(e: DragEvent) {
  if (!dragKeys.value.length || !body.value) return
  const rect = body.value.getBoundingClientRect(), edge = 36
  scrollDir = e.clientY < rect.top + edge ? -1 : e.clientY > rect.bottom - edge ? 1 : 0
  if (scrollDir && !scrollRaf) { const step = () => { if (!scrollDir) { scrollRaf = 0; return } body.value!.scrollTop += scrollDir * 12; scrollRaf = requestAnimationFrame(step) }; scrollRaf = requestAnimationFrame(step) }
}
function stopScroll() { scrollDir = 0; if (scrollRaf) cancelAnimationFrame(scrollRaf); scrollRaf = 0 }
onBeforeUnmount(stopScroll)

// ── Fayl tashlash (Postman/OpenAPI/CSV/cURL) — import Bosqich 5 da; hozir App.vue ushlaydi ──

// ── Bosish ──
let clickTimer: ReturnType<typeof setTimeout> | null = null
function onClick(e: MouseEvent, r: Row) {
  const k = keyOf(r)
  if (e.shiftKey || e.metaKey || e.ctrlKey) { tree.select(k, { shift: e.shiftKey, meta: e.metaKey || e.ctrlKey }); return }
  if (r.isCollection || r.folder) {                                   // Postman kabi: qator bosilsa tab (preview) ochiladi va papka ochiladi/yopiladi
    tree.toggle(k, r.item); tree.select(k)
    openNodeTab(r.collectionId, r.isCollection ? null : r.id, 'overview', true)
    return
  }
  tree.select(k)
  openRequest(r.collectionId, r.id, false)
}
function onDbl(r: Row) {
  if (r.isCollection) openNodeTab(r.collectionId, null, 'overview')
  else if (r.folder) openNodeTab(r.collectionId, r.id, 'overview')
  else if (!r.folder) openRequest(r.collectionId, r.id, true)
}
void clickTimer

// ── Example'lar ──
function onExample(r: Row, permanent: boolean) { tree.select(keyOf(r)); openExample(r.collectionId, r.parentId!, r.exampleId ?? '', r.name, permanent) }
async function dupExample(r: Row) {
  const list = await ensureExampleIds(r.collectionId, r.parentId!)
  const i = list.findIndex(e => (r.exampleId ? e.id === r.exampleId : e.name === r.name))
  if (i < 0) return
  const copy = { ...JSON.parse(JSON.stringify(list[i])), id: exId(), name: list[i].name + ' Copy' }
  await tree.updateItem(r.collectionId, r.parentId!, { response: [...list.slice(0, i + 1), copy, ...list.slice(i + 1)] })
}
async function delExample(r: Row) {
  if (!(await askConfirm(`«${r.name}» namunasi o'chirilsinmi?`, "O'chirish"))) return
  const list = await ensureExampleIds(r.collectionId, r.parentId!)
  const gone = list.find(e => (r.exampleId ? e.id === r.exampleId : e.name === r.name))
  await tree.updateItem(r.collectionId, r.parentId!, { response: list.filter(e => e !== gone) })
  if (gone) tabs.dropRef(`${r.collectionId}:${r.parentId}:${gone.id}`)
}

// ── Kontekst menyu ──
function ctx(e: MouseEvent, r: Row) { menu.value = { x: e.clientX, y: e.clientY, row: r }; if (!tree.selection.includes(keyOf(r))) tree.select(keyOf(r)) }
async function menuAct(a: string) {
  const r = menu.value!.row; menu.value = null
  if (a === 'ex-open') onExample(r, true)
  else if (a === 'ex-dup') await dupExample(r)
  else if (a === 'ex-delete') await delExample(r)
  else if (a === 'rename') startRename(r)
  else if (a === 'runner') tabs.open('runner', r.isCollection ? r.collectionId : `${r.collectionId}:${r.id}`, 'Runner: ' + r.name, { permanent: true })
  else if (a === 'open') openNodeTab(r.collectionId, null, 'overview')
  else if (a === 'settings') openNodeTab(r.collectionId, r.id, 'overview')
  else if (a === 'newreq') { const t = tabs.openNew(); t.draft!.name = 'Yangi so\'rov' }
  else if (a === 'newfolder') { await tree.addItem(r.collectionId, { name: 'Yangi papka', item: [] }, r.isCollection ? null : r.id) }
  else if (a === 'move') { moveDlg.value = { keys: tree.selection.length ? [...tree.selection] : [keyOf(r)] }; moveTarget.value = '' }
  else if (a === 'dup') await duplicate(r)
  else if (a === 'delete') {
    const keys = tree.selection.includes(keyOf(r)) ? [...tree.selection] : [keyOf(r)]
    if (!(await askConfirm(`${keys.length} ta element o'chirilsinmi?`, 'O\'chirish'))) return
    for (const k of keys) { const [c, i] = k.split(':'); await tree.removeItem(c, i); tabs.dropRef(k) }
    tree.clearSelection()
  }
}
async function duplicate(r: Row) {
  const newId = await tree.duplicate(r.collectionId, r.id)
  await nextTick()
  const nr = tree.rows.find(x => x.collectionId === r.collectionId && x.id === newId)
  if (nr) { tree.select(keyOf(nr)); startRename(nr) }       // yangi element darhol rename rejimida ("... Copy" belgilangan)
}
let renameDone = false                    // Enter/Esc dan keyin kelgan blur ikkinchi marta ishlamasin
const vFocusSelect = { mounted(el: HTMLInputElement) { nextTick(() => { el.focus(); el.select() }) } }   // dinamik elementda autofocus ishonchsiz
function startRename(r: Row) { renameDone = false; renaming.value = keyOf(r); renameVal.value = suggestName(r.name) }
const renameWarn = (r: Row) => nameWarning(r.collectionId, r.isCollection ? null : r.id, renameVal.value)
async function commitRename(r: Row, mode: 'enter' | 'blur' = 'enter') {
  if (renameDone) return
  const id = r.isCollection ? null : r.id
  const err = validateName(r.collectionId, id, renameVal.value)
  if (err) {
    showToast(err, 'warn')
    if (mode === 'enter') return                        // tahrirda qoladi
    renameDone = true; renaming.value = null; return    // blur: bekor
  }
  renameDone = true; renaming.value = null
  if (renameVal.value.trim() !== r.name) await renameNode(r.collectionId, id, renameVal.value)
}
function cancelRename() { renameDone = true; renaming.value = null }
// "Ko'chirish..." — klaviatura/accessibility uchun DnD ning muqobili
const moveOptions = computed(() => tree.rows.filter(r => r.isCollection || r.folder).map(r => ({ key: keyOf(r), label: '　'.repeat(r.depth) + r.name })))
async function confirmMove() {
  const d = moveDlg.value!; moveDlg.value = null
  if (!moveTarget.value) return
  try { await tree.move(d.keys, moveTarget.value, 'inside') } catch (e: any) { showToast(e.message, 'error') }
}
/** Tugunning o'z auth'i (meros emas, "Auth yo'q" emas) — daraxtda qulf belgisi uchun. */
const ownAuth = (r: Row) => { const pm = r.isCollection ? tree.cols[r.collectionId]?.auth : r.folder ? (r.item as any)?.auth : (r.item as any)?.request?.auth; return hasRealAuth(pm as any) ? pm : null }
const reqCount = (it: TreeItem | null): number => (it && isFolder(it) ? it.item.reduce((n, c) => n + (isFolder(c) ? reqCount(c) : 1), 0) : 0)
const titles: Record<string, string> = { collections: 'Kolleksiyalar', environments: 'Muhitlar', history: 'Tarix', runner: 'Runner' }
function openRunner() {
  const sel = tree.selection[0]?.split(':')[0]
  const m = tree.metas.find(x => x.id === sel) ?? tree.metas[0]
  if (!m) return showToast('Avval collection yarating', 'warn')
  tabs.open('runner', m.id, 'Runner: ' + m.name, { permanent: true })
}
/** Klaviatura: ↑↓ qatorlar orasida, ←/→ papkani yopish/ochish, Enter ochish, F2 — nomini o'zgartirish. */
function onKey(e: KeyboardEvent, r: Row) {
  if (r.isExample) return
  const rows = [...(body.value?.querySelectorAll<HTMLElement>('[data-testid=tree-row]') ?? [])]
  const i = rows.indexOf(e.currentTarget as HTMLElement)
  if (e.key === 'ArrowDown') { e.preventDefault(); rows[i + 1]?.focus() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); rows[i - 1]?.focus() }
  else if (e.key === 'ArrowRight' && r.folder && !r.expanded) { e.preventDefault(); tree.toggle(keyOf(r), r.item) }
  else if (e.key === 'ArrowLeft' && r.folder && r.expanded) { e.preventDefault(); tree.toggle(keyOf(r), r.item) }
  else if (e.key === 'Enter' || e.key === ' ') { if ((e.target as HTMLElement).tagName === 'INPUT') return; e.preventDefault(); onClick(new MouseEvent('click'), r); if (e.key === 'Enter' && !r.folder) onDbl(r) }
  else if (e.key === 'F2') { e.preventDefault(); startRename(r) }
  else if (e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) { e.preventDefault(); const b = (e.currentTarget as HTMLElement).getBoundingClientRect(); ctx(new MouseEvent('contextmenu', { clientX: b.left + 40, clientY: b.bottom }), r) }
}
async function newCollection() { await tree.createCollection('Yangi collection') }

// ── Environments / History ──
const loadHistory = openFromHistory
const openEnv = (id: string, name: string) => tabs.open('environment', id, name, { permanent: true })
async function delEnv(id: string, name: string) { if (await askConfirm(`'${name}' o'chirilsinmi?`, "O'chirish")) await ws.deleteEnv(id) }
const cleanOpen = ref(false)
const cleanCount = computed(() => urlNamedItems().length)
async function newEnv() { const id = await ws.createEnv('Yangi muhit'); openEnv(id, 'Yangi muhit') }
</script>

<template>
  <aside class="sidebar" data-testid="sidebar" :aria-label="titles[panel]">
    <div class="sb-title">
      <b data-testid="sb-title">{{ titles[panel] }}</b>
      <div style="display:flex;gap:2px">
        <template v-if="panel === 'collections'">
          <button class="ib" aria-label="Yangi so'rov" title="Yangi so'rov" data-testid="sb-new-request" @click="tabs.openNew()"><Icon name="plus" :size="16" /></button>
          <button class="ib" aria-label="Yangi collection" title="Yangi collection" data-testid="new-collection" @click="newCollection"><Icon name="folder-plus" :size="16" /></button>
        </template>
        <template v-else-if="panel === 'environments'"><button class="ib" aria-label="Yangi muhit" title="Yangi muhit" data-testid="new-env" @click="newEnv"><Icon name="plus" :size="16" /></button></template>
        <template v-else-if="panel === 'history'">
          <button class="ib" aria-label="Kengaytirilgan tarix" title="Kengaytirilgan tarix" data-testid="history-btn" @click="$emit('open-history')"><Icon name="clock" :size="16" /></button>
          <button class="ib" aria-label="Tarixni tozalash" title="Tozalash" data-testid="history-clear" @click="hist.clear('request')"><Icon name="trash" :size="16" /></button>
        </template>
      </div>
    </div>

    <div v-if="panel === 'collections' && cleanCount && !ws.nameCleanDismissed" class="nameclean" data-testid="nameclean-offer" role="status">
      <span class="nc-text">{{ cleanCount }} ta so'rov nomi URL ko'rinishida.</span>
      <button class="linkbtn" data-testid="nameclean-open" @click="cleanOpen = true">Ko'rish va tozalash…</button>
      <button class="ib nc-x" aria-label="Taklifni yopish" title="Yopish" data-testid="nameclean-close" @click="dismissOffer()">×</button>
    </div>
    <NameCleanDialog v-if="cleanOpen" @close="cleanOpen = false" />

    <template v-if="panel === 'collections'">
      <div class="sb-search"><input v-model="tree.filter" placeholder="Filtr…" aria-label="Kolleksiyalarda qidirish" data-testid="sb-search"></div>
      <div class="sb-body" ref="body" data-testid="tree" role="tree" @dragover="onContainerDragOver" @dragend="reset" @drop="stopScroll">
        <div v-if="!tree.rows.length" class="empty">{{ tree.filter ? 'Hech narsa topilmadi' : 'Collection yo\'q. ＋ bosing.' }}</div>
        <template v-for="r in tree.rows" :key="rowKey(r.collectionId, r.id)">
        <div v-if="r.isExample" class="row ex-row" :class="{ sel: tree.selection.includes(keyOf(r)) }" data-testid="example-row" role="treeitem" tabindex="0" :aria-level="r.depth + 1" :data-name="r.name" :data-key="keyOf(r)"
             :style="{ paddingLeft: 8 + r.depth * 14 + 'px' }" @click="onExample(r, false)" @dblclick="onExample(r, true)" @contextmenu.prevent="ctx($event, r)" @keydown.enter.prevent="onExample(r, true)">
          <span class="ex-tag" aria-hidden="true">EX</span><span class="name">{{ r.name }}</span>
        </div>
        <div v-else class="row" :class="{ root: r.isCollection, sel: tree.selection.includes(rowKey(r.collectionId, r.id)), dragging: dragKeys.includes(rowKey(r.collectionId, r.id)),
                       'drop-inside': drop?.key === rowKey(r.collectionId, r.id) && drop.pos === 'inside',
                       'drop-before': drop?.key === rowKey(r.collectionId, r.id) && drop.pos === 'before',
                       'drop-after': drop?.key === rowKey(r.collectionId, r.id) && drop.pos === 'after' }"
             data-testid="tree-row" role="treeitem" tabindex="0" :aria-level="r.depth + 1" :aria-expanded="r.folder ? r.expanded : undefined" :aria-selected="tree.selection.includes(rowKey(r.collectionId, r.id))"
             :data-key="rowKey(r.collectionId, r.id)" :data-name="r.name" :data-kind="r.isCollection ? 'collection' : r.folder ? 'folder' : 'request'"
             :style="{ paddingLeft: 8 + r.depth * 14 + 'px' }" :draggable="!r.isCollection"
             @click="onClick($event, r)" @dblclick="onDbl(r)" @contextmenu.prevent="ctx($event, r)" @keydown="onKey($event, r)"
             @dragstart="onDragStart($event, r)" @dragover="onDragOver($event, r)" @drop="onDrop($event)">
          <span v-if="r.folder" class="ico" data-testid="row-chevron" :style="{ transform: r.expanded ? 'rotate(90deg)' : 'none' }" @click.stop="tree.toggle(keyOf(r), r.item)"><Icon name="chevron-right" :size="14" /></span>
          <span v-if="r.hasExamples" class="ico ex-chev" data-testid="ex-chevron" role="button" :aria-label="r.expanded ? 'Namunalarni yopish' : 'Namunalarni ochish'" :style="{ transform: r.expanded ? 'rotate(90deg)' : 'none' }" @click.stop="tree.setExpanded(keyOf(r), !r.expanded)"><Icon name="chevron-right" :size="12" /></span>
          <span v-if="r.isCollection" class="ico" style="width:18px;height:18px;border-radius:5px;background:var(--accent-weak);color:var(--accent-text);align-items:center;justify-content:center"><Icon name="layers" :size="12" /></span>
          <span v-else-if="r.folder" class="ico"><Icon name="folder" :size="15" /></span>
          <span v-else class="m" :class="'m-' + (r.item as any).request.method">{{ (r.item as any).request.method }}</span>
          <input v-if="renaming === rowKey(r.collectionId, r.id)" v-model="renameVal" v-focus-select aria-label="Yangi nom" style="flex:1;height:var(--ctl-xs);padding:0 6px" data-testid="rename-input"
                 @click.stop @keydown.stop @keydown.enter.prevent="commitRename(r, 'enter')" @keydown.esc.prevent="cancelRename" @blur="commitRename(r, 'blur')">
          <small v-if="renaming === rowKey(r.collectionId, r.id) && renameWarn(r)" class="name-warn name-warn-abs" data-testid="name-warn" role="status">{{ renameWarn(r) }}</small>
          <span v-else class="name" :style="{ fontWeight: r.folder ? 500 : 400 }">{{ r.name }}</span>
          <span v-if="ownAuth(r)" class="lock" data-testid="auth-lock" role="img" :aria-label="`O'z auth'i bor: ${authName(ownAuth(r))}`" :title="`Auth: ${authName(ownAuth(r))} (o'z auth'i)`"><Icon name="lock" :size="12" /></span>
          <span v-if="r.folder && !r.isCollection" class="cnt">{{ reqCount(r.item) }}</span>
        </div>
        </template>
      </div>
    </template>

    <div v-else-if="panel === 'environments'" class="sb-body" data-testid="env-list">
      <button class="row" style="height:44px" data-testid="globals-row" @click="tabs.open('environment', 'globals', 'Globals', { permanent: true })">
        <span class="ico"><Icon name="globe" :size="15" /></span><span class="name"><b style="font-weight:500;display:block">Globals</b><span class="muted" style="font-size:var(--fs-sm)">{{ ws.globals.length }} ta o'zgaruvchi</span></span>
      </button>
      <div v-for="e in ws.environments" :key="e.id" class="row" :class="{ sel: ws.activeEnvId === e.id }" style="height:44px" data-testid="env-row" @click="openEnv(e.id, e.name)">
        <span class="kind-dot" :class="e.kind ? 'kind-' + e.kind : ''" style="flex-shrink:0" :style="e.kind ? {} : { background: ws.activeEnvId === e.id ? 'var(--ok)' : 'var(--border-strong)' }" :data-kind="e.kind || undefined" aria-hidden="true" />
        <button class="row-main name" @click.stop="openEnv(e.id, e.name)"><b style="font-weight:500;display:block">{{ e.name }}</b><span class="muted" style="font-size:var(--fs-sm)">{{ e.values.length }} ta o'zgaruvchi{{ e.kind ? ' · ' + kindLabel(e.kind) : '' }}{{ ws.activeEnvId === e.id ? ' · faol' : '' }}</span></button>
        <button class="ib x" :aria-label="ws.activeEnvId === e.id ? 'Faolsizlantirish' : 'Faollashtirish'" :title="ws.activeEnvId === e.id ? 'Faol ✓' : 'Faollashtirish'" @click.stop="ws.setActive(ws.activeEnvId === e.id ? null : e.id)"><Icon :name="ws.activeEnvId === e.id ? 'check' : 'play'" :size="14" /></button>
        <button class="ib x" aria-label="Muhitni o'chirish" title="O'chirish" @click.stop="delEnv(e.id, e.name)"><Icon name="x" :size="14" /></button>
      </div>
      <div v-if="!ws.environments.length" class="empty">Muhit yo'q</div>
      <div class="sb-note">Globals barcha muhitlarda amal qiladi. Eski “Default” o'zgaruvchilar shu yerga ko'chirilgan.</div>
    </div>

    <div v-else-if="panel === 'history'" class="sb-body hist-panel" data-testid="history-list">
      <HistoryList :entries="hist.items" tp="sh" row-testid="history-row" empty-text="Tarix bo'sh" @select="loadHistory" @remove="hist.remove" />
    </div>

    <div v-else class="sb-body" style="padding:8px 16px;color:var(--muted);font-size:var(--fs-md);line-height:1.6" data-testid="runner-panel">
      <p style="margin:0 0 12px">Collection yoki papkani tanlab, uni ketma-ket yoki CSV/JSON ma'lumotlari bilan bir necha marta ishga tushiring.</p>
      <button class="primary" data-testid="open-runner" @click="openRunner"><Icon name="play" :size="14" />Runner'ni ochish</button>
    </div>

    <div v-if="menu" class="overlay" style="background:none" @click="menu = null" @contextmenu.prevent="menu = null">
      <div class="menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }" data-testid="tree-menu" @click.stop>
        <template v-if="menu.row.isExample">
          <button data-act="ex-open" @click="menuAct('ex-open')">Ochish</button>
          <button data-act="ex-dup" @click="menuAct('ex-dup')">Dublikat</button>
          <button data-act="ex-delete" @click="menuAct('ex-delete')">O'chirish</button>
        </template>
        <template v-else>
        <button v-if="menu.row.isCollection" data-act="open" @click="menuAct('open')">Ochish</button>
        <button v-if="menu.row.folder" data-act="runner" @click="menuAct('runner')">Runner</button>
        <button v-if="menu.row.folder && !menu.row.isCollection" data-act="settings" @click="menuAct('settings')">Sozlamalar (Auth, Variables, Scripts)</button>
        <button v-if="menu.row.folder" data-act="newfolder" @click="menuAct('newfolder')">Yangi papka</button>
        <button data-act="rename" @click="menuAct('rename')">Nomini o'zgartirish</button>
        <button v-if="!menu.row.isCollection" data-act="dup" @click="menuAct('dup')">Dublikat</button>
        <button v-if="!menu.row.isCollection" data-act="move" @click="menuAct('move')">Ko'chirish…</button>
        <button v-if="!menu.row.isCollection" data-act="delete" @click="menuAct('delete')">O'chirish</button>
        </template>
      </div>
    </div>

    <Dialog v-if="moveDlg" title="Ko'chirish…" testid="move-dialog" width="460px" @close="moveDlg = null">
      <select v-model="moveTarget" style="width:100%" data-testid="move-target" aria-label="Qayerga ko'chirish" data-autofocus><option value="" disabled>Papka yoki collection tanlang</option><option v-for="o in moveOptions" :key="o.key" :value="o.key">{{ o.label }}</option></select>
      <template #footer>
        <button @click="moveDlg = null">Bekor qilish</button>
        <button class="primary" :disabled="!moveTarget" data-testid="move-ok" @click="confirmMove">Ko'chirish</button>
      </template>
    </Dialog>
  </aside>
</template>
