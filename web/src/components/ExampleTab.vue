<script setup lang="ts">
/** Example tahriri (Postman `item.response[]`): nom, status, headers, body. ref: "cid:requestId:exampleId". */
import { computed, watch } from 'vue'
import CodeEditor from './CodeEditor.vue'
import KvTable from './KvTable.vue'
import { askConfirm, showToast } from '../lib/ui'
import { useTabs, type Tab } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { examplesOf, exampleSnapshot, formFromExample, saveExampleTab, STATUS_TEXT, type ExampleForm } from '../lib/examples'
import { openRequest } from '../lib/actions'

const props = defineProps<{ tab: Tab }>()
const tabs = useTabs(), tree = useTree()
const [cid, reqId, exId] = (props.tab.ref ?? '').split(':')
props.tab.state ??= {}
const item = computed<any>(() => tree.findItem(cid, reqId))
const example = computed(() => examplesOf(item.value).find(e => e.id === exId) ?? null)
// forma tab holatida (`tab.state.form`): boshqa tabga o'tib qaytganda saqlanmagan tahrir yo'qolmaydi
if (!props.tab.state.form && example.value) { props.tab.state.form = formFromExample(example.value); props.tab.state.saved = exampleSnapshot(props.tab.state.form) }
const form = computed<ExampleForm | null>(() => (props.tab.state?.form as ExampleForm) ?? null)
const dirty = computed(() => !!form.value && exampleSnapshot(form.value) !== props.tab.state!.saved)
watch(dirty, d => { if (d) tabs.touch(props.tab.id) })
const lang = computed(() => (form.value?.lang === 'json' ? 'json' : form.value?.lang === 'html' ? 'html' : 'raw') as 'json' | 'html' | 'raw')
const orig = computed(() => { const o = example.value?.originalRequest; return o ? { method: o.method ?? 'GET', url: typeof o.url === 'string' ? o.url : o.url?.raw ?? '' } : null })

async function save() { try { if (await saveExampleTab(props.tab)) showToast('Namuna saqlandi', 'success') } catch (e: any) { showToast(e.message, 'error') } }
async function remove() {
  if (!(await askConfirm(`«${form.value!.name}» namunasi o'chirilsinmi?`, "O'chirish"))) return
  await tree.updateItem(cid, reqId, { response: examplesOf(item.value).filter(e => e.id !== exId) })
  tabs.dropRef(props.tab.ref!)
}
const openReq = () => openRequest(cid, reqId, true)
</script>

<template>
  <div v-if="form" class="example-tab scroll" data-testid="example-tab">
    <div class="ex-head">
      <span class="ex-tag" aria-hidden="true">EX</span>
      <input v-model="form.name" class="ex-name" aria-label="Namuna nomi" data-testid="example-name" @input="tabs.touch(tab.id)">
      <span style="flex:1" />
      <button data-testid="example-delete" @click="remove">O'chirish</button>
      <button class="primary" data-testid="example-save" :disabled="!dirty" @click="save">Saqlash</button>
    </div>
    <p v-if="orig" class="muted ex-orig" data-testid="example-orig"><b class="m" :class="'m-' + orig.method">{{ orig.method }}</b> <span>{{ orig.url }}</span> · <button class="linkbtn" data-testid="example-open-request" @click="openReq">«{{ item?.name }}» so'rovini ochish</button></p>
    <div class="ex-grid">
      <label class="bf"><span class="bl">Status kodi</span><input type="number" min="100" max="599" v-model.number="form.code" aria-label="Status kodi" data-testid="example-code" @input="form.status = STATUS_TEXT[Number(form.code)] ?? ''"></label>
      <label class="bf"><span class="bl">Status matni</span><input v-model="form.status" aria-label="Status matni" data-testid="example-status"></label>
      <label class="bf"><span class="bl">Body turi</span><select v-model="form.lang" aria-label="Body turi" data-testid="example-lang"><option value="json">JSON</option><option value="text">Text</option><option value="html">HTML</option><option value="xml">XML</option></select></label>
    </div>
    <h3 class="ex-h">Headers</h3>
    <KvTable :rows="form.headers" testid="example-headers" @change="tabs.touch(tab.id)" />
    <h3 class="ex-h">Body</h3>
    <div class="ex-body"><CodeEditor v-model="form.body" :lang="lang" testid="example-body" label="Namuna body" @update:model-value="tabs.touch(tab.id)" /></div>
  </div>
  <div v-else class="empty" data-testid="example-missing">Namuna topilmadi (o'chirilgan bo'lishi mumkin)</div>
</template>
