<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useWorkspace } from '../stores/workspace'
import { useTabs, type Tab } from '../stores/tabs'
import type { Environment } from '../types/model'
import { showToast } from '../lib/ui'
import { ensureGhost } from '../lib/ghost'
import { useTree } from '../stores/tree'
import { requestsIn } from '../lib/nodes'
import { downloadFrom } from '../lib/exporter'
import Icon from './Icon.vue'
import { KINDS } from '../lib/envkind'
import type { EnvKind } from '../types/model'

const props = defineProps<{ tab: Tab }>()
const ws = useWorkspace(), tabs = useTabs(), tree = useTree()
const env = ref<Environment | null>(null)
const isGlobals = props.tab.ref === 'globals'
// Oxirida doim bitta ghost qator (saqlanmaydi, o'zi dirty yaratmaydi)
const blank = (v: { key: string; value: string }) => !v.key && !v.value
const make = () => ({ key: '', value: '', enabled: true, type: 'default' as const })
watch(() => [props.tab.ref, ws.environments, ws.globals], () => {
  env.value = JSON.parse(JSON.stringify(isGlobals ? { id: 'globals', name: 'Globals', values: ws.globals } : (ws.environments.find(e => e.id === props.tab.ref) ?? null)))
  if (env.value) ensureGhost(env.value.values, blank, make)
}, { immediate: true })
const isGhost = (i: number) => !!env.value && i === env.value.values.length - 1 && blank(env.value.values[i])
const touchRow = () => { ensureGhost(env.value!.values, blank, make); tabs.touch(props.tab.id) }
const removeRow = (i: number) => { env.value!.values.splice(i, 1); ensureGhost(env.value!.values, blank, make); tabs.touch(props.tab.id) }
function setKind(k: EnvKind) {
  if (!env.value) return
  env.value.kind = env.value.kind === k ? '' : k
  if (env.value.kind === 'prod' && env.value.confirm_writes === undefined) env.value.confirm_writes = true
  tabs.touch(props.tab.id)
}
const confirmOn = (): boolean => env.value?.confirm_writes ?? env.value?.kind === 'prod'
function setConfirm(v: boolean) { if (env.value) { env.value.confirm_writes = v; tabs.touch(props.tab.id) } }
// ── Boshlang'ich / Joriy qiymatlar ──
const shown = ref<Record<string, boolean>>({})
const masked = (v: { type: string; key: string }) => v.type === 'secret' && !shown.value[v.key]
function setCurrent(v: { current?: string | null }, val: string) { v.current = val === '' ? null : val; tabs.touch(props.tab.id) }
const hasCurrent = computed(() => !!env.value?.values.some(v => v.key && v.current != null))
function currentToInitial() { for (const v of env.value!.values) if (v.key && v.current != null) { v.value = v.current; v.current = null } tabs.touch(props.tab.id) }
function resetCurrent() { for (const v of env.value!.values) v.current = null; tabs.touch(props.tab.id) }
const usedBy = computed(() => {
  const keys = (env.value?.values ?? []).map(v => v.key).filter(Boolean)
  if (!keys.length) return 0
  let n = 0
  for (const c of Object.values(tree.cols)) for (const r of requestsIn(c.item)) { const t = JSON.stringify(r.item.request); if (keys.some(k => t.includes('{{' + k + '}}'))) n++ }
  return n
})
async function duplicate() {
  try {
    const id = await ws.createEnv(env.value!.name + ' Copy')
    await ws.saveEnv({ id, name: env.value!.name + ' Copy', values: env.value!.values.filter(v => v.key).map(v => ({ key: v.key, value: v.value, enabled: v.enabled, type: v.type })), kind: env.value!.kind, confirm_writes: env.value!.confirm_writes } as any)
    tabs.open('environment', id, env.value!.name + ' Copy', { permanent: true })
  } catch (e: any) { showToast(e.message, 'error') }
}
function exportEnv() {
  const e = env.value!
  const body = JSON.stringify({ id: e.id, name: e.name, values: e.values.filter(v => v.key).map(v => ({ key: v.key, value: v.value, type: v.type, enabled: v.enabled })), _postman_variable_scope: 'environment' }, null, 2)
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([body], { type: 'application/json' })); a.download = `${e.name}.postman_environment.json`; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
async function save() {
  try { if (isGlobals) await ws.saveGlobals(env.value!.values.filter(v => v.key)); else await ws.saveEnv({ ...env.value!, values: env.value!.values.filter(v => v.key) }); tabs.markSaved(props.tab.id, { title: env.value!.name }) }
  catch (e: any) { showToast(e.message, 'error') }     // 409: boshqa tab/jarayon o'zgartirgan — ustidan yozilmaydi
}
</script>

