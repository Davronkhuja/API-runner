<script setup lang="ts">
/** Workspace zaxirasi (zip): sukut — maxfiy va Current qiymatlarsiz. Maxfiylarni qo'shish qizil ogohlantirish bilan; ixtiyoriy parol (AES-256). */
import { computed, ref } from 'vue'
import Dialog from './Dialog.vue'
import { downloadFrom } from '../lib/exporter'
import { showToast } from '../lib/ui'

const emit = defineEmits<{ close: [] }>()
const secrets = ref(false), state = ref(false), encrypt = ref(false), pw = ref(''), pw2 = ref(''), busy = ref(false)
const pwError = computed(() => (!encrypt.value ? '' : pw.value.length < 8 ? "Parol kamida 8 belgi bo'lsin" : pw.value !== pw2.value ? 'Parollar mos kelmadi' : ''))
async function run() {
  if (pwError.value) return
  busy.value = true
  const n = await downloadFrom('/api/workspace/export', 'workspace.zip', { secrets: secrets.value, state: secrets.value && state.value, password: encrypt.value ? pw.value : undefined })
  busy.value = false
  if (n) { showToast(`Zaxira yuklab olindi: ${n}`, 'success'); emit('close') }
}
</script>

<template>
  <Dialog title="Workspace zaxirasi (zip)" testid="wsexport-dialog" width="540px" @close="emit('close')">
    <p style="margin:0 0 var(--sp-3)">Collection'lar, muhitlar, globals, sozlamalar va biriktirilgan fayllar. <b>Sukut bo'yicha</b> maxfiy (secret) qiymatlar, Current qiymatlar va auth parol/tokenlari <b>bo'sh</b> ketadi.</p>
    <label class="exp-sec"><input type="checkbox" v-model="secrets" data-testid="wsexport-secrets">Maxfiy va Current qiymatlarni ham qo'shish</label>
    <div v-if="secrets" class="state-error wsx-warn" role="alert" data-testid="wsexport-warning">
      <b>Diqqat:</b> zip token, parol va maxfiy o'zgaruvchilarni ochiq matnda saqlaydi. Uni begonalarga bermang, messenjer yoki git'ga yuklamang. Quyida parol bilan shifrlashni yoqish tavsiya etiladi.
    </div>
    <label v-if="secrets" class="exp-sec"><input type="checkbox" v-model="state" data-testid="wsexport-state">Tarix, javoblar va cookie bazasini ham qo'shish <small class="muted">(ularda ham token bo'lishi mumkin)</small></label>
    <label v-if="secrets" class="exp-sec"><input type="checkbox" v-model="encrypt" data-testid="wsexport-encrypt">Parol bilan shifrlash (AES-256) <small class="muted">— tavsiya etiladi</small></label>
    <template v-if="secrets && encrypt">
      <label class="dlg-field"><span>Parol (kamida 8 belgi)</span><input type="password" v-model="pw" autocomplete="new-password" data-testid="wsexport-password" style="width:100%"></label>
      <label class="dlg-field"><span>Parolni takrorlang</span><input type="password" v-model="pw2" autocomplete="new-password" data-testid="wsexport-password2" style="width:100%"></label>
      <p v-if="pwError" class="state-error" role="alert" data-testid="wsexport-pwerror" style="padding:6px 10px;margin:0">{{ pwError }}</p>
      <p class="muted" style="margin:var(--sp-2) 0 0;font-size:var(--fs-sm)">Parolni yo'qotsangiz fayl qayta tiklanmaydi. Import paytida parol so'raladi. Fayl nomi <code>.zip.enc</code> bilan tugaydi.</p>
    </template>
    <p class="muted" style="margin:var(--sp-3) 0 0;font-size:var(--fs-sm)">Avtomatik zaxiralar (<code>backups/</code>) bundan mustasno — ular lokal va to'liq.</p>
    <template #footer>
      <button @click="emit('close')">Bekor qilish</button>
      <button class="primary" data-testid="wsexport-go" :disabled="busy || !!pwError" data-autofocus @click="run">Yuklab olish</button>
    </template>
  </Dialog>
</template>
