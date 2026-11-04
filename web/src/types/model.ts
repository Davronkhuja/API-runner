// Backend modeli: Postman Collection v2.1 superseti (docs/adr/0004).
export interface PmHeader { key: string; value: string; disabled?: boolean; description?: string }
export interface PmQuery { key: string; value: string; disabled?: boolean; description?: string }
export interface PmRequest {
  method: string
  header: PmHeader[]
  url: { raw: string; query?: PmQuery[]; variable?: { key: string; value: string }[] }
  body?: {
    mode: 'raw' | 'urlencoded' | 'formdata' | 'file' | 'graphql'
    raw?: string
    file?: { src?: string; name?: string }
    graphql?: { query?: string; variables?: string }
    urlencoded?: PmQuery[]
    formdata?: { key: string; value?: string; src?: string | string[]; type: 'text' | 'file'; contentType?: string; disabled?: boolean }[]
    options?: { raw?: { language?: string } }
  }
  auth?: { type: string; [k: string]: any } | null
}
export interface RequestItem {
  id: string
  name: string
  request: PmRequest
  response: unknown[] // Examples
  event?: { listen: string; script: { type?: string; exec: string[] | string } }[]
  'x-apirunner'?: { legacy?: Record<string, any>; files_migrated?: boolean; pre_files_body?: unknown; settings?: Record<string, any> }
}
export interface FolderItem {
  id: string
  name: string
  item: TreeItem[]
  event?: { listen: string; script: { type?: string; exec: string[] | string } }[]
  'x-apirunner'?: { expanded?: boolean }
}
export type TreeItem = RequestItem | FolderItem
export const isFolder = (i: TreeItem): i is FolderItem => 'item' in i

export interface Collection {
  info: { _postman_id: string; name: string }
  item: TreeItem[]
  auth?: unknown
  variable?: unknown[]
  event?: unknown[]
}
/** value — Boshlang'ich (eksport/zaxiraga tushadi); current — Joriy (shu kompyuterda; skriptlar shuni o'zgartiradi, bor bo'lsa ustun). */
export interface EnvValue { key: string; value: string; current?: string | null; enabled: boolean; type: 'default' | 'secret' }
export type EnvKind = 'dev' | 'test' | 'prod'
export interface Environment { id: string; name: string; values: EnvValue[]; kind?: EnvKind | ''; confirm_writes?: boolean }
export interface CollectionMeta { id: string; name: string; requests: number }
export type DropPosition = 'before' | 'after' | 'inside'