<template>
  <div v-if="env" class="page env-page" data-testid="env-tab">
    <div class="env-head">
      <input v-model="env.name" class="env-title" aria-label="Muhit nomi" data-testid="env-name" :disabled="isGlobals" @input="tabs.touch(tab.id)">
      <span v-if="!isGlobals && ws.activeEnvId === env.id" class="env-active" data-testid="env-active-badge">FAOL</span>
      <span style="flex:1" />
      <template v-if="!isGlobals">
        <button data-testid="env-duplicate" @click="duplicate">Dublikat</button>
        <button data-testid="env-export" @click="exportEnv">Eksport</button>
      </template>
      <button class="primary" data-testid="env-save" @click="save">Saqlash</button>
      <button v-if="!isGlobals" data-testid="env-activate" @click="ws.setActive(ws.activeEnvId === env!.id ? null : env!.id)">{{ ws.activeEnvId === env.id ? 'Faol ✓' : 'Faol qilish' }}</button>
    </div>
    <div v-if="!isGlobals" class="kind-chips" data-testid="env-kind" role="group" aria-label="Muhit turi"><span class="muted" style="font-weight:600;font-size:var(--fs-sm)">Turi:</span>
      <button v-for="k in KINDS" :key="k.id" class="chip" :class="['kind-' + k.id, { on: env.kind === k.id }]" :aria-pressed="env.kind === k.id" :data-kind="k.id" @click="setKind(k.id)"><span class="kind-dot" :class="'kind-' + k.id" />{{ k.label }}</button>
      <label class="confirm"><input type="checkbox" data-testid="env-confirm-writes" :checked="confirmOn()" @change="setConfirm(($event.target as HTMLInputElement).checked)">POST / PUT / PATCH / DELETE yuborishdan oldin tasdiq so'ralsin</label>
    </div>
    <div class="env-note" data-testid="env-note"><Icon name="alert" :size="16" /><span><b>Boshlang'ich qiymat</b> eksport va zaxiraga tushadi. <b>Joriy qiymat</b> faqat shu kompyuterda ishlatiladi: tokenlar va parollarni shu ustunga yozing. Skriptlar faqat joriy qiymatni o'zgartiradi.</span></div>
    <div class="kv-wrap">
      <table class="kv" style="table-layout:fixed" data-testid="env-table">
        <colgroup><col style="width:30px"><col style="width:22%"><col style="width:96px"><col><col><col style="width:64px"></colgroup>
        <thead><tr><th /><th scope="col">O'zgaruvchi</th><th scope="col">Turi</th><th scope="col">Boshlang'ich qiymat</th><th scope="col">Joriy qiymat</th><th /></tr></thead>
        <tbody>
          <tr v-for="(v, i) in env.values" :key="i" :class="{ ghost: isGhost(i) }" :data-ghost="isGhost(i) || undefined">
            <td style="text-align:center"><input v-if="!isGhost(i)" type="checkbox" aria-label="Yoqish" v-model="v.enabled" @change="tabs.touch(tab.id)"></td>
            <td><input v-model="v.key" placeholder="O'zgaruvchi" aria-label="Kalit" data-testid="env-key" @input="touchRow"></td>
            <td><select v-if="!isGhost(i)" v-model="v.type" aria-label="Turi" data-testid="env-type" @change="tabs.touch(tab.id)"><option value="default">default</option><option value="secret">secret</option></select></td>
            <td><input v-model="v.value" :type="masked(v) ? 'password' : 'text'" placeholder="Qiymat" aria-label="Boshlang'ich qiymat" data-testid="env-val" @input="touchRow"></td>
            <td><input :value="v.current ?? ''" :type="masked(v) ? 'password' : 'text'" :placeholder="isGhost(i) ? 'Qiymat' : (v.value ? '= boshlang\'ich' : 'Qiymat')" aria-label="Joriy qiymat" data-testid="env-cur" :class="{ differs: v.current != null && v.current !== v.value }" @input="setCurrent(v, ($event.target as HTMLInputElement).value)"></td>
            <td style="white-space:nowrap;text-align:right">
              <button v-if="v.type === 'secret' && !isGhost(i)" class="ghost" :aria-label="shown[v.key] ? 'Qiymatni yashirish' : 'Qiymatni ko\'rsatish'" data-testid="env-reveal" @click="shown[v.key] = !shown[v.key]"><Icon name="eye" :size="15" /></button>
              <button v-if="!isGhost(i)" class="ghost" aria-label="O'zgaruvchini o'chirish" @click="removeRow(i)">×</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="env-foot">
      <button data-testid="env-cur-to-init" :disabled="!hasCurrent" @click="currentToInitial">Joriy → boshlang'ich (hammasi)</button>
      <button data-testid="env-cur-reset" :disabled="!hasCurrent" @click="resetCurrent">Joriy qiymatlarni tiklash</button>
      <button data-testid="env-export-postman" title="Postman formati: faqat boshlang'ich qiymatlar, maxfiylar bo'sh (saqlangan holat)" @click="downloadFrom(isGlobals ? '/api/globals/export' : `/api/environments/${env!.id}/export`)"><Icon name="download" :size="14" />Eksport (Postman)</button>
      <span style="flex:1" />
      <span class="muted" data-testid="env-used-by">{{ isGlobals ? 'Globals barcha muhitlarda amal qiladi' : `Bu muhitni ${usedBy} ta so'rov ishlatadi` }}</span>
    </div>
  </div>
  <div v-else class="empty">Muhit topilmadi</div>
</template>
