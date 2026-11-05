/** Nomni o'zgartirish: yagona yo'l (server + daraxt + ochiq tablar + qoralama), tekshiruv va xabarlar. */
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { isFolder, type TreeItem } from '../types/model'
import { showToast } from './ui'

/** Faqat bo'sh nom rad etiladi: Postman kabi bir papkada bir xil nomli elementlar ruxsat (ID bo'yicha ajraladi). */
export function validateName(_cid: string, _id: string | null, raw: string): string | null {
  return raw.trim() ? null : "Nom bo'sh bo'lishi mumkin emas"
}

/** Yumshoq ogohlantirish (bloklamaydi): so'rovlar — nom VA metod bir xil bo'lsa; papkalar — bir xil nomli papka bo'lsa. */
export function nameWarning(cid: string, id: string | null, raw: string): string | null {
  const tree = useTree()
  const name = raw.trim().toLowerCase()
  if (!name || id === null) return null
  const me = tree.findItem(cid, id) as any
  if (!me) return null
  const same = tree.siblings(cid, id).filter(s => s.id !== id && s.name.trim().toLowerCase() === name)
  if (isFolder(me)) return same.some(s => isFolder(s)) ? 'Bu papkada shu nomli papka allaqachon bor (ruxsat etiladi)' : null
  const m = (me.request?.method ?? '').toUpperCase()
  return same.some(s => !isFolder(s) && ((s as any).request?.method ?? '').toUpperCase() === m) ? `Bu papkada nomi va metodi (${m}) bir xil so'rov bor (ruxsat etiladi)` : null
}

/** Nomi to'liq URL bo'lib qolgan so'rov uchun qisqa taklif: host'siz path ("https://h/v1/a?x=1" -> "v1/a"). URL bo'lmasa — o'zi. */
export function suggestName(name: string): string {
  const t = name.trim()
  const m = /^(?:https?:\/\/[^/?#\s]+|\{\{[^}]+\}\})(\/[^?#\s]*)?/i.exec(t)
  if (!m) return name
  const path = (m[1] ?? '').replace(/^\/+|\/+$/g, '')
  return path || name
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
