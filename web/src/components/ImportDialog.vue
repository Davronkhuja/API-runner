<script setup lang="ts">
/** Import dialogi (Postman uslubida): fayl/papka sudrab tashlash yoki tanlash, matn joylashtirish (cURL, Postman JSON, OpenAPI), URL'dan import; natija oldindan ko'rsatiladi va tasdiqlanadi. */
import { computed, reactive, ref } from 'vue'
import Dialog from './Dialog.vue'
import { post } from '../api/client'
import { useTree } from '../stores/tree'
import { useTabs } from '../stores/tabs'
import { useWorkspace } from '../stores/workspace'
import { applyCurlToDraft, parseCurl } from '../lib/curl'
import { showToast } from '../lib/ui'

const emit = defineEmits<{ close: [] }>()
const tree = useTree(), tabs = useTabs(), ws = useWorkspace()
type Action = 'import' | 'copy' | 'replace' | 'merge' | 'skip'
interface Stats { folders?: number; requests?: number; variables?: number; examples?: number; scripts?: number }
interface Item { type: 'collection' | 'environment' | 'globals'; name: string; stats: Stats; conflict: { id: string; name: string; merge: Record<string, number> } | null; default_action: Action; action: Action }
interface Entry { id: number; name: string; content: string; encoding?: 'base64'; curl?: boolean; preview?: { kind: string; name: string; folders: number; requests: number; variables: number }; label?: string; items?: Item[]; warnings?: string[]; error?: string }
const entries = ref<Entry[]>([])
const tab = ref<'file' | 'text' | 'url'>('file')
const text = ref(''), url = ref(''), busy = ref(false), over = ref(false)
const fileEl = ref<HTMLInputElement>(), dirEl = ref<HTMLInputElement>()
let seq = 0

