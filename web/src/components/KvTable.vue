<script setup lang="ts">
import { ref } from 'vue'
import { emptyKV, type KV } from '../lib/draft'
import { post } from '../api/client'
import { showToast } from '../lib/ui'

const props = defineProps<{ rows: KV[]; files?: boolean; testid?: string }>()
const emit = defineEmits<{ change: [] }>()
const dragFrom = ref<number | null>(null)
const over = ref<number | null>(null)

function touch() {
  const last = props.rows[props.rows.length - 1]
  if (!last || last.key || last.value) props.rows.push(emptyKV())
  emit('change')
}
function remove(i: number) { props.rows.splice(i, 1); if (!props.rows.length) props.rows.push(emptyKV()); emit('change') }
function drop(i: number) {
  if (dragFrom.value === null || dragFrom.value === i) { over.value = null; return }
  const [r] = props.rows.splice(dragFrom.value, 1)
  props.rows.splice(i, 0, r)
  dragFrom.value = over.value = null
  emit('change')
}
async function upload(i: number, ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  const fd = new FormData(); fd.append('file', f)
  try {
    const r = await fetch('/upload_temp', { method: 'POST', body: fd, headers: { 'X-Session-Token': window.__API_TOKEN__ ?? '' } }).then(x => x.json())
    if (!props.rows[i].key) props.rows[i].key = 'file'
    props.rows[i].value = `${r.path}::${r.name}`; props.rows[i].kind = 'file'; touch()
  } catch { showToast('Fayl yuklanmadi', 'error') }
}
const bulk = ref(false)
const bulkText = ref('')
const bulkOf = () => props.rows.filter(r => r.key || r.value).map(r => `${r.enabled ? '' : '//'}${r.key}:${r.value}`).join('\n')
function toggleBulk() { if (!bulk.value) bulkText.value = bulkOf(); bulk.value = !bulk.value }
/** Har qator `kalit:qiymat` (birinchi ":" bo'yicha), `//` bilan boshlansa o'chirilgan; tavsif va fayl turi kalit bo'yicha saqlanadi. */
function applyBulk() {
  const old = new Map(props.rows.filter(r => r.key).map(r => [r.key, r]))
  const next = bulkText.value.split('\n').filter(l => l.trim()).map(l => {
    const off = l.startsWith('//'), t = off ? l.slice(2) : l, i = t.indexOf(':')
    const key = (i < 0 ? t : t.slice(0, i)).trim(), value = i < 0 ? '' : t.slice(i + 1).trim(), o = old.get(key)
    return { ...(o && o.kind === 'file' && o.value === value ? o : {}), key, value, enabled: !off, ...(o?.description ? { description: o.description } : {}) }
  })
  props.rows.splice(0, props.rows.length, ...next, emptyKV())
  emit('change')
}
const label = (v: string) => (v.includes('::') ? v.split('::')[1] : v)
void post
</script>

<template>
  <div>
  <div style="text-align:right"><button class="ghost" data-testid="kv-bulk" @click="toggleBulk">{{ bulk ? 'Key-Value Edit' : 'Bulk Edit' }}</button></div>
  <textarea v-if="bulk" v-model="bulkText" :data-testid="(testid ?? 'kv') + '-bulk'" placeholder="kalit:qiymat (har qatorda bittadan; // — o'chirilgan)" style="width:100%;height:160px;font-family:ui-monospace,monospace" @input="applyBulk" />
  <table v-else class="kv" :data-testid="testid">
    <tbody>
      <tr v-for="(r, i) in rows" :key="i" :class="{ dragover: over === i }" draggable="true"
          @dragstart="dragFrom = i" @dragover.prevent="over = i" @dragleave="over = null" @drop.prevent="drop(i)" @dragend="dragFrom = over = null">
        <td style="width:18px" class="grip" title="Sudrab tartiblash">⋮⋮</td>
        <td style="width:22px"><input type="checkbox" v-model="r.enabled" @change="emit('change')"></td>
        <td><input type="text" placeholder="Nom" v-model="r.key" @input="touch" draggable="false"></td>
        <td>
          <input v-if="r.kind !== 'file'" type="text" placeholder="Qiymat" v-model="r.value" @input="touch" draggable="false">
          <span v-else>📎 {{ label(r.value) }}</span>
        </td>
        <td style="width:30%"><input type="text" placeholder="Tavsif" v-model="r.description" data-testid="kv-desc" @input="emit('change')" draggable="false"></td>
        <td v-if="files" style="width:30px">
          <label title="Fayl biriktirish" style="cursor:pointer">📎<input type="file" hidden @change="upload(i, $event)"></label>
        </td>
        <td style="width:24px"><button class="ghost" @click="remove(i)" title="O'chirish">×</button></td>
      </tr>
    </tbody>
  </table>
  </div>
</template>
