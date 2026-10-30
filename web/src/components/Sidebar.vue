<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useTree, rowKey, dropPositionFor, type Row } from '../stores/tree'
import { useTabs } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useHistory } from '../stores/history'
import { openRequest } from '../lib/actions'
import { askConfirm, showToast } from '../lib/ui'
import { isFolder, type DropPosition, type RequestItem } from '../types/model'
import { draftFromItem } from '../lib/draft'

const tree = useTree(), tabs = useTabs(), ws = useWorkspace(), hist = useHistory()
const panel = ref<'collections' | 'environments' | 'history'>('collections')
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
  if (r.isCollection || r.folder) { tree.toggle(k, r.item); tree.select(k); return }
  tree.select(k)
  openRequest(r.collectionId, r.id, false)
}
function onDbl(r: Row) { if (!r.folder) openRequest(r.collectionId, r.id, true) }
void clickTimer

// ── Kontekst menyu ──
function ctx(e: MouseEvent, r: Row) { menu.value = { x: e.clientX, y: e.clientY, row: r }; if (!tree.selection.includes(keyOf(r))) tree.select(keyOf(r)) }
async function menuAct(a: string) {
  const r = menu.value!.row; menu.value = null
  if (a === 'rename') { renaming.value = keyOf(r); renameVal.value = r.name }
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
  await tree.move([keyOf(r)], keyOf(r), 'after', true)
}
async function commitRename(r: Row) {
  const name = renameVal.value.trim()
  renaming.value = null
  if (!name || name === r.name) return
  await tree.renameItem(r.collectionId, r.id, name)
  tabs.retitle(keyOf(r), name)
}
// "Ko'chirish..." — klaviatura/accessibility uchun DnD ning muqobili
const moveOptions = computed(() => tree.rows.filter(r => r.isCollection || r.folder).map(r => ({ key: keyOf(r), label: '　'.repeat(r.depth) + r.name })))
async function confirmMove() {
  const d = moveDlg.value!; moveDlg.value = null
  if (!moveTarget.value) return
  try { await tree.move(d.keys, moveTarget.value, 'inside') } catch (e: any) { showToast(e.message, 'error') }
}
async function newCollection() { await tree.createCollection('Yangi collection') }

// ── Environments / History ──
const loadHistory = (h: any) => { const t = tabs.openNew(); const p = h.payload; t.draft = draftFromItem({ id: 'h', name: 'Tarixdan', request: { method: 'GET', header: [], url: { raw: '' } }, response: [], 'x-apirunner': { legacy: { ...p, headers: p.headers ?? [], params: p.params ?? [] } } } as RequestItem); t.title = 'Tarixdan'; tabs.touch(t.id) }
const openEnv = (id: string, name: string) => tabs.open('environment', id, name, { permanent: true })
async function delEnv(id: string, name: string) { if (await askConfirm(`'${name}' o'chirilsinmi?`, "O'chirish")) await ws.deleteEnv(id) }
async function newEnv() { const id = await ws.createEnv('Yangi muhit'); openEnv(id, 'Yangi muhit') }
</script>

