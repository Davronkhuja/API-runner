<script setup lang="ts">
/** Collection yoki papka sozlamalari: Auth, Variables, Scripts, Description (ref: "cid" yoki "cid:folderId"). */
import { computed, ref, watch } from 'vue'
import { put } from '../api/client'
import { useTree } from '../stores/tree'
import { useTabs, type Tab } from '../stores/tabs'
import { authFromPm, authToPm, type AuthDraft } from '../lib/auth'
import { showToast } from '../lib/ui'
import AuthEditor from './AuthEditor.vue'
import VarsTable from './VarsTable.vue'

const props = defineProps<{ tab: Tab }>()
const tree = useTree(), tabs = useTabs()
const [cid, fid] = (props.tab.ref ?? '').split(':')
const isFolder = !!fid
const node = computed<any>(() => (isFolder ? tree.findItem(cid, fid) : tree.cols[cid]))
const meta = computed(() => tree.metas.find(m => m.id === cid))
const section = ref('auth')

interface Form { auth: AuthDraft; vars: any[]; pre: string; test: string; description: string }
const form = ref<Form | null>(null)
const execOf = (ev: any[] | undefined, listen: string) => ((ev ?? []).find(e => e.listen === listen)?.script?.exec ?? []).join('\n')
function load() {
  const n = node.value
  if (!n) { form.value = null; return }
  form.value = {
    auth: authFromPm(n.auth), vars: JSON.parse(JSON.stringify(n.variable ?? [])).map((v: any) => ({ type: 'default', ...v })),
    pre: execOf(n.event, 'prerequest'), test: execOf(n.event, 'test'), description: n['x-apirunner']?.description ?? '',
  }
}
watch(() => props.tab.ref, load, { immediate: true })
const touch = () => tabs.touch(props.tab.id)

function eventsFrom(f: Form) {
  const mk = (listen: string, src: string) => (src.trim() ? [{ listen, script: { type: 'text/javascript', exec: src.split('\n') } }] : [])
  return [...mk('prerequest', f.pre), ...mk('test', f.test)]
}
async function save() {
  const f = form.value!
  const patch: any = { variable: f.vars.filter(v => v.key), event: eventsFrom(f), auth: authToPm(f.auth) ?? null }
  try {
    if (isFolder) {
      await tree.updateItem(cid, fid, { ...patch, 'x-apirunner': { ...(node.value['x-apirunner'] ?? {}), description: f.description } })
    } else {
      const col = JSON.parse(JSON.stringify(tree.cols[cid]))
      Object.assign(col, patch, { 'x-apirunner': { ...(col['x-apirunner'] ?? {}), description: f.description } })
      await put(`/api/collections/${cid}`, col)
      await tree.reloadCollection(cid)
    }
    tabs.markSaved(props.tab.id, { title: props.tab.title })
    showToast('Saqlandi', 'success')
  } catch (e: any) { showToast(e.message, 'error') }
}
</script>

<template>
  <div v-if="form" class="editor" :data-testid="isFolder ? 'tab-folder' : 'tab-collection'">
    <div style="display:flex;gap:10px;align-items:center">
      <h3 style="flex:1">{{ node?.name ?? node?.info?.name }}</h3>
      <span class="muted" v-if="!isFolder">{{ meta?.requests ?? 0 }} ta so'rov</span>
      <button class="primary" data-testid="scope-save" :disabled="!tab.dirty" @click="save">Saqlash</button>
    </div>
    <div class="sections" data-testid="scope-sections">
      <button v-for="s in ['auth', 'vars', 'scripts', 'desc']" :key="s" :class="{ on: section === s }" :data-scope-section="s" @click="section = s">
        {{ { auth: 'Auth', vars: 'Variables', scripts: 'Scripts', desc: 'Tavsif' }[s] }}
      </button>
    </div>
    <div style="padding-top:10px">
      <AuthEditor v-if="section === 'auth'" :auth="form.auth" :allow-inherit="isFolder" :scope-ref="props.tab.ref" @change="touch" />
      <VarsTable v-else-if="section === 'vars'" :rows="form.vars" testid="scope-vars" @change="touch" />
      <div v-else-if="section === 'scripts'">
        <p class="muted">Pre-request / Tests skriptlari saqlanadi; bajarilishi Bosqich 3 da.</p>
        <b>Pre-request</b><textarea v-model="form.pre" data-testid="scope-pre" style="width:100%;height:110px;font-family:ui-monospace,monospace" @input="touch" />
        <b>Tests</b><textarea v-model="form.test" data-testid="scope-test" style="width:100%;height:110px;font-family:ui-monospace,monospace" @input="touch" />
      </div>
      <textarea v-else v-model="form.description" data-testid="scope-desc" placeholder="Tavsif (Markdown)" style="width:100%;height:200px" @input="touch" />
    </div>
  </div>
  <div v-else class="empty">Topilmadi</div>
</template>
