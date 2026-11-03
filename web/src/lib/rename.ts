/** Nomni o'zgartirish: yagona yo'l (server + daraxt + ochiq tablar + qoralama), tekshiruv va xabarlar. */
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { isFolder, type TreeItem } from '../types/model'
import { showToast } from './ui'

/** `id` null — collection. Xabar qaytaradi yoki null (yaroqli). */
export function validateName(cid: string, id: string | null, raw: string): string | null {
  const tree = useTree()
  const name = raw.trim()
  if (!name) return "Nom bo'sh bo'lishi mumkin emas"
  if (id === null) {
    const dup = tree.metas.some(m => m.id !== cid && m.name.trim().toLowerCase() === name.toLowerCase())
    return dup ? `«${name}» nomli collection allaqachon bor` : null
  }
  const sib = tree.siblings(cid, id)
  if (sib.some(s => s.id !== id && s.name.trim().toLowerCase() === name.toLowerCase())) return `«${name}» nomli element bu papkada allaqachon bor`
  return null
}

export async function renameNode(cid: string, id: string | null, raw: string): Promise<boolean> {
  const tree = useTree(), tabs = useTabs()
  const name = raw.trim()
  const err = validateName(cid, id, raw)
  if (err) { showToast(err, 'warn'); return false }
  const cur = id === null ? tree.cols[cid]?.info.name : tree.findItem(cid, id)?.name
  if (cur === name) return true
  try {
    if (id === null) await tree.renameCollection(cid, name); else await tree.renameItem(cid, id, name)
  } catch (e: any) { showToast(e.message, 'error'); return false }
  tabs.renameRef(id === null ? cid : `${cid}:${id}`, name)
  return true
}

/** "X Copy", "X Copy 2" … — bir papkada takrorlanmaydigan nusxa nomi. */
export function copyName(cid: string, id: string, base: string): string {
  const tree = useTree()
  const names = new Set(tree.siblings(cid, id).map(s => s.name))
  let n = base + ' Copy', i = 1
  while (names.has(n)) n = `${base} Copy ${++i}`
  return n
}
void (null as unknown as TreeItem | null); void isFolder
