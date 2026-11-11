<script setup lang="ts">
/** Klaviatura yorliqlari ro'yxati (? bilan ochiladi). */
import Dialog from './Dialog.vue'

const emit = defineEmits<{ close: [] }>()
const groups: { title: string; rows: [string, string][] }[] = [
  { title: 'So\'rov va tablar', rows: [['Yangi so\'rov', '⌘ T'], ['Yuborish', '⌘ ↵'], ['Saqlash', '⌘ S'], ['Tabni yopish', '⌘ W'], ['Yopilgan tabni qaytarish', '⌘ ⇧ T'], ['Keyingi / oldingi tab', '⌃ Tab / ⌃ ⇧ Tab']] },
  { title: 'Umumiy', rows: [['Qidirish va buyruqlar palitrasi', '⌘ K'], ['Yorliqlar ro\'yxati', '?'], ['Dialog / menyuni yopish', 'Esc']] },
  { title: 'Muharrir', rows: [['Avtoto\'ldirishni ochish', '⌃ Space'], ['Muharrirda qidirish', '⌘ F'], ['O\'zgaruvchi (`{{`)', '{{']] },
]
</script>

<template>
  <Dialog title="Klaviatura yorliqlari" testid="shortcuts-dialog" width="min(560px,94vw)" @close="emit('close')">
    <section v-for="g in groups" :key="g.title" class="sc-group">
      <h3>{{ g.title }}</h3>
      <div v-for="r in g.rows" :key="r[0]" class="sc-row"><span>{{ r[0] }}</span><span class="kbd">{{ r[1] }}</span></div>
    </section>
    <p class="muted" style="margin:var(--sp-3) 0 0">Windows/Linux'da ⌘ o'rniga Ctrl.</p>
    <template #footer><button class="primary" @click="emit('close')">Yopish</button></template>
  </Dialog>
</template>
