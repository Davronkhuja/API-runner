/** Nomi to'liq URL bo'lib qolgan so'rovlar uchun bir martalik "Nomlarni tozalash" taklifi (oldindan ko'rish + zaxira). */
import { post } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { useTree } from '../stores/tree'
import { requestsIn } from './nodes'
import { suggestName } from './rename'

export interface CleanItem { cid: string; id: string; old: string; neu: string }

export function urlNamedItems(): CleanItem[] {
  const tree = useTree(), out: CleanItem[] = []
  for (const [cid, col] of Object.entries(tree.cols)) {
    for (const r of requestsIn(col.item)) {
      const neu = suggestName(r.item.name)
      if (neu !== r.item.name && neu.trim()) out.push({ cid, id: r.item.id, old: r.item.name, neu })
    }
  }
  return out
}
export const isDismissed = () => useWorkspace().nameCleanDismissed
export const dismissOffer = () => { useWorkspace().dismissNameClean().catch(() => {}) }

/** Avval to'liq zaxira, keyin tanlangan nomlar o'zgartiriladi (so'rov ichidagi hech narsa tegilmaydi). Qaytaradi: zaxira nomi. */
export async function applyClean(items: CleanItem[]): Promise<string> {
  const tree = useTree(), tabs = useTabs()
  const bk = await post('/api/backups')
  for (const it of items) {
    await tree.renameItem(it.cid, it.id, it.neu)
    tabs.renameRef(`${it.cid}:${it.id}`, it.neu)
  }
  return bk.name
}
