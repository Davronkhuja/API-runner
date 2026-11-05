<script setup lang="ts">
/** "Set as variable": so'rov muharririda matn belgilanganda {{ }} tugmasi chiqadi; dialog nom/scope/qiymatni so'raydi va belgilangan joyni {{nom}} ga almashtiradi. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { EditorView } from '@codemirror/view'
import Dialog from './Dialog.vue'
import { get, put } from '../api/client'
import { useTabs } from '../stores/tabs'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { showToast } from '../lib/ui'
import { scopedVars } from '../lib/scope'
import { suggestVarName, upsertVar, validateVarName, type VarScope } from '../lib/setvar'

interface Sel { text: string; x: number; y: number; apply: (name: string) => boolean; hint: string }
const btn = ref<Sel | null>(null)
const dlg = ref<Sel | null>(null)
const tabs = useTabs(), tree = useTree(), ws = useWorkspace()
const name = ref(''), scope = ref<VarScope>('environment'), value = ref(''), busy = ref(false)
const ref_ = computed(() => tabs.active?.ref ?? null)
const [cid, itemId] = [computed(() => (ref_.value ?? '').split(':')[0]), computed(() => (ref_.value ?? '').split(':')[1])]
void itemId
const scopes = computed(() => [
  ...(ws.activeEnv ? [{ id: 'environment' as VarScope, label: `Environment: ${ws.activeEnv.name}` }] : []),
  { id: 'globals' as VarScope, label: 'Globals' },
  ...(cid.value && tree.cols[cid.value] ? [{ id: 'collection' as VarScope, label: `Collection: ${tree.cols[cid.value].info.name}` }] : []),
])
const tpl = computed(() => '{' + '{' + (name.value || 'nom') + '}' + '}')
const err = computed(() => validateVarName(name.value))
const existing = computed(() => { const k = scopedVars(ref_.value)[name.value]; return k && ((scope.value === 'environment' && k.scope === 'Environment') || (scope.value === 'globals' && k.scope === 'Globals') || (scope.value === 'collection' && k.scope === 'Collection')) })

let t: ReturnType<typeof setTimeout> | undefined
function scan() {
  clearTimeout(t)
  t = setTimeout(() => {
    if (dlg.value) return
    btn.value = detect()
  }, 60)
}
function detect(): Sel | null {
  const a = document.activeElement as HTMLElement | null
  if (!a || !a.closest('[data-testid=request-editor]')) return null
  if ((a instanceof HTMLInputElement && /^(text|search|url|)$/.test(a.type)) || a instanceof HTMLTextAreaElement) {
    if (a.readOnly || a.disabled) return null
    const s = a.selectionStart ?? 0, e = a.selectionEnd ?? 0, text = a.value.slice(s, e)
    if (!ok(text)) return null
    const r = a.getBoundingClientRect()
    return { text, x: r.right - 150, y: r.top - 30, hint: a.getAttribute('aria-label') === 'Qiymat' ? (a.closest('tr')?.querySelector<HTMLInputElement>('[data-cell$=":0"]')?.value ?? '') : '',
      apply: n => { if (a.value.slice(s, e) !== text) return false; a.setRangeText(`{{${n}}}`, s, e, 'end'); a.dispatchEvent(new Event('input', { bubbles: true })); return true } }
  }
  const ed = a.closest('.cm-editor') as HTMLElement | null
  const view = ed ? EditorView.findFromDOM(ed) : null
  if (view && !view.state.readOnly) {
    const m = view.state.selection.main
    if (m.empty) return null
    const text = view.state.doc.sliceString(m.from, m.to)
    if (!ok(text)) return null
    const c = view.coordsAtPos(m.to)
    if (!c) return null
    return { text, x: Math.min(c.left, window.innerWidth - 170), y: c.top - 32, hint: '',
      apply: n => { if (view.state.doc.sliceString(m.from, m.to) !== text) return false; view.dispatch({ changes: { from: m.from, to: m.to, insert: `{{${n}}}` }, selection: { anchor: m.from + n.length + 4 } }); return true } }
  }
  return null
}
const ok = (s: string) => s.trim().length > 0 && s.length <= 300 && !/[\r\n]/.test(s) && !s.includes('{{')

function open() {
  const s = btn.value!
  dlg.value = s; btn.value = null
  name.value = suggestVarName(s.text, s.hint); value.value = s.text
  scope.value = scopes.value[0].id
}
function close() { dlg.value = null }

async function save() {
  if (err.value || busy.value || !dlg.value) return
  busy.value = true
  const key = name.value, val = value.value
  try {
    const row = (k: string, v: string) => ({ key: k, value: v, enabled: true, type: 'default' as const })
    if (scope.value === 'environment' && ws.activeEnv) {
      const env = JSON.parse(JSON.stringify(ws.activeEnv))
      env.values = upsertVar(env.values, key, val, row).rows
      await ws.saveEnv(env)
    } else if (scope.value === 'globals') {
      await ws.saveGlobals(upsertVar(JSON.parse(JSON.stringify(ws.globals)), key, val, row).rows as any)
    } else {
      const c = await get(`/api/collections/${cid.value}`)
      c.variable = upsertVar(c.variable ?? [], key, val, (k, v) => ({ key: k, value: v, type: 'default' })).rows
      await put(`/api/collections/${cid.value}`, c)
      await tree.reloadCollection(cid.value)
    }
    const replaced = dlg.value.apply(key)
    showToast(replaced ? `{{${key}}} yaratildi` : `{{${key}}} yaratildi, lekin matn o'zgargan — qo'lda almashtiring`, replaced ? 'success' : 'warn')
    close()
  } catch (e: any) { showToast(e.message, 'error') } finally { busy.value = false }
}

onMounted(() => document.addEventListener('selectionchange', scan))
onBeforeUnmount(() => { document.removeEventListener('selectionchange', scan); clearTimeout(t) })
</script>

<template>
  <button v-if="btn && !dlg" class="setvar-btn" data-testid="set-var-btn" type="button" title="Belgilangan matndan o'zgaruvchi yaratish" :style="{ left: Math.max(8, btn.x) + 'px', top: Math.max(8, btn.y) + 'px' }" @mousedown.prevent @click="open"><span v-text="'{{ }}'" /> O'zgaruvchi qilish</button>
  <Dialog v-if="dlg" title="O'zgaruvchi yaratish" testid="setvar-dialog" width="480px" @close="close">
    <label class="dlg-field"><span>Nomi</span><input v-model="name" data-testid="setvar-name" data-autofocus style="width:100%" spellcheck="false" @keydown.enter="save"></label>
    <p v-if="err" class="state-error" role="alert" data-testid="setvar-error" style="padding:6px 10px;margin:0 0 var(--sp-3)">{{ err }}</p>
    <label class="dlg-field"><span>Scope</span><select v-model="scope" data-testid="setvar-scope" style="width:100%"><option v-for="s in scopes" :key="s.id" :value="s.id">{{ s.label }}</option></select></label>
    <label class="dlg-field"><span>Qiymati</span><input v-model="value" data-testid="setvar-value" style="width:100%" spellcheck="false" @keydown.enter="save"></label>
    <p class="muted" style="margin:0;font-size:var(--fs-sm)" data-testid="setvar-note">Belgilangan matn <code v-text="tpl" /> bilan almashtiriladi.<template v-if="existing"> <b>Diqqat:</b> bu scope'da «{{ name }}» bor — qiymati yangilanadi.</template></p>
    <template #footer>
      <button @click="close">Bekor qilish</button>
      <button class="primary" data-testid="setvar-ok" :disabled="!!err || busy" @click="save">{{ existing ? 'Yangilash va almashtirish' : 'Yaratish' }}</button>
    </template>
  </Dialog>
</template>
