<script setup lang="ts">
/** Savat: o'chirilganlar 30 kun saqlanadi; tiklash yoki butunlay o'chirish. */
import { onMounted, ref } from 'vue'
import Dialog from './Dialog.vue'
import Icon from './Icon.vue'
import { askConfirm, showToast } from '../lib/ui'
import { deleteTrash, emptyTrash, kindLabel, listTrash, restoreTrash, whereLabel, type TrashRow } from '../lib/trash'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'

const emit = defineEmits<{ close: [] }>()
const tree = useTree(), ws = useWorkspace()
const rows = ref<TrashRow[]>([]), loading = ref(true), busy = ref(false)
async function load() { try { rows.value = await listTrash() } finally { loading.value = false } }
onMounted(load)
async function restore(r: TrashRow) {
  busy.value = true
  try {
    const res = await restoreTrash(r.id)
    await Promise.all([tree.load(), ws.load()])
    showToast(res.new_collection ? `«${r.name}» yangi collection'da tiklandi (asl collection o'chirilgan)` : res.to_root ? `«${r.name}» tiklandi (ota papka yo'q — collection ildizida)` : `«${r.name}» tiklandi`, 'success', 4000)
    await load()
  } catch (e: any) { showToast(e.message, 'error') } finally { busy.value = false }
}
async function forever(r: TrashRow) {
  if (!(await askConfirm(`«${r.name}» butunlay o'chirilsinmi? Qaytarib bo'lmaydi.`, "Butunlay o'chirish"))) return
  await deleteTrash(r.id); await load()
}
async function empty() {
  if (!(await askConfirm(`Savatdagi ${rows.value.length} ta element butunlay o'chirilsinmi? Qaytarib bo'lmaydi.`, 'Savatni bo\'shatish'))) return
  await emptyTrash(); await load()
}
</script>

<template>
  <Dialog title="Savat" testid="trash-dialog" width="min(680px,92vw)" @close="emit('close')">
    <p class="muted" style="margin:0 0 var(--sp-3)">O'chirilgan so'rov, papka, collection va muhitlar 30 kun saqlanadi, keyin avtomatik o'chiriladi.</p>
    <p v-if="loading" class="muted" role="status">Yuklanmoqda…</p>
    <p v-else-if="!rows.length" class="muted" data-testid="trash-empty">Savat bo'sh.</p>
    <ul v-else class="trash-list" data-testid="trash-list">
      <li v-for="r in rows" :key="r.id" data-testid="trash-row">
        <span class="badge">{{ kindLabel(r) }}</span>
        <span class="tr-main"><b class="tr-name" data-testid="trash-name">{{ r.name }}</b><small class="muted">{{ whereLabel(r) }}</small></span>
        <span class="muted tr-days" data-testid="trash-days">{{ r.days_left }} kun qoldi</span>
        <button class="sm" data-testid="trash-restore" :disabled="busy" @click="restore(r)">Tiklash</button>
        <button class="ib" aria-label="Butunlay o'chirish" title="Butunlay o'chirish" data-testid="trash-forever" @click="forever(r)"><Icon name="trash" :size="15" /></button>
      </li>
    </ul>
    <template #footer>
      <button data-testid="trash-empty-btn" :disabled="!rows.length" @click="empty">Savatni bo'shatish</button>
      <button class="primary" @click="emit('close')">Yopish</button>
    </template>
  </Dialog>
</template>
