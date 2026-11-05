<script setup lang="ts">
/** Import dialogi (Postman uslubida): fayl/papka sudrab tashlash yoki tanlash, matn joylashtirish (cURL, Postman JSON, OpenAPI), URL'dan import; natija oldindan ko'rsatiladi va tasdiqlanadi. */
import { computed, reactive, ref } from 'vue'
import Dialog from './Dialog.vue'
import { post } from '../api/client'
import { useTree } from '../stores/tree'
import { useTabs } from '../stores/tabs'
import { applyCurlToDraft, parseCurl } from '../lib/curl'
import { showToast } from '../lib/ui'

const emit = defineEmits<{ close: [] }>()
const tree = useTree(), tabs = useTabs()
interface Entry { id: number; name: string; content: string; curl?: boolean; preview?: { kind: string; name: string; folders: number; requests: number; variables: number }; error?: string }
const entries = ref<Entry[]>([])
const tab = ref<'file' | 'text' | 'url'>('file')
const text = ref(''), url = ref(''), busy = ref(false), over = ref(false)
const fileEl = ref<HTMLInputElement>(), dirEl = ref<HTMLInputElement>()
let seq = 0

async function add(name: string, content: string) {
  const e = reactive<Entry>({ id: ++seq, name, content })          // reaktiv: preview keyin to'ldiriladi
  entries.value.push(e)
  const c = parseCurl(content)
  if (c && /^\s*curl\b/i.test(content)) { e.curl = true; e.preview = { kind: 'cURL', name: `${c.method} ${c.url}`.slice(0, 80), folders: 0, requests: 1, variables: 0 }; return }
  try { e.preview = (await post('/api/import', { content, dry_run: true })) as any } catch (err: any) { e.error = err.message }
}
async function onFiles(files: FileList | File[] | null) {
  for (const f of [...(files ?? [])]) { if (/\.(json|txt|curl|ya?ml)$/i.test(f.name) || f.type.includes('json')) await add(f.name, await f.text()) }
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
const total = computed(() => valid.value.reduce((a, e) => ({ folders: a.folders + e.preview!.folders, requests: a.requests + e.preview!.requests, variables: a.variables + e.preview!.variables }), { folders: 0, requests: 0, variables: 0 }))
async function run() {
  busy.value = true
  let ok = 0
  try {
    for (const e of valid.value) {
      if (e.curl) { const t = tabs.openNew(); applyCurlToDraft(t.draft!, parseCurl(e.content)!); tabs.touch(t.id) }
      else await post('/api/import', { content: e.content })
      ok++
    }
    await tree.load()
    showToast(`Import qilindi: ${ok} ta manba`, 'success')
    emit('close')
  } catch (err: any) { showToast(err.message, 'error') } finally { busy.value = false }
}
const remove = (id: number) => { entries.value = entries.value.filter(e => e.id !== id) }
const summary = (p: Entry['preview']) => (p ? `${p.folders} papka, ${p.requests} so'rov${p.variables ? `, ${p.variables} o'zgaruvchi` : ''}` : '')
defineExpose({ add })
</script>

<template>
  <Dialog title="Import" testid="import-dialog" width="min(720px,92vw)" @close="emit('close')">
    <div class="seg-group" role="tablist" aria-label="Manba" style="margin-bottom:12px">
      <button v-for="t in ([['file', 'Fayl / papka'], ['text', 'Matn'], ['url', 'URL']] as const)" :key="t[0]" class="seg" role="tab" :aria-selected="tab === t[0]" :class="{ on: tab === t[0] }" :data-tab="t[0]" @click="tab = t[0]">{{ t[1] }}</button>
    </div>
    <div v-if="tab === 'file'" class="imp-drop" :class="{ over }" data-testid="import-drop" @dragover.prevent="over = true" @dragleave="over = false" @drop="onDrop">
      <b>Fayl yoki papkani shu yerga tashlang</b><span class="muted">Postman collection / OpenAPI (.json)</span>
      <span style="display:flex;gap:8px"><button data-autofocus data-testid="import-pick-file" @click="fileEl?.click()">Fayl tanlash…</button><button data-testid="import-pick-dir" @click="dirEl?.click()">Papka tanlash…</button></span>
      <input ref="fileEl" type="file" multiple accept=".json,.txt" hidden data-testid="import-dlg-file" @change="onFiles(($event.target as HTMLInputElement).files)">
      <input ref="dirEl" type="file" webkitdirectory multiple hidden @change="onFiles(($event.target as HTMLInputElement).files)">
    </div>
    <div v-else-if="tab === 'text'" class="dlg-field">
      <span>cURL, Postman JSON yoki OpenAPI matnini joylashtiring</span>
      <textarea v-model="text" rows="8" style="width:100%;height:auto;padding:8px;font-family:var(--font-mono)" data-testid="import-text" data-autofocus placeholder="curl -X POST 'https://…' -H '…'  yoki  { &quot;info&quot;: … }" />
      <span><button :disabled="!text.trim()" data-testid="import-add-text" @click="addText">Qo'shish</button></span>
    </div>
    <div v-else class="dlg-field">
      <span>Postman collection yoki OpenAPI hujjati manzili</span>
      <span style="display:flex;gap:8px"><input v-model="url" style="flex:1" placeholder="https://example.com/openapi.json" data-testid="import-url" data-autofocus @keydown.enter="addUrl"><button :disabled="busy || !url.trim()" data-testid="import-add-url" @click="addUrl">Yuklash</button></span>
    </div>
    <ul v-if="entries.length" class="imp-list" data-testid="import-list">
      <li v-for="e in entries" :key="e.id" :class="{ bad: e.error }" data-testid="import-entry">
        <span class="imp-name"><b>{{ e.preview ? e.preview.name : e.name }}</b><small class="muted">{{ e.name }}</small></span>
        <span v-if="e.error" class="imp-err" role="alert" data-testid="import-error">{{ e.error }}</span>
        <span v-else class="imp-sum" data-testid="import-preview"><span class="badge">{{ e.preview?.kind }}</span> {{ summary(e.preview) }}</span>
        <button class="ib" aria-label="Olib tashlash" @click="remove(e.id)">×</button>
      </li>
    </ul>
    <p v-if="valid.length" class="imp-total" data-testid="import-total">Jami: <b>{{ total.folders }}</b> papka, <b>{{ total.requests }}</b> so'rov<template v-if="total.variables">, <b>{{ total.variables }}</b> o'zgaruvchi</template> import qilinadi.</p>
    <template #footer>
      <button @click="emit('close')">Bekor qilish</button>
      <button class="primary" data-testid="import-confirm" :disabled="busy || !valid.length" @click="run">Import ({{ valid.length }})</button>
    </template>
  </Dialog>
</template>