const curlCount = (t: string) => (t.match(/(^|\n)\s*(\$\s*)?curl\b/gi) ?? []).length
async function add(name: string, content: string, encoding?: 'base64') {
  const e = reactive<Entry>({ id: ++seq, name, content, encoding })          // reaktiv: preview keyin to'ldiriladi
  entries.value.push(e)
  const c = encoding ? null : parseCurl(content)
  if (c && /^\s*curl\b/i.test(content) && curlCount(content) === 1) { e.curl = true; e.label = 'cURL'; e.preview = { kind: 'cURL', name: `${c.method} ${c.url}`.slice(0, 80), folders: 0, requests: 1, variables: 0 }; return }
  try {
    const r = (await post('/api/import/preview', { sources: [{ name, content, encoding }] })).sources[0]
    if (!r.ok) { e.error = r.error; return }
    e.label = r.label; e.warnings = r.warnings
    e.items = r.items.map((i: any) => ({ ...i, action: i.default_action }))
    const first = e.items!.find(i => i.type === 'collection') ?? e.items![0]
    e.preview = { kind: r.label, name: e.items!.length > 1 ? `${first.name} (+${e.items!.length - 1})` : first.name, folders: sum(e.items!, 'folders'), requests: sum(e.items!, 'requests'), variables: sum(e.items!, 'variables') }
  } catch (err: any) { e.error = err.message }
}
const sum = (items: Item[], k: keyof Stats) => items.filter(i => i.action !== 'skip').reduce((n, i) => n + (i.stats[k] ?? 0), 0)
async function toBase64(f: File) {
  const buf = new Uint8Array(await f.arrayBuffer()); let s = ''
  for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000))
  return btoa(s)
}
async function onFiles(files: FileList | File[] | null) {
  for (const f of [...(files ?? [])]) {
    if (/\.zip$/i.test(f.name)) await add(f.name, await toBase64(f), 'base64')
    else if (/\.(json|txt|curl|sh|ya?ml|har)$/i.test(f.name) || f.type.includes('json')) await add(f.name, await f.text())
  }
}
function onDrop(ev: DragEvent) { over.value = false; ev.preventDefault(); onFiles(ev.dataTransfer?.files ?? null) }
async function addText() { if (text.value.trim()) { await add('Joylashtirilgan matn', text.value); text.value = '' } }
async function addUrl() {
  if (!url.value.trim()) return
  busy.value = true
  try { const r = await post('/api/import/fetch', { url: url.value.trim() }); await add(url.value.trim(), r.content); url.value = '' }
  catch (err: any) { entries.value.push({ id: ++seq, name: url.value.trim(), content: '', error: err.message }) }
  finally { busy.value = false }
}
const valid = computed(() => entries.value.filter(e => e.preview && !e.error))
const total = computed(() => valid.value.reduce((a, e) => (e.items ? { folders: a.folders + sum(e.items, 'folders'), requests: a.requests + sum(e.items, 'requests'), variables: a.variables + sum(e.items, 'variables') } : { folders: a.folders + e.preview!.folders, requests: a.requests + e.preview!.requests, variables: a.variables + e.preview!.variables }), { folders: 0, requests: 0, variables: 0 }))
const activeItems = computed(() => valid.value.reduce((n, e) => n + (e.items ? e.items.filter(i => i.action !== 'skip').length : 1), 0))
async function run() {
  busy.value = true
  try {
    const server = valid.value.filter(e => !e.curl)
    for (const e of valid.value.filter(e => e.curl)) { const t = tabs.openNew(); applyCurlToDraft(t.draft!, parseCurl(e.content)!); tabs.touch(t.id) }
    let results: any[] = []
    if (server.length) {
      const r = await post('/api/import/apply', {
        sources: server.map(e => ({ name: e.name, content: e.content, encoding: e.encoding })),
        decisions: server.flatMap((e, si) => (e.items ?? []).map((i, ii) => ({ source: si, item: ii, action: i.action }))),
      })
      if (r.errors?.length) throw new Error(r.errors[0].error)
      results = r.results
    }
    await Promise.all([tree.load(), ws.load()])
    const done = results.filter(r => r.action !== 'skip')
    showToast(done.length ? `Import qilindi: ${done.map(r => `${r.name}${r.action === 'merge' ? ` (+${r.added_requests ?? r.added_variables ?? 0})` : ''}`).slice(0, 3).join(', ')}${done.length > 3 ? ` va yana ${done.length - 3} ta` : ''}` : 'Import qilindi', 'success', 4000)
    emit('close')
  } catch (err: any) { showToast(err.message, 'error') } finally { busy.value = false }
}
const ACTION_LABEL = (i: Item): [Action, string][] => {
  const m = i.conflict?.merge ?? {}
  const gain = i.type === 'collection' ? `+${m.added_requests ?? 0} so'rov` : `+${m.added_variables ?? 0} o'zgaruvchi`
  return [['copy', i.type === 'globals' ? "Qo'shimcha nusxa yo'q" : 'Yangi nusxa'], ['merge', `Birlashtirish (${gain})`], ['replace', i.type === 'globals' ? 'Almashtirish (zaxira olinadi)' : 'Almashtirish (eskisi Savatga)'], ['skip', "O'tkazib yuborish"]].filter(x => !(i.type === 'globals' && x[0] === 'copy')) as [Action, string][]
}
const remove = (id: number) => { entries.value = entries.value.filter(e => e.id !== id) }
const summary = (p: Entry['preview']) => (p ? `${p.folders} papka, ${p.requests} so'rov${p.variables ? `, ${p.variables} o'zgaruvchi` : ''}` : '')
const itemSummary = (i: Item) => (i.type === 'collection' ? `${i.stats.folders ?? 0} papka, ${i.stats.requests ?? 0} so'rov${i.stats.variables ? `, ${i.stats.variables} o'zgaruvchi` : ''}${i.stats.examples ? `, ${i.stats.examples} namuna` : ''}${i.stats.scripts ? `, ${i.stats.scripts} skript` : ''}` : `${i.stats.variables ?? 0} o'zgaruvchi`)
const TYPE_LABEL: Record<string, string> = { collection: 'Collection', environment: 'Muhit', globals: 'Globals' }
defineExpose({ add })
</script>

<template>
  <Dialog title="Import" testid="import-dialog" width="min(720px,92vw)" @close="emit('close')">
    <div class="seg-group" role="tablist" aria-label="Manba" style="margin-bottom:12px">
      <button v-for="t in ([['file', 'Fayl / papka'], ['text', 'Matn'], ['url', 'URL']] as const)" :key="t[0]" class="seg" role="tab" :aria-selected="tab === t[0]" :class="{ on: tab === t[0] }" :data-tab="t[0]" @click="tab = t[0]">{{ t[1] }}</button>
    </div>
    <div v-if="tab === 'file'" class="imp-drop" :class="{ over }" data-testid="import-drop" @dragover.prevent="over = true" @dragleave="over = false" @drop="onDrop">
      <b>Fayl yoki papkani shu yerga tashlang</b><span class="muted">Postman, OpenAPI/Swagger (JSON, YAML), Insomnia v4, HAR, cURL (.sh/.txt), workspace zaxirasi (.zip)</span>
      <span style="display:flex;gap:8px"><button data-autofocus data-testid="import-pick-file" @click="fileEl?.click()">Fayl tanlash…</button><button data-testid="import-pick-dir" @click="dirEl?.click()">Papka tanlash…</button></span>
      <input ref="fileEl" type="file" multiple accept=".json,.txt,.yaml,.yml,.har,.sh,.curl,.zip" hidden data-testid="import-dlg-file" @change="onFiles(($event.target as HTMLInputElement).files)">
      <input ref="dirEl" type="file" webkitdirectory multiple hidden @change="onFiles(($event.target as HTMLInputElement).files)">
    </div>
    <div v-else-if="tab === 'text'" class="dlg-field">
      <span>cURL (bir nechta ham), Postman, OpenAPI (JSON/YAML), Insomnia yoki HAR matnini joylashtiring</span>
      <textarea v-model="text" rows="8" style="width:100%;height:auto;padding:8px;font-family:var(--font-mono)" data-testid="import-text" data-autofocus placeholder="curl -X POST 'https://…' -H '…'  yoki  { &quot;info&quot;: … }" />
      <span><button :disabled="!text.trim()" data-testid="import-add-text" @click="addText">Qo'shish</button></span>
    </div>
    <div v-else class="dlg-field">
      <span>Postman collection, OpenAPI/Swagger yoki boshqa import hujjati manzili</span>
      <span style="display:flex;gap:8px"><input v-model="url" style="flex:1" placeholder="https://example.com/openapi.json" data-testid="import-url" data-autofocus @keydown.enter="addUrl"><button :disabled="busy || !url.trim()" data-testid="import-add-url" @click="addUrl">Yuklash</button></span>
    </div>
    <ul v-if="entries.length" class="imp-list" data-testid="import-list">
      <li v-for="e in entries" :key="e.id" :class="{ bad: e.error, multi: e.items && e.items.length > 0 }" data-testid="import-entry">
        <div class="imp-head">
          <span class="imp-name"><b>{{ e.preview ? e.preview.name : e.name }}</b><small class="muted">{{ e.name }}</small></span>
          <span v-if="e.error" class="imp-err" role="alert" data-testid="import-error">{{ e.error }}</span>
          <span v-else class="imp-sum" data-testid="import-preview"><span class="badge">{{ e.preview?.kind }}</span> {{ summary(e.preview) }}</span>
          <button class="ib" aria-label="Olib tashlash" @click="remove(e.id)">×</button>
        </div>
        <ul v-if="e.items && (e.items.length > 1 || e.items.some(i => i.conflict))" class="imp-items" data-testid="import-items">
          <li v-for="(i, k) in e.items" :key="k" data-testid="import-item" :class="{ skipped: i.action === 'skip' }">
            <span class="badge">{{ TYPE_LABEL[i.type] }}</span>
            <span class="imp-iname"><b>{{ i.name }}</b><small class="muted">{{ itemSummary(i) }}</small></span>
            <label v-if="i.conflict" class="imp-conflict"><span class="warn-txt" data-testid="import-conflict">Shu nomli mavjud</span>
              <select v-model="i.action" :aria-label="`«${i.name}» uchun amal`" data-testid="import-action"><option v-for="o in ACTION_LABEL(i)" :key="o[0]" :value="o[0]">{{ o[1] }}</option></select></label>
            <label v-else class="imp-conflict"><input type="checkbox" :checked="i.action !== 'skip'" :aria-label="`«${i.name}» ni import qilish`" data-testid="import-item-on" @change="i.action = ($event.target as HTMLInputElement).checked ? i.default_action : 'skip'"></label>
          </li>
        </ul>
        <ul v-if="e.warnings?.length" class="imp-warn" data-testid="import-warnings"><li v-for="w in e.warnings.slice(0, 5)" :key="w">⚠ {{ w }}</li><li v-if="e.warnings.length > 5" class="muted">… yana {{ e.warnings.length - 5 }} ta ogohlantirish</li></ul>
      </li>
    </ul>
    <p v-if="valid.length" class="imp-total" data-testid="import-total">Jami: <b>{{ total.folders }}</b> papka, <b>{{ total.requests }}</b> so'rov<template v-if="total.variables">, <b>{{ total.variables }}</b> o'zgaruvchi</template> import qilinadi.</p>
    <template #footer>
      <button @click="emit('close')">Bekor qilish</button>
      <button class="primary" data-testid="import-confirm" :disabled="busy || !activeItems" @click="run">Import ({{ activeItems }})</button>
    </template>
  </Dialog>
</template>
