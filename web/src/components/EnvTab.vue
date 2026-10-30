<script setup lang="ts">
import { ref, watch } from 'vue'
import { useWorkspace } from '../stores/workspace'
import { useTabs, type Tab } from '../stores/tabs'
import type { Environment } from '../types/model'
import { showToast } from '../lib/ui'

const props = defineProps<{ tab: Tab }>()
const ws = useWorkspace(), tabs = useTabs()
const env = ref<Environment | null>(null)
watch(() => [props.tab.ref, ws.environments], () => { env.value = JSON.parse(JSON.stringify(ws.environments.find(e => e.id === props.tab.ref) ?? null)) }, { immediate: true })
const add = () => { env.value!.values.push({ key: '', value: '', enabled: true, type: 'default' }); tabs.touch(props.tab.id) }
async function save() {
  try { await ws.saveEnv(env.value!); tabs.markSaved(props.tab.id, { title: env.value!.name }) }
  catch (e: any) { showToast(e.message, 'error') }     // 409: boshqa tab/jarayon o'zgartirgan — ustidan yozilmaydi
}
</script>

<template>
  <div v-if="env" class="editor" data-testid="env-tab">
    <p><input v-model="env.name" data-testid="env-name" @input="tabs.touch(tab.id)"> <button class="primary" data-testid="env-save" @click="save">Saqlash</button>
      <button data-testid="env-activate" @click="ws.setActive(ws.activeEnvId === env!.id ? null : env!.id)">{{ ws.activeEnvId === env.id ? 'Faol ✓' : 'Faollashtirish' }}</button></p>
    <table class="kv"><tbody>
      <tr v-for="(v, i) in env.values" :key="i">
        <td style="width:22px"><input type="checkbox" v-model="v.enabled" @change="tabs.touch(tab.id)"></td>
        <td><input v-model="v.key" placeholder="O'zgaruvchi" data-testid="env-key" @input="tabs.touch(tab.id)"></td>
        <td><input v-model="v.value" :type="v.type === 'secret' ? 'password' : 'text'" placeholder="Qiymat" data-testid="env-val" @input="tabs.touch(tab.id)"></td>
        <td style="width:90px"><select v-model="v.type" @change="tabs.touch(tab.id)"><option value="default">default</option><option value="secret">secret</option></select></td>
        <td style="width:24px"><button class="ghost" @click="env!.values.splice(i, 1); tabs.touch(tab.id)">×</button></td>
      </tr>
    </tbody></table>
    <button data-testid="env-add" @click="add">＋ O'zgaruvchi</button>
  </div>
  <div v-else class="empty">Muhit topilmadi</div>
</template>
