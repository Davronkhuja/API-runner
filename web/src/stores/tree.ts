import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { get, post, patch, del } from '../api/client'
import { isFolder, type Collection, type CollectionMeta, type DropPosition, type TreeItem } from '../types/model'

export interface Row { id: string; collectionId: string; item: TreeItem | null; depth: number; folder: boolean; expanded: boolean; parentId: string | null; isCollection: boolean; name: string }

export const rowKey = (collectionId: string, id: string) => `${collectionId}:${id}`

/** Nodeni (papka) o'z ichiga/avlodiga tashlashni taqiqlash: `target` `dragged` ning avlodimi yoki o'zimi. */
export function isSelfOrDescendant(items: TreeItem[], draggedId: string, targetId: string): boolean {
  const find = (xs: TreeItem[]): TreeItem | undefined => { for (const x of xs) { if (x.id === draggedId) return x; if (isFolder(x)) { const r = find(x.item); if (r) return r } } }
  const node = find(items)
  if (!node) return false
  const has = (n: TreeItem): boolean => n.id === targetId || (isFolder(n) && n.item.some(has))
  return has(node)
}

/** Pointer joylashuvidan tushish pozitsiyasi: papkada yuqori 25% = before, pastki 25% = after, o'rtasi = inside; so'rovda 50/50. */
export function dropPositionFor(offsetY: number, height: number, isFolderRow: boolean): DropPosition {
  const r = offsetY / Math.max(1, height)
  if (isFolderRow) return r < 0.25 ? 'before' : r > 0.75 ? 'after' : 'inside'
  return r < 0.5 ? 'before' : 'after'
}

