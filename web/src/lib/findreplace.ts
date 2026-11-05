/** Workspace bo'ylab Find & Replace: API klienti. */
import { post } from '../api/client'

export interface FrOptions { query: string; replacement: string; case: boolean; word: boolean; regex: boolean; targets: string[]; collection_ids?: string[] }
export interface FrSnippet { before: string; match: string; after: string; replacement: string; lead: boolean; trail: boolean }
export interface FrResult { id: string; doc_kind: 'collection' | 'environment'; collection_id: string | null; collection_name: string; owner_kind: string; owner_id: string; owner_name: string; field: string; count: number; secret: boolean; snippets: FrSnippet[] }

export const TARGET_LABELS: [string, string][] = [['name', 'Nomlar'], ['url', 'URL'], ['params', 'Params'], ['headers', 'Headers'], ['body', 'Body'], ['auth', 'Auth'], ['scripts', 'Skriptlar'], ['description', 'Tavsiflar'], ['variables', "Collection/papka o'zgaruvchilari"], ['environments', 'Muhitlar']]
export const ALL_TARGETS = TARGET_LABELS.map(t => t[0])

export const frSearch = (o: FrOptions) => post('/api/find-replace/search', o) as Promise<{ results: FrResult[]; truncated: boolean; total: number }>
export const frApply = (o: FrOptions, ids: string[]) => post('/api/find-replace/apply', { ...o, ids }) as Promise<{ replacements: number; documents: number; skipped: string[]; backup: string }>

/** Natijalarni collection → egasi (so'rov/papka/collection) bo'yicha guruhlash. */
export function groupResults(rs: FrResult[]) {
  const out: { key: string; title: string; sub: string; rows: FrResult[] }[] = []
  const idx = new Map<string, number>()
  for (const r of rs) {
    const key = r.doc_kind === 'environment' ? `e:${r.owner_id}` : `c:${r.collection_id}:${r.owner_id}`
    if (!idx.has(key)) { idx.set(key, out.length); out.push({ key, title: r.owner_kind === 'collection' ? r.collection_name : r.owner_name, sub: r.doc_kind === 'environment' ? 'Muhit' : r.owner_kind === 'collection' ? 'Collection' : `${r.collection_name} · ${r.owner_kind === 'folder' ? 'papka' : "so'rov"}`, rows: [] }) }
    out[idx.get(key)!].rows.push(r)
  }
  return out
}
