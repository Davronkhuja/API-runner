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
    urlencoded?: PmQuery[]
    formdata?: { key: string; value?: string; src?: string; type: 'text' | 'file'; disabled?: boolean }[]
    options?: { raw?: { language?: string } }
  }
  auth?: { type: string; [k: string]: any } | null
}
export interface RequestItem {
  id: string
  name: string
  request: PmRequest
  response: unknown[] // Examples
  'x-apirunner'?: { legacy?: Record<string, any>; settings?: Record<string, any> }
}
export interface FolderItem {
  id: string
  name: string
  item: TreeItem[]
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
export interface EnvValue { key: string; value: string; enabled: boolean; type: 'default' | 'secret' }
export interface Environment { id: string; name: string; values: EnvValue[] }
export interface CollectionMeta { id: string; name: string; requests: number }
export type DropPosition = 'before' | 'after' | 'inside'
