<script setup lang="ts">
/** Kalit/Qiymat/Tavsif jadvali: ustun sarlavhalari, oxirida doim bitta ghost qator, Enter/Tab bilan kataklar orasida yurish, Bulk Edit. */
import { nextTick, onMounted, ref, watch } from 'vue'
import { emptyKV, type KV } from '../lib/draft'
import { ensureGhost } from '../lib/ghost'
import { showToast } from '../lib/ui'

const props = defineProps<{ rows: KV[]; files?: boolean; testid?: string }>()
const emit = defineEmits<{ change: [] }>()
const root = ref<HTMLElement>()
const dragFrom = ref<number | null>(null)
const over = ref<number | null>(null)

const blank = (r: KV) => !r.key && !r.value && !r.description && r.kind !== 'file'
const isGhost = (i: number) => i === props.rows.length - 1 && blank(props.rows[i])
const sync = () => ensureGhost(props.rows, blank, emptyKV)           // `change` chiqarmaydi: ghost dirty yaratmasin
onMounted(sync)
watch(() => props.rows.length, sync)
watch(() => props.rows, sync, { deep: true, flush: 'post' })

function touch() { sync(); emit('change') }
function remove(i: number) { if (isGhost(i)) return; props.rows.splice(i, 1); sync(); emit('change') }
function drop(i: number) {
  if (dragFrom.value === null || dragFrom.value === i || isGhost(dragFrom.value) || isGhost(i)) { over.value = dragFrom.value = null; return }
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

// ── klaviatura: Enter/Tab katakdan katakka, Shift+Tab orqaga, Alt+Backspace qatorni o'chiradi ──
const cell = (i: number, c: number) => root.value?.querySelector<HTMLInputElement>(`[data-cell="${i}:${c}"]`)
async function focusCell(i: number, c: number) {
  await nextTick()
  const el = cell(i, c) ?? cell(i, c === 1 ? 2 : 1)                       // fayl qatorida qiymat katagi yo'q
  el?.focus(); el?.select?.()
}
function onKey(e: KeyboardEvent, i: number, c: number) {
  if (e.altKey && e.key === 'Backspace') { e.preventDefault(); remove(i); focusCell(Math.min(i, props.rows.length - 1), c); return }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    if (c < 2) focusCell(i, c + 1)
    else if (i < props.rows.length - 1) focusCell(i + 1, 0)
  } else if (e.key === 'Tab' && !e.shiftKey && c === 2 && i < props.rows.length - 1) { e.preventDefault(); focusCell(i + 1, 0) }
  else if (e.key === 'Tab' && e.shiftKey && c === 0 && i > 0) { e.preventDefault(); focusCell(i - 1, 2) }
}

const bulk = ref(false)
const bulkText = ref('')
const bulkOf = () => props.rows.filter(r => r.key || r.value).map(r => `${r.enabled ? '' : '//'}${r.key}:${r.value}`).join('\n')
function toggleBulk() { if (!bulk.value) bulkText.value = bulkOf(); bulk.value = !bulk.value; if (!bulk.value) sync() }
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
</script>

<template>
  <div ref="root" class="kv-wrap-outer">
    <div v-if="bulk" style="text-align:right;margin-bottom:6px"><button class="ghost" data-testid="kv-bulk" @click="toggleBulk">Key-Value Edit</button></div>
    <textarea v-if="bulk" v-model="bulkText" :data-testid="(testid ?? 'kv') + '-bulk'" aria-label="Bulk Edit" placeholder="kalit:qiymat (har qatorda bittadan; // — o'chirilgan)" style="width:100%;height:160px;font-family:var(--font-mono)" @input="applyBulk" />
    <div v-else class="kv-wrap">
      <table class="kv kv-head" aria-hidden="false">
        <colgroup><col style="width:22px"><col style="width:26px"><col><col><col style="width:30%"><col style="width:112px"></colgroup>
        <thead><tr><th colspan="2" /><th scope="col">Kalit</th><th scope="col">Qiymat</th><th scope="col">Tavsif</th><th style="text-align:right;padding-right:6px"><button class="ghost sm" data-testid="kv-bulk" style="height:22px;width:auto;padding:0 8px;white-space:nowrap" @click="toggleBulk">Bulk Edit</button></th></tr></thead>
      </table>
      <table class="kv" :data-testid="testid">
        <colgroup><col style="width:22px"><col style="width:26px"><col><col><col style="width:30%"><col style="width:112px"></colgroup>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i" :class="{ dragover: over === i, ghost: isGhost(i) }" :data-ghost="isGhost(i) || undefined" :draggable="!isGhost(i)"
              @dragstart="dragFrom = i" @dragover.prevent="over = i" @dragleave="over = null" @drop.prevent="drop(i)" @dragend="dragFrom = over = null">
            <td class="grip" :title="isGhost(i) ? undefined : 'Sudrab tartiblash'"><span v-if="!isGhost(i)" aria-hidden="true">⋮⋮</span></td>
            <td style="text-align:center"><input v-if="!isGhost(i)" type="checkbox" aria-label="Yoqish" tabindex="-1" v-model="r.enabled" @change="emit('change')"></td>
            <td><input type="text" :data-cell="`${i}:0`" placeholder="Kalit" aria-label="Kalit" v-model="r.key" draggable="false" @input="touch" @keydown="onKey($event, i, 0)"></td>
            <td>
              <input v-if="r.kind !== 'file'" type="text" :data-cell="`${i}:1`" placeholder="Qiymat" aria-label="Qiymat" v-model="r.value" draggable="false" @input="touch" @keydown="onKey($event, i, 1)">
              <span v-else style="padding:0 10px">📎 {{ label(r.value) }}</span>
            </td>
            <td><input type="text" :data-cell="`${i}:2`" placeholder="Tavsif" aria-label="Tavsif" v-model="r.description" data-testid="kv-desc" draggable="false" @input="touch" @keydown="onKey($event, i, 2)"></td>
            <td style="text-align:right;padding-right:4px;white-space:nowrap">
              <label v-if="files && !isGhost(i)" title="Fayl biriktirish" aria-label="Fayl biriktirish" style="cursor:pointer;margin-right:4px">📎<input type="file" hidden tabindex="-1" @change="upload(i, $event)"></label>
              <button v-if="!isGhost(i)" class="ghost" aria-label="Qatorni o'chirish" tabindex="-1" title="O'chirish (Alt+Backspace)" @click="remove(i)">×</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