<template>
  <aside class="sidebar" data-testid="sidebar">
    <div class="sb-head">
      <button :class="{ on: panel === 'collections' }" data-testid="sb-collections" @click="panel = 'collections'">Collections</button>
      <button :class="{ on: panel === 'environments' }" data-testid="sb-environments" @click="panel = 'environments'">Muhit</button>
      <button :class="{ on: panel === 'history' }" data-testid="sb-history" @click="panel = 'history'; hist.load()">Tarix</button>
    </div>

    <template v-if="panel === 'collections'">
      <div style="padding:6px;display:flex;gap:4px">
        <input v-model="tree.filter" placeholder="Qidirish…" style="flex:1" data-testid="sb-search">
        <button title="Yangi collection" data-testid="new-collection" @click="newCollection">＋</button>
      </div>
      <div class="sb-body" ref="body" data-testid="tree" @dragover="onContainerDragOver" @dragend="reset" @drop="stopScroll">
        <div v-if="!tree.rows.length" class="empty">{{ tree.filter ? 'Hech narsa topilmadi' : 'Collection yo\'q. ＋ bosing.' }}</div>
        <div v-for="r in tree.rows" :key="rowKey(r.collectionId, r.id)" class="row" data-testid="tree-row"
             :data-key="rowKey(r.collectionId, r.id)" :data-name="r.name" :data-kind="r.isCollection ? 'collection' : r.folder ? 'folder' : 'request'"
             :class="{ sel: tree.selection.includes(rowKey(r.collectionId, r.id)), dragging: dragKeys.includes(rowKey(r.collectionId, r.id)),
                       'drop-inside': drop?.key === rowKey(r.collectionId, r.id) && drop.pos === 'inside',
                       'drop-before': drop?.key === rowKey(r.collectionId, r.id) && drop.pos === 'before',
                       'drop-after': drop?.key === rowKey(r.collectionId, r.id) && drop.pos === 'after' }"
             :style="{ paddingLeft: 6 + r.depth * 14 + 'px' }" :draggable="!r.isCollection"
             @click="onClick($event, r)" @dblclick="onDbl(r)" @contextmenu.prevent="ctx($event, r)"
             @dragstart="onDragStart($event, r)" @dragover="onDragOver($event, r)" @drop="onDrop($event)">
          <span v-if="r.folder" style="width:12px">{{ r.expanded ? '▾' : '▸' }}</span>
          <span v-else class="m" :class="'m-' + (r.item as any).request.method">{{ (r.item as any).request.method }}</span>
          <span v-if="r.isCollection">📚</span><span v-else-if="r.folder">📁</span>
          <input v-if="renaming === rowKey(r.collectionId, r.id)" v-model="renameVal" style="flex:1;padding:1px 4px" data-testid="rename-input"
                 @click.stop @keydown.enter="commitRename(r)" @keydown.esc="renaming = null" @blur="commitRename(r)" autofocus>
          <span v-else class="name">{{ r.name }}</span>
        </div>
      </div>
    </template>

    <div v-else-if="panel === 'environments'" class="sb-body" data-testid="env-list">
      <div style="padding:6px"><button style="width:100%" data-testid="new-env" @click="newEnv">＋ Yangi muhit</button></div>
      <div v-for="e in ws.environments" :key="e.id" class="row" :class="{ sel: ws.activeEnvId === e.id }" style="padding-left:10px" data-testid="env-row" @click="openEnv(e.id, e.name)">
        <span :class="ws.activeEnvId === e.id ? 'ok' : 'muted'">●</span><span class="name">{{ e.name }}</span>
        <button class="ghost" title="Faollashtirish" @click.stop="ws.setActive(ws.activeEnvId === e.id ? null : e.id)">{{ ws.activeEnvId === e.id ? '✓' : '○' }}</button>
        <button class="ghost" title="O'chirish" @click.stop="delEnv(e.id, e.name)">×</button>
      </div>
      <div v-if="!ws.environments.length" class="empty">Muhit yo'q</div>
    </div>

    <div v-else class="sb-body" data-testid="history-list">
      <div style="padding:6px"><button style="width:100%" @click="hist.clear('request')">Tozalash</button></div>
      <div v-for="h in hist.items" :key="h.id" class="row" style="padding-left:10px" data-testid="history-row" @click="loadHistory(h)">
        <span class="m" :class="'m-' + h.payload.method">{{ h.payload.method }}</span><span class="name">{{ h.payload.url }}</span>
        <button class="ghost" @click.stop="hist.remove(h.id)">×</button>
      </div>
      <div v-if="!hist.items.length" class="empty">Tarix bo'sh</div>
    </div>

    <div v-if="menu" class="overlay" style="background:none" @click="menu = null" @contextmenu.prevent="menu = null">
      <div class="menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }" data-testid="tree-menu" @click.stop>
        <button v-if="menu.row.folder" data-act="newfolder" @click="menuAct('newfolder')">Yangi papka</button>
        <button v-if="!menu.row.isCollection" data-act="rename" @click="menuAct('rename')">Nomini o'zgartirish</button>
        <button v-if="!menu.row.isCollection" data-act="dup" @click="menuAct('dup')">Dublikat</button>
        <button v-if="!menu.row.isCollection" data-act="move" @click="menuAct('move')">Ko'chirish…</button>
        <button v-if="!menu.row.isCollection" data-act="delete" @click="menuAct('delete')">O'chirish</button>
      </div>
    </div>

    <div v-if="moveDlg" class="overlay" @click.self="moveDlg = null">
      <div class="dialog" data-testid="move-dialog">
        <b>Ko'chirish…</b>
        <p><select v-model="moveTarget" style="width:100%" data-testid="move-target"><option value="" disabled>Papka yoki collection tanlang</option><option v-for="o in moveOptions" :key="o.key" :value="o.key">{{ o.label }}</option></select></p>
        <div class="btns"><button @click="moveDlg = null">Bekor qilish</button><button class="primary" :disabled="!moveTarget" data-testid="move-ok" @click="confirmMove">Ko'chirish</button></div>
      </div>
    </div>
  </aside>
</template>
