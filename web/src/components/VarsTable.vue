<script setup lang="ts">
/** Collection/papka/Globals o'zgaruvchilari jadvali (Postman `variable[]` formati: key, value, disabled, type); oxirida doim bitta ghost qator. */
import { onMounted, watch } from 'vue'
import { ensureGhost } from '../lib/ghost'

type Row = { key: string; value: string; disabled?: boolean; type?: string }
const props = defineProps<{ rows: Row[]; testid?: string }>()
const emit = defineEmits<{ change: [] }>()
const blank = (r: Row) => !r.key && !r.value
const make = (): Row => ({ key: '', value: '', type: 'default' })
const isGhost = (i: number) => i === props.rows.length - 1 && blank(props.rows[i])
const sync = () => ensureGhost(props.rows, blank, make)
onMounted(sync)
watch(() => props.rows, sync, { deep: true, flush: 'post' })
const touch = () => { sync(); emit('change') }
const remove = (i: number) => { if (isGhost(i)) return; props.rows.splice(i, 1); sync(); emit('change') }
</script>

<template>
  <div :data-testid="testid ?? 'vars-table'" class="kv-wrap">
    <table class="kv" style="table-layout:fixed">
      <colgroup><col style="width:30px"><col><col><col style="width:100px"><col style="width:30px"></colgroup>
      <thead><tr><th /><th scope="col">Kalit</th><th scope="col">Qiymat</th><th scope="col">Turi</th><th /></tr></thead>
      <tbody>
        <tr v-for="(v, i) in rows" :key="i" :class="{ ghost: isGhost(i) }" :data-ghost="isGhost(i) || undefined">
          <td style="text-align:center"><input v-if="!isGhost(i)" type="checkbox" aria-label="Yoqish" :checked="!v.disabled" @change="v.disabled = !($event.target as HTMLInputElement).checked; emit('change')"></td>
          <td><input v-model="v.key" placeholder="O'zgaruvchi" aria-label="Kalit" data-testid="var-key" @input="touch"></td>
          <td><input v-model="v.value" :type="v.type === 'secret' ? 'password' : 'text'" placeholder="Qiymat" aria-label="Qiymat" data-testid="var-val" @input="touch"></td>
          <td><select v-if="!isGhost(i)" v-model="v.type" aria-label="Turi" data-testid="var-type" @change="emit('change')"><option value="default">default</option><option value="secret">secret</option></select></td>
          <td><button v-if="!isGhost(i)" class="ghost" aria-label="O'zgaruvchini o'chirish" @click="remove(i)">×</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
