<script setup lang="ts">
/** Kalit/Qiymat/Tavsif jadvali: ustun sarlavhalari, oxirida doim bitta ghost qator, Enter/Tab bilan kataklar orasida yurish, Bulk Edit. */
import { nextTick, onMounted, ref, watch } from 'vue'
import { emptyKV, type KV } from '../lib/draft'
import { ensureGhost } from '../lib/ghost'
import { fmtBytes, showToast } from '../lib/ui'
import { fileInfo, guessType, isMissing, refreshFileInfo, uploadFile } from '../lib/files'
import Icon from './Icon.vue'

/** `formdata` — Body → form-data (Turi ustuni, fayl qatorlari); `quickAttach` — Params: 📎/sudrash faylni Body → form-data'ga o'tkazadi. */
const props = defineProps<{ rows: KV[]; formdata?: boolean; quickAttach?: boolean; testid?: string }>()
const emit = defineEmits<{ change: []; attach: [index: number, files: File[]] }>()
const root = ref<HTMLElement>()
const dragFrom = ref<number | null>(null)
const over = ref<number | null>(null)

const blank = (r: KV) => !r.key && !r.value && !r.description && !r.contentType && r.kind !== 'file'
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
// ── fayllar: form-data qatori ──
const pending = ref<{ row: number; replace: number | null } | null>(null)
const inputs = ref<Record<number, HTMLInputElement | null>>({})
const hasFiles = (r: KV) => r.kind === 'file'
const missingRow = (r: KV) => hasFiles(r) && !!r.files?.some(f => isMissing(f.ref))
function setKind(i: number, kind: 'text' | 'file') {
  const r = props.rows[i]
  if (kind === 'file') { r.kind = 'file'; r.value = ''; r.files = r.files ?? [] }
  else { r.kind = 'text'; r.files = undefined; r.contentType = r.contentType }
  touch()
}
function startPick(i: number, replace: number | null = null) { pending.value = { row: i, replace }; inputs.value[i]?.click() }
async function addFiles(i: number, files: File[], replace: number | null = null) {
  const r = props.rows[i]
  if (!files.length) return
  try {
    const up = []
    for (const f of files) up.push(await uploadFile(f))
    if (r.kind !== 'file') { r.kind = 'file'; r.value = '' }
    if (!r.key) r.key = 'file'
    const refs = up.map(u => ({ ref: u.ref, name: u.name }))
    const cur = r.files ?? []
    r.files = replace !== null && cur[replace] ? [...cur.slice(0, replace), ...refs, ...cur.slice(replace + 1)] : [...cur, ...refs]
    touch()
  } catch (e: any) { showToast('Fayl yuklanmadi: ' + (e?.message ?? ''), 'error') }
}
async function onPick(i: number, ev: Event) {
  const el = ev.target as HTMLInputElement
  const files = [...(el.files ?? [])]
  const rep = pending.value?.row === i ? pending.value.replace : null
  el.value = ''; pending.value = null
  await addFiles(i, files, rep)
}
function removeFile(i: number, fi: number) { const r = props.rows[i]; r.files = (r.files ?? []).filter((_, k) => k !== fi); touch() }
const dragFiles = (e: DragEvent) => !!e.dataTransfer && [...(e.dataTransfer.types ?? [])].includes('Files')
function onRowDrop(i: number, e: DragEvent) {
  if (dragFiles(e)) {
    e.preventDefault(); e.stopPropagation(); over.value = null
    const files = [...(e.dataTransfer?.files ?? [])]
    if (props.formdata) addFiles(i, files)
    else if (props.quickAttach) emit('attach', -1, files)
    return
  }
  drop(i)
}
function onTableDrop(e: DragEvent) { if (props.quickAttach && dragFiles(e)) { e.preventDefault(); emit('attach', -1, [...(e.dataTransfer?.files ?? [])]) } }
const ctPlaceholder = (r: KV) => (hasFiles(r) && r.files?.[0] ? guessType(r.files[0].name) : 'auto')
// qatorlardagi fayllarning holati (topilmadi / hajm) — server so'raladi
const refsOf = () => (props.formdata ? props.rows.flatMap(r => (r.kind === 'file' ? (r.files ?? []).map(f => f.ref) : [])) : [])
function loadInfo() { const want = refsOf().filter(r => !(r in fileInfo)); if (want.length) refreshFileInfo(want) }
onMounted(loadInfo)
watch(() => refsOf().join('|'), loadInfo)
function attachQuick(i: number, ev: Event) {
  const el = ev.target as HTMLInputElement
  const files = [...(el.files ?? [])]; el.value = ''
  if (files.length) emit('attach', i, files)
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
const bulkOf = () => props.rows.filter(r => (r.key || r.value) && r.kind !== 'file').map(r => `${r.enabled ? '' : '//'}${r.key}:${r.value}`).join('\n')
function toggleBulk() { if (!bulk.value) bulkText.value = bulkOf(); bulk.value = !bulk.value; if (!bulk.value) sync() }
/** Har qator `kalit:qiymat` (birinchi ":" bo'yicha), `//` bilan boshlansa o'chirilgan; tavsif va fayl turi kalit bo'yicha saqlanadi. */
function applyBulk() {
  const old = new Map(props.rows.filter(r => r.key && r.kind !== 'file').map(r => [r.key, r]))
  const next = bulkText.value.split('\n').filter(l => l.trim()).map(l => {
    const off = l.startsWith('//'), t = off ? l.slice(2) : l, i = t.indexOf(':')
    const key = (i < 0 ? t : t.slice(0, i)).trim(), value = i < 0 ? '' : t.slice(i + 1).trim(), o = old.get(key)
    return { key, value, enabled: !off, ...(o?.description ? { description: o.description } : {}), ...(o?.contentType ? { contentType: o.contentType } : {}) }
  })
  const fileRows = props.rows.filter(r => r.kind === 'file')                          // fayl qatorlari Bulk Edit'da ko'rinmaydi, lekin yo'qolmaydi
  props.rows.splice(0, props.rows.length, ...fileRows, ...next, emptyKV())
  emit('change')
}
</script>

<template>
  <div ref="root" class="kv-wrap-outer">
    <div v-if="bulk" style="text-align:right;margin-bottom:6px"><button class="ghost" data-testid="kv-bulk" @click="toggleBulk">Key-Value Edit</button></div>
    <textarea v-if="bulk" v-model="bulkText" :data-testid="(testid ?? 'kv') + '-bulk'" aria-label="Bulk Edit" placeholder="kalit:qiymat (har qatorda bittadan; // — o'chirilgan)" style="width:100%;min-height:160px;resize:vertical;font-family:var(--font-mono)" @input="applyBulk" />
    <div v-else class="kv-wrap" @dragover="quickAttach && dragFiles($event) && $event.preventDefault()" @drop="onTableDrop">
      <table class="kv kv-head" aria-hidden="false">
        <colgroup v-if="formdata"><col style="width:22px"><col style="width:26px"><col style="width:24%"><col style="width:96px"><col><col style="width:22%"><col style="width:112px"></colgroup>
        <colgroup v-else><col style="width:22px"><col style="width:26px"><col><col><col style="width:30%"><col style="width:112px"></colgroup>
        <thead><tr><th colspan="2" /><th scope="col">Kalit</th><th v-if="formdata" scope="col">Turi</th><th scope="col">{{ formdata ? 'Qiymat / Fayl' : 'Qiymat' }}</th><th scope="col">{{ formdata ? 'Content-Type' : 'Tavsif' }}</th><th style="text-align:right;padding-right:6px"><button class="ghost sm" data-testid="kv-bulk" style="height:22px;width:auto;padding:0 8px;white-space:nowrap" @click="toggleBulk">Bulk Edit</button></th></tr></thead>
      </table>
      <table class="kv" :data-testid="testid">
        <colgroup v-if="formdata"><col style="width:22px"><col style="width:26px"><col style="width:24%"><col style="width:96px"><col><col style="width:22%"><col style="width:112px"></colgroup>
        <colgroup v-else><col style="width:22px"><col style="width:26px"><col><col><col style="width:30%"><col style="width:112px"></colgroup>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i" :class="{ dragover: over === i, ghost: isGhost(i), missing: missingRow(r) }" :data-ghost="isGhost(i) || undefined" :data-missing="missingRow(r) || undefined" :draggable="!isGhost(i)"
              @dragstart="dragFrom = i" @dragover.prevent="over = i" @dragleave="over = null" @drop.prevent="onRowDrop(i, $event)" @dragend="dragFrom = over = null">
            <td class="grip" :title="isGhost(i) ? undefined : 'Sudrab tartiblash'"><span v-if="!isGhost(i)" aria-hidden="true">⋮⋮</span></td>
            <td style="text-align:center"><input v-if="!isGhost(i)" type="checkbox" aria-label="Yoqish" tabindex="-1" v-model="r.enabled" @change="emit('change')"></td>
            <td><input type="text" :data-cell="`${i}:0`" placeholder="Kalit" aria-label="Kalit" v-model="r.key" draggable="false" @input="touch" @keydown="onKey($event, i, 0)"></td>
            <td v-if="formdata"><select v-if="!isGhost(i)" :value="hasFiles(r) ? 'file' : 'text'" aria-label="Turi" data-testid="fd-type" @change="setKind(i, ($event.target as HTMLSelectElement).value as 'text' | 'file')"><option value="text">Text</option><option value="file">File</option></select></td>
            <td>
              <div v-if="formdata && hasFiles(r)" class="fd-files" data-testid="fd-files">
                <span v-for="(f, fi) in r.files" :key="f.ref + fi" class="fd-file" :class="{ missing: isMissing(f.ref) }" data-testid="fd-file">
                  <Icon name="file" :size="14" /><span class="fd-name" data-testid="fd-name" :title="f.name">{{ f.name }}</span>
                  <span v-if="isMissing(f.ref)" class="fd-miss" data-testid="fd-missing" role="alert">topilmadi, qayta tanlang</span>
                  <small v-else-if="fileInfo[f.ref]" data-testid="fd-size">{{ fmtBytes(fileInfo[f.ref].size) }}</small>
                  <button class="linkbtn" data-testid="fd-replace" tabindex="-1" @click="startPick(i, fi)">Almashtirish</button>
                  <button class="ghost" aria-label="Faylni olib tashlash" data-testid="fd-remove" tabindex="-1" @click="removeFile(i, fi)">×</button>
                </span>
                <button class="linkbtn" data-testid="fd-add" tabindex="-1" @click="startPick(i)">{{ r.files?.length ? '+ yana fayl' : 'Fayl tanlash…' }}</button>
                <input :ref="el => (inputs[i] = el as HTMLInputElement)" type="file" multiple hidden tabindex="-1" aria-label="Fayl tanlash" data-testid="fd-input" @change="onPick(i, $event)">
              </div>
              <input v-else type="text" :data-cell="`${i}:1`" placeholder="Qiymat" aria-label="Qiymat" v-model="r.value" draggable="false" @input="touch" @keydown="onKey($event, i, 1)">
            </td>
            <td v-if="formdata"><input type="text" :data-cell="`${i}:2`" :placeholder="ctPlaceholder(r)" aria-label="Content-Type" v-model="r.contentType" data-testid="fd-ct" draggable="false" @input="touch" @keydown="onKey($event, i, 2)"></td>
            <td v-else><input type="text" :data-cell="`${i}:2`" placeholder="Tavsif" aria-label="Tavsif" v-model="r.description" data-testid="kv-desc" draggable="false" @input="touch" @keydown="onKey($event, i, 2)"></td>
            <td style="text-align:right;padding-right:4px;white-space:nowrap">
              <label v-if="quickAttach && !isGhost(i)" title="Fayl Body → form-data'ga qo'shiladi" aria-label="Fayl biriktirish" data-testid="params-attach" style="cursor:pointer;margin-right:4px"><Icon name="file" :size="14" /><input type="file" hidden tabindex="-1" @change="attachQuick(i, $event)"></label>
              <button v-if="!isGhost(i)" class="ghost" aria-label="Qatorni o'chirish" tabindex="-1" title="O'chirish (Alt+Backspace)" @click="remove(i)">×</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
