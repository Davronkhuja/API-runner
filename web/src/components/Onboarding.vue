<script setup lang="ts">
/** Birinchi ishga tushirishdagi qisqa tanishtiruv (3 qadam, o'tkazib yuborish mumkin). */
import { computed, ref } from 'vue'
import Dialog from './Dialog.vue'

const emit = defineEmits<{ close: [] }>()
const steps = [
  { title: 'API Runner\'ga xush kelibsiz', text: 'Lokal API klient: ma\'lumotlaringiz faqat shu kompyuterda saqlanadi. «Yangi so\'rov» (⌘T) bilan boshlang yoki Postman / OpenAPI / cURL\'ni import qiling (header → Import).' },
  { title: 'Muhitlar va qidiruv', text: 'Muhitlar (Dev/Prod) bilan `{{o\'zgaruvchi}}` ishlating. ⌘K — barcha so\'rov, muhit va amallar bo\'yicha qidiruv. «?» — yorliqlar ro\'yxati.' },
  { title: 'Avtomatlashtirish', text: 'Collection Runner, Mock server, Monitor (cron bo\'yicha avtomatik run), Proxy capture va CLI (`apirunner run`) — hammasi shu ilovada. O\'chirilganlar 30 kun Savatda turadi.' },
]
const i = ref(0), last = computed(() => i.value === steps.length - 1)
</script>

<template>
  <Dialog :title="steps[i].title" testid="onboarding" width="min(520px,94vw)" @close="emit('close')">
    <p style="margin:0;line-height:1.6" data-testid="onb-text">{{ steps[i].text }}</p>
    <p class="muted" style="margin:var(--sp-3) 0 0" aria-live="polite">{{ i + 1 }} / {{ steps.length }}</p>
    <template #footer>
      <button data-testid="onb-skip" @click="emit('close')">O'tkazib yuborish</button>
      <button v-if="i > 0" data-testid="onb-back" @click="i--">Orqaga</button>
      <button v-if="!last" class="primary" data-testid="onb-next" @click="i++">Keyingi</button>
      <button v-else class="primary" data-testid="onb-done" @click="emit('close')">Boshlash</button>
    </template>
  </Dialog>
</template>