export const useTree = defineStore('tree', () => {
  const metas = ref<CollectionMeta[]>([])
  const cols = ref<Record<string, Collection>>({})
  const expandedOverride = ref<Record<string, boolean>>({})   // collapse/expand holati (ui-state bilan saqlanadi)
  const filter = ref('')
  const selection = ref<string[]>([])                        // rowKey'lar
  const anchor = ref<string | null>(null)

  async function load() {
    metas.value = await get('/api/workspace').then(w => w.collections)
    const loaded: Record<string, Collection> = {}
    for (const m of metas.value) loaded[m.id] = await get(`/api/collections/${m.id}`)
    cols.value = loaded
  }
  async function reloadCollection(cid: string) { cols.value = { ...cols.value, [cid]: await get(`/api/collections/${cid}`) } }

  const isExpanded = (k: string, item: TreeItem | null) =>
    k in expandedOverride.value ? expandedOverride.value[k] : (item && isFolder(item) ? (item['x-apirunner']?.expanded ?? true) : true)

  function toggle(k: string, item: TreeItem | null) { expandedOverride.value = { ...expandedOverride.value, [k]: !isExpanded(k, item) } }
  function setExpanded(k: string, v: boolean) { expandedOverride.value = { ...expandedOverride.value, [k]: v } }

  const matches = (it: TreeItem, q: string): boolean => it.name.toLowerCase().includes(q) || (isFolder(it) && it.item.some(c => matches(c, q)))

  /** Ko'rinadigan qatorlar (tekis ro'yxat). Qidiruv faol bo'lsa mos kelganlar va ularning ota-onalari ko'rinadi, papkalar ochiq. */
  const rows = computed<Row[]>(() => {
    const out: Row[] = []
    const q = filter.value.trim().toLowerCase()
    for (const m of metas.value) {
      const col = cols.value[m.id]
      if (!col) continue
      if (q && !col.item.some(i => matches(i, q))) continue
      const ck = rowKey(m.id, '')
      const cExp = q ? true : isExpanded(ck, null)
      out.push({ id: '', collectionId: m.id, item: null, depth: 0, folder: true, expanded: cExp, parentId: null, isCollection: true, name: col.info.name })
      if (!cExp) continue
      const walk = (items: TreeItem[], depth: number, parentId: string | null) => {
        for (const it of items) {
          if (q && !matches(it, q)) continue
          const k = rowKey(m.id, it.id)
          const f = isFolder(it)
          const exp = f ? (q ? true : isExpanded(k, it)) : false
          out.push({ id: it.id, collectionId: m.id, item: it, depth, folder: f, expanded: exp, parentId, isCollection: false, name: it.name })
          if (f && exp) walk(it.item, depth + 1, it.id)
        }
      }
      walk(col.item, 1, null)
    }
    return out
  })

  // ── tanlash: Shift = oraliq, Cmd/Ctrl = qo'shish/olish ──
  function select(k: string, mods: { shift?: boolean; meta?: boolean } = {}) {
    const keys = rows.value.filter(r => !r.isCollection).map(r => rowKey(r.collectionId, r.id))
    if (mods.shift && anchor.value && keys.includes(anchor.value)) {
      const a = keys.indexOf(anchor.value), b = keys.indexOf(k)
      selection.value = keys.slice(Math.min(a, b), Math.max(a, b) + 1)
    } else if (mods.meta) {
      selection.value = selection.value.includes(k) ? selection.value.filter(x => x !== k) : [...selection.value, k]
      anchor.value = k
    } else { selection.value = [k]; anchor.value = k }
  }
  const clearSelection = () => { selection.value = []; anchor.value = null }

  /** Sudralayotgan elementlar: sudralgan tanlangan bo'lsa — butun tanlov (tartib bilan), aks holda faqat o'zi. */
  function dragSet(k: string): string[] {
    if (!selection.value.includes(k)) return [k]
    const order = rows.value.map(r => rowKey(r.collectionId, r.id))
    return [...selection.value].sort((a, b) => order.indexOf(a) - order.indexOf(b))
  }

  /** Klientdagi dastlabki tekshiruv (server baribir tekshiradi). */
  function canDrop(dragKeys: string[], targetKey: string, pos: DropPosition): boolean {
    const [tc, tid] = targetKey.split(':')
    const target = rows.value.find(r => r.collectionId === tc && r.id === tid)
    if (!target) return false
    if (target.isCollection) return pos === 'inside'
    if (pos === 'inside' && !target.folder) return false
    for (const dk of dragKeys) {
      const [dc, did] = dk.split(':')
      if (dc === tc && (did === tid || isSelfOrDescendant(cols.value[dc].item, did, tid))) return false
    }
    return true
  }

  /** Server tomonda ko'chirish/nusxalash; tartib backendda `item[]` da saqlanadi. */
  async function move(dragKeys: string[], targetKey: string, pos: DropPosition, copy = false) {
    if (!canDrop(dragKeys, targetKey, pos)) return false
    const [tc, tid] = targetKey.split(':')
    // bir nechta collection'dan sudralganda — har bir manba alohida chaqiriladi
    const bySrc = new Map<string, string[]>()
    for (const k of dragKeys) { const [c, i] = k.split(':'); bySrc.set(c, [...(bySrc.get(c) ?? []), i]) }
    for (const [src, ids] of bySrc) {
      await post('/api/items/move', { src, dst: tc, ids, target_id: tid || null, position: pos, copy })
    }
    await Promise.all([...new Set([...bySrc.keys(), tc])].map(reloadCollection))
    if (pos === 'inside') setExpanded(targetKey, true)
    return true
  }

  /** Dublikat: elementdan keyin nusxa (yangi id), nomi " Copy" bilan. */
  async function duplicate(cid: string, id: string) {
    const r = await post('/api/items/move', { src: cid, dst: cid, ids: [id], target_id: id, position: 'after', copy: true })
    const newId = r.mapping[id] as string
    const orig = findItem(cid, id)
    await reloadCollection(cid)
    if (orig) await renameItem(cid, newId, orig.name + ' Copy')
    return newId
  }

  async function addItem(cid: string, item: any, parentId: string | null = null, index?: number) {
    const r = await post(`/api/collections/${cid}/items`, { parent_id: parentId, item, index })
    await reloadCollection(cid)
    return r.id as string
  }
  async function renameItem(cid: string, id: string, name: string) { await patch(`/api/collections/${cid}/items/${id}`, { name }); await reloadCollection(cid) }
  async function updateItem(cid: string, id: string, p: object) { await patch(`/api/collections/${cid}/items/${id}`, p); await reloadCollection(cid) }
  async function removeItem(cid: string, id: string) { await del(`/api/collections/${cid}/items/${id}`); await reloadCollection(cid) }
  async function createCollection(name: string) { const r = await post('/api/collections', { name }); await load(); return r.id as string }

  function findItem(cid: string, id: string): TreeItem | undefined {
    const walk = (xs: TreeItem[]): TreeItem | undefined => { for (const x of xs) { if (x.id === id) return x; if (isFolder(x)) { const r = walk(x.item); if (r) return r } } }
    return cols.value[cid] ? walk(cols.value[cid].item) : undefined
  }
  /** "Collection'da ko'rsatish": ota papkalarni ochadi va qatorni tanlaydi. */
  function reveal(cid: string, id: string) {
    const path: string[] = []
    const walk = (xs: TreeItem[], trail: string[]): boolean => { for (const x of xs) { if (x.id === id) { path.push(...trail); return true } if (isFolder(x) && walk(x.item, [...trail, x.id])) return true } return false }
    if (!cols.value[cid] || !walk(cols.value[cid].item, [])) return false
    setExpanded(rowKey(cid, ''), true)
    path.forEach(p => setExpanded(rowKey(cid, p), true))
    selection.value = [rowKey(cid, id)]; anchor.value = rowKey(cid, id)
    return true
  }

  return { metas, cols, expandedOverride, filter, selection, rows, load, reloadCollection, isExpanded, toggle, setExpanded, select, clearSelection, dragSet, canDrop, move, duplicate, addItem, renameItem, updateItem, removeItem, createCollection, findItem, reveal }
})
