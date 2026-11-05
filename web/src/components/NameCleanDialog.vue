<script setup lang="ts">
/** Nomlarni tozalash: URL bo'lib qolgan so'rov nomlari -> qisqa (host'siz) nomlar. Oldindan ko'rish, tanlash, avtomatik zaxira. */
import { computed, ref } from 'vue'
import Dialog from './Dialog.vue'
import { applyClean, dismissOffer, urlNamedItems } from '../lib/nameclean'
import { showToast } from '../lib/ui'

const emit = defineEmits<{ close: [] }>()
const items = urlNamedItems()
const checked = ref<Record<string, boolean>>(Object.fromEntries(items.map(i => [i.id, true])))
const picked = computed(() => items.filter(i => checked.value[i.id]))
const busy = ref(false)
async function run() {
  busy.value = true
  try { const bk = await applyClean(picked.value); showToast(`${picked.value.length} ta nom tozalandi · zaxira: ${bk}`, 'success', 6000); dismissOffer(); emit('close') }
  catch (e: any) { showToast(e.message, 'error') } finally { busy.value = false }
}
</script>

<template>
  <Dialog title="Nomlarni tozalash" testid="nameclean-dialog" width="min(760px,92vw)" @close="emit('close')">
    <p style="margin:0 0 10px">Quyidagi <b>{{ items.length }}</b> ta so'rovning nomi to'liq URL. Ular host'siz qisqa nomga almashtiriladi (so'rovning o'zi o'zgarmaydi). O'zgartirishdan oldin ish maydonining zaxira nusxasi avtomatik olinadi.</p>
    <ul class="imp-list" data-testid="nameclean-list">
      <li v-for="i in items" :key="i.id" data-testid="nameclean-row">
        <input v-model="checked[i.id]" type="checkbox" :aria-label="`${i.old} — tozalash`">
        <span class="imp-name"><small class="muted" :title="i.old">{{ i.old }}</small><b>→ {{ i.neu }}</b></span>
      </li>
    </ul>
    <template #footer>
      <button data-testid="nameclean-skip" @click="dismissOffer(); emit('close')">Keyinroq / kerak emas</button>
      <button class="primary" data-testid="nameclean-apply" data-autofocus :disabled="busy || !picked.length" @click="run">Tozalash ({{ picked.length }})</button>
    </template>
  </Dialog>
</template>
