/** «Meros'ga o'tkazish» taklifi: faqat haqiqiy nomzodlar uchun, va faqat auth tur/tokeni haqiqatan o'zgarganda. */
import { post } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { emptyAuth } from './auth'
import { hasRealAuth, overridableRequests, sameAuth } from './nodes'
import { showToast } from './ui'

export const offerKey = (cid: string, nodeId: string | null) => `${cid}:${nodeId ?? ''}`

export interface OfferCandidate { id: string; name: string; path: string; auth: any; same: boolean; noauth: boolean; stale: boolean }

/**
 * Nomzod: o'z auth'i papkaning YANGI yoki ESKI auth'iga aynan teng (bir xil tur va token) so'rov. Boshqacha auth'li so'rovlar sanalmaydi;
 * foydalanuvchi «o'z auth'ida qoldirgan» (kept) so'rovlar ham. `stale` — eski auth bilan bir xil (eski tokenni ishlatyapti).
 */
export function offerCandidates(cid: string, nodeId: string | null, oldPm: any, newPm: any): OfferCandidate[] {
  if (!hasRealAuth(newPm) || sameAuth(oldPm ?? null, newPm)) return []
  const node = useWorkspace().authOffers.nodes[offerKey(cid, nodeId)]
  if (node?.off) return []
  const kept = new Set(node?.kept ?? [])
  return overridableRequests(cid, nodeId, newPm)
    .filter(c => !c.noauth && !kept.has(c.id) && (sameAuth(c.auth, newPm) || (hasRealAuth(oldPm) && sameAuth(c.auth, oldPm))))
    .map(c => ({ ...c, stale: !sameAuth(c.auth, newPm) }))
}

/** Tanlangan so'rovlarni «Meros»ga o'tkazadi (zaxira bilan) va ochiq tablardagi qoralamalarni yangilaydi. */
export async function applyInherit(cid: string, ids: string[]) {
  const tree = useTree(), tabs = useTabs()
  const r = await post(`/api/collections/${cid}/inherit-auth`, { ids })
  await tree.reloadCollection(cid)
  for (const t of tabs.tabs) {
    const id = t.ref?.split(':')[1]
    if (t.kind === 'request' && t.draft && t.ref?.startsWith(cid + ':') && id && ids.includes(id)) t.draft.auth = emptyAuth('inherit')
  }
  return r as { changed: number; backup: string }
}

/** Rad etilgan so'rovlar (o'z auth'ida qoldirilgan) va «bu papka uchun boshqa so'ramaslik» ni eslab qoladi. */
export async function rememberOffer(cid: string, nodeId: string | null, kept: string[], off: boolean) {
  const ws = useWorkspace(), key = offerKey(cid, nodeId), cur = ws.authOffers.nodes[key] ?? { off: false, kept: [] }
  if (!kept.length && !off) return
  await ws.saveAuthOffers({ ...ws.authOffers, nodes: { ...ws.authOffers.nodes, [key]: { off: cur.off || off, kept: [...new Set([...cur.kept, ...kept])] } } })
}

/** Yengil variant: 8 soniyalik toast + «Meros'ga o'tkazish» tugmasi. */
export function offerToast(cid: string, cands: OfferCandidate[]) {
  const stale = cands.filter(c => c.stale).length
  const msg = stale ? `${stale} ta so'rov eski tokenni ishlatyapti` : `${cands.length} ta so'rovda shu auth'ning o'z nusxasi bor`
  showToast(msg, 'info', 8000, {
    label: "Meros'ga o'tkazish",
    run: async () => {
      try { const r = await applyInherit(cid, cands.map(c => c.id)); showToast(`${r.changed} ta so'rov «Meros»ga o'tkazildi · zaxira: ${r.backup}`, 'success', 6000) } catch (e: any) { showToast(e.message, 'error') }
    },
  })
}
