<script setup lang="ts">
import { ref, watch } from 'vue'
import { useWorkspace } from '../stores/workspace'
import { useTabs, type Tab } from '../stores/tabs'
import type { Environment } from '../types/model'
import { showToast } from '../lib/ui'
import { ensureGhost } from '../lib/ghost'
import { KINDS } from '../lib/envkind'
import type { EnvKind } from '../types/model'

const props = defineProps<{ tab: Tab }>()
const ws = useWorkspace(), tabs = useTabs()
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
async function save() {
  try { if (isGlobals) await ws.saveGlobals(env.value!.values.filter(v => v.key)); else await ws.saveEnv({ ...env.value!, values: env.value!.values.filter(v => v.key) }); tabs.markSaved(props.tab.id, { title: env.value!.name }) }
  catch (e: any) { showToast(e.message, 'error') }     // 409: boshqa tab/jarayon o'zgartirgan — ustidan yozilmaydi
}
</script>

<template>
  <div v-if="env" class="page" data-testid="env-tab">
    <p><input v-model="env.name" aria-label="Muhit nomi" data-testid="env-name" :disabled="isGlobals" @input="tabs.touch(tab.id)"> <button class="primary" data-testid="env-save" @click="save">Saqlash</button>
      <button v-if="!isGlobals" data-testid="env-activate" @click="ws.setActive(ws.activeEnvId === env!.id ? null : env!.id)">{{ ws.activeEnvId === env.id ? 'Faol ✓' : 'Faollashtirish' }}</button></p>
    <div v-if="!isGlobals" class="kind-chips" data-testid="env-kind" role="group" aria-label="Muhit turi"><span class="muted" style="font-weight:600;font-size:12px">Turi:</span>
      <button v-for="k in KINDS" :key="k.id" class="chip" :class="['kind-' + k.id, { on: env.kind === k.id }]" :aria-pressed="env.kind === k.id" :data-kind="k.id" @click="setKind(k.id)"><span class="kind-dot" :class="'kind-' + k.id" />{{ k.label }}</button>
      <label class="confirm"><input type="checkbox" data-testid="env-confirm-writes" :checked="confirmOn()" @change="setConfirm(($event.target as HTMLInputElement).checked)">POST / PUT / PATCH / DELETE yuborishdan oldin tasdiq so'ralsin</label>
    </div>
    <div class="kv-wrap">
      <table class="kv" style="table-layout:fixed">
        <colgroup><col style="width:30px"><col><col><col style="width:100px"><col style="width:30px"></colgroup>
        <thead><tr><th /><th scope="col">Kalit</th><th scope="col">Qiymat</th><th scope="col">Turi</th><th /></tr></thead>
        <tbody>
          <tr v-for="(v, i) in env.values" :key="i" :class="{ ghost: isGhost(i) }" :data-ghost="isGhost(i) || undefined">
            <td style="text-align:center"><input v-if="!isGhost(i)" type="checkbox" aria-label="Yoqish" v-model="v.enabled" @change="tabs.touch(tab.id)"></td>
            <td><input v-model="v.key" placeholder="O'zgaruvchi" aria-label="Kalit" data-testid="env-key" @input="touchRow"></td>
            <td><input v-model="v.value" :type="v.type === 'secret' ? 'password' : 'text'" placeholder="Qiymat" aria-label="Qiymat" data-testid="env-val" @input="touchRow"></td>
            <td><select v-if="!isGhost(i)" v-model="v.type" aria-label="Turi" @change="tabs.touch(tab.id)"><option value="default">default</option><option value="secret">secret</option></select></td>
            <td><button v-if="!isGhost(i)" class="ghost" aria-label="O'zgaruvchini o'chirish" @click="removeRow(i)">×</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div v-else class="empty">Muhit topilmadi</div>
</template>
