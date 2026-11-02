<script setup lang="ts">
/** Collection/papka/Globals o'zgaruvchilari jadvali (Postman `variable[]` formati: key, value, disabled, type). */
const props = defineProps<{ rows: { key: string; value: string; disabled?: boolean; type?: string }[]; testid?: string }>()
const emit = defineEmits<{ change: [] }>()
const add = () => { props.rows.push({ key: '', value: '', type: 'default' }); emit('change') }
const remove = (i: number) => { props.rows.splice(i, 1); emit('change') }
</script>

<template>
  <div :data-testid="testid ?? 'vars-table'">
    <table class="kv"><tbody>
      <tr v-for="(v, i) in rows" :key="i">
        <td style="width:22px"><input type="checkbox" :checked="!v.disabled" @change="v.disabled = !($event.target as HTMLInputElement).checked; emit('change')"></td>
        <td><input v-model="v.key" placeholder="O'zgaruvchi" data-testid="var-key" @input="emit('change')"></td>
        <td><input v-model="v.value" :type="v.type === 'secret' ? 'password' : 'text'" placeholder="Qiymat" data-testid="var-val" @input="emit('change')"></td>
        <td style="width:90px"><select v-model="v.type" data-testid="var-type" @change="emit('change')"><option value="default">default</option><option value="secret">secret</option></select></td>
        <td style="width:24px"><button class="ghost" @click="remove(i)">×</button></td>
      </tr>
    </tbody></table>
    <button data-testid="var-add" @click="add">＋ O'zgaruvchi</button>
  </div>
</template>
