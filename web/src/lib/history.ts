import { useTabs } from '../stores/tabs'
import { draftFromItem } from './draft'
import type { RequestItem } from '../types/model'

/** Tarix yozuvidan yangi tab ochadi (Sidebar va History drawer uchun yagona). */
export function openFromHistory(h: { payload: any }) {
  const tabs = useTabs()
  const t = tabs.openNew()
  const p = h.payload
  t.draft = draftFromItem({ id: 'h', name: 'Tarixdan', request: { method: 'GET', header: [], url: { raw: '' } }, response: [], 'x-apirunner': { legacy: { ...p, headers: p.headers ?? [], params: p.params ?? [] } } } as RequestItem)
  t.title = 'Tarixdan'
  tabs.touch(t.id)
}
