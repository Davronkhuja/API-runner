<script setup lang="ts">
/** Collection eksporti: format tanlash (Postman v2.1 / OpenAPI JSON / YAML). Maxfiy o'zgaruvchi qiymatlari sukut bo'yicha bo'sh. */
import { ref } from 'vue'
import Dialog from './Dialog.vue'
import { downloadFrom, EXPORT_FORMATS } from '../lib/exporter'
import { showToast } from '../lib/ui'

const props = defineProps<{ cid: string; name: string; requests?: number }>()
const emit = defineEmits<{ close: [] }>()
const fmt = ref('postman'), secrets = ref(false), busy = ref(false)
async function run() {
  busy.value = true
  const n = await downloadFrom(`/api/collections/${props.cid}/export?format=${fmt.value}${secrets.value && fmt.value === 'postman' ? '&secrets=1' : ''}`)
  busy.value = false
  if (n) { showToast(`Eksport qilindi: ${n}`, 'success'); emit('close') }
}
</script>

<template>
  <Dialog title="Collection eksporti" testid="export-dialog" width="520px" @close="emit('close')">
    <p style="margin:0 0 var(--sp-3)"><b data-testid="export-name">{{ name }}</b><span v-if="requests != null" class="muted"> · {{ requests }} ta so'rov</span></p>
    <fieldset class="exp-fmt" role="radiogroup" aria-label="Format">
      <label v-for="f in EXPORT_FORMATS" :key="f.id" class="exp-opt" :class="{ on: fmt === f.id }"><input type="radio" v-model="fmt" :value="f.id" :data-testid="'export-fmt-' + f.id"><span><b>{{ f.label }}</b><small class="muted">{{ f.hint }}</small></span></label>
    </fieldset>
    <label v-if="fmt === 'postman'" class="exp-sec"><input type="checkbox" v-model="secrets" data-testid="export-secrets">Maxfiy (secret) o'zgaruvchi qiymatlarini ham kiritish <small class="muted">(sukut: bo'sh)</small></label>
    <p class="muted" style="margin:var(--sp-3) 0 0;font-size:var(--fs-sm)">Auth maydonlaridagi qiymatlar (token, parol) collection'da qanday yozilgan bo'lsa shunday ketadi — begonalarga berishdan oldin tekshiring.</p>
    <template #footer>
      <button @click="emit('close')">Bekor qilish</button>
      <button class="primary" data-testid="export-go" :disabled="busy" data-autofocus @click="run">Yuklab olish</button>
    </template>
  </Dialog>
</template>
