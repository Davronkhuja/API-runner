/** GraphQL: introspection, sxema keshi (tab bo'yicha), so'rov skeleti va variables tekshiruvi. */
import { markRaw, reactive } from 'vue'
import { buildClientSchema, getIntrospectionQuery, isNonNullType, isObjectType, isInterfaceType, getNamedType, isLeafType, parse, print, type GraphQLField, type GraphQLNamedType, type GraphQLSchema, type OperationDefinitionNode } from 'graphql'
import { del, get, post, put } from '../api/client'
import { flatVars } from './scope'
import { prepareAuth, specFor } from './scope'
import type { Tab } from '../stores/tabs'

export interface GqlState { schema: GraphQLSchema | null; loading: boolean; error: string; at: number; fromCache: boolean; key: string }
export const gqlStates = reactive<Record<string, GqlState>>({})
export const gqlState = (tabId: string): GqlState => (gqlStates[tabId] ??= { schema: null, loading: false, error: '', at: 0, fromCache: false, key: '' })

/** Kesh kaliti: o'zgaruvchilari yechilgan URL (query'siz) — bir endpoint'ning so'rovlari bitta sxemani bo'lishadi. */
export function cacheKey(tab: Tab): string {
  const vars = flatVars(tab.ref)
  return tab.draft!.url.trim().split('?')[0].replace(/\{\{\s*([^}]+?)\s*\}\}/g, (m, k) => vars[k] ?? m)
}

/** Diskdagi keshdan sxemani yuklaydi (bo'lsa). */
export async function loadCached(tab: Tab): Promise<void> {
  const st = gqlState(tab.id)
  const key = cacheKey(tab)
  if (!key || st.schema && st.key === key) return
  try {
    const r = await get(`/api/graphql/schema?key=${encodeURIComponent(key)}`)
    if (r.cached) { st.schema = markRaw(buildClientSchema(r.introspection)); st.at = r.fetched_at * 1000; st.fromCache = true; st.key = key }
  } catch { /* kesh o'qilmadi — qayta yuklash mumkin */ }
}
export async function clearCached(tab: Tab): Promise<void> {
  const st = gqlState(tab.id)
  await del(`/api/graphql/schema?key=${encodeURIComponent(cacheKey(tab))}`).catch(() => {})
  st.schema = null; st.fromCache = false
}

/** Hozirgi so'rov URL/headers/auth bilan introspection yuboradi (`/run_one`). */
export async function introspect(tab: Tab): Promise<void> {
  const st = gqlState(tab.id), d = tab.draft!
  st.loading = true; st.error = ''
  try {
    if (!d.url.trim()) throw new Error('URL kiriting')
    await prepareAuth(d, tab.ref)
    const spec = specFor(d, tab.ref)
    spec.method = 'POST'; spec.body_type = 'json'; spec.body = JSON.stringify({ query: getIntrospectionQuery({ descriptions: true }) }); spec.timeout = 30
    const r = await post('/run_one', spec)
    if (typeof r.status !== 'number') throw new Error(typeof r.response === 'string' ? r.response : 'Ulanib bo\'lmadi')
    const body = typeof r.response === 'string' ? JSON.parse(r.response) : r.response
    if (body?.errors?.length && !body.data) throw new Error((r.status >= 400 ? `HTTP ${r.status}: ` : '') + (body.errors[0].message ?? 'Introspection xatosi'))
    if (!body?.data?.__schema) throw new Error(r.status >= 400 ? `Server HTTP ${r.status} qaytardi` : 'Javobda sxema yo\'q (introspection o\'chirilgan bo\'lishi mumkin)')
    st.schema = markRaw(buildClientSchema(body.data)); st.at = Date.now(); st.fromCache = false; st.key = cacheKey(tab)
    put('/api/graphql/schema', { key: st.key, introspection: body.data }).catch(() => {})            // diskka saqlanadi
  } catch (e: any) { st.error = e.message } finally { st.loading = false }
}

export const rootTypes = (s: GraphQLSchema) => [['Query', s.getQueryType()], ['Mutation', s.getMutationType()], ['Subscription', s.getSubscriptionType()]].filter(x => x[1]) as [string, GraphQLNamedType][]
export const userTypes = (s: GraphQLSchema) => Object.values(s.getTypeMap()).filter(t => !t.name.startsWith('__')).sort((a, b) => a.name.localeCompare(b.name))
export const fieldsOf = (t: GraphQLNamedType): GraphQLField<any, any>[] => (isObjectType(t) || isInterfaceType(t) ? Object.values(t.getFields()) : [])

/** Maydon uchun tayyor operatsiya: argumentlar o'zgaruvchi sifatida, ichida skalyar maydonlar (1 daraja). */
export function skeleton(op: 'query' | 'mutation' | 'subscription', f: GraphQLField<any, any>): string {
  const vars = f.args.map(a => `$${a.name}: ${a.type}`).join(', ')
  const args = f.args.map(a => `${a.name}: $${a.name}`).join(', ')
  const named = getNamedType(f.type)
  const sel = isLeafType(named) ? '' : ` {\n${(fieldsOf(named).filter(x => isLeafType(getNamedType(x.type))).slice(0, 6).map(x => `    ${x.name}`).join('\n')) || '    __typename'}\n  }`
  return `${op}${vars ? ` Op(${vars})` : ' Op'} {\n  ${f.name}${args ? `(${args})` : ''}${sel}\n}`
}
export function skeletonVariables(f: GraphQLField<any, any>): string {
  const ex = (t: any): unknown => { const s = (getNamedType(t) as any).name as string; return s === 'Int' || s === 'Float' ? 0 : s === 'Boolean' ? false : s === 'String' || s === 'ID' ? '' : null }
  const o: Record<string, unknown> = {}
  for (const a of f.args) o[a.name] = ex(a.type)
  return Object.keys(o).length ? JSON.stringify(o, null, 2) : ''
}

/** Variables tekshiruvi: JSON xatosi va majburiy (NonNull, defaultsiz) o'zgaruvchilar yo'qligi. */
export function variableIssues(query: string, varsText: string): string[] {
  const out: string[] = []
  let vars: Record<string, unknown> = {}
  if (varsText.trim()) { try { const v = JSON.parse(varsText); if (v && typeof v === 'object' && !Array.isArray(v)) vars = v; else out.push('Variables JSON obyekt bo\'lishi kerak') } catch { out.push('Variables: JSON noto\'g\'ri') } }
  try {
    const ops = parse(query).definitions.filter((x): x is OperationDefinitionNode => x.kind === 'OperationDefinition')
    for (const op of ops.slice(0, 1)) for (const v of op.variableDefinitions ?? []) {
      const name = v.variable.name.value
      if (v.type.kind === 'NonNullType' && !v.defaultValue && !(name in vars)) out.push(`Majburiy o'zgaruvchi yo'q: $${name}`)
    }
    if (ops.length > 1) out.push(`${ops.length} ta operatsiya bor — serverga operationName kerak bo'lishi mumkin`)
  } catch { /* sintaksis xatosini muharrir ko'rsatadi */ }
  return out
}
export { print, isNonNullType }
