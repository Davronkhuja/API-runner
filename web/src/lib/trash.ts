/** Savat (30 kun): ro'yxat, tiklash, butunlay o'chirish. */
import { del, get, post } from '../api/client'

export interface TrashRow {
  id: string; kind: 'item' | 'collection' | 'environment'; name: string; deleted_at: number; expires_at: number; days_left: number
  origin: { collection_name?: string; parent_name?: string | null; folder?: boolean; requests?: number; values?: number }
}
export const listTrash = () => get('/api/trash') as Promise<TrashRow[]>
export const restoreTrash = (id: string) => post(`/api/trash/${id}/restore`) as Promise<any>
export const deleteTrash = (id: string) => del(`/api/trash/${id}`)
export const emptyTrash = () => del('/api/trash') as Promise<{ deleted: number }>

export const kindLabel = (r: TrashRow) => (r.kind === 'collection' ? 'Collection' : r.kind === 'environment' ? 'Muhit' : r.origin.folder ? 'Papka' : "So'rov")
export function whereLabel(r: TrashRow): string {
  if (r.kind === 'collection') return `${r.origin.requests ?? 0} ta so'rov`
  if (r.kind === 'environment') return `${r.origin.values ?? 0} ta o'zgaruvchi`
  return [r.origin.collection_name, r.origin.parent_name].filter(Boolean).join(' / ') + (r.origin.folder ? ` · ${r.origin.requests ?? 0} ta so'rov` : '')
}
