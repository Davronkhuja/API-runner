<script setup lang="ts">
/** Bosilganda inline input'ga aylanadigan nom. Enter/blur — saqlash, Esc — bekor. Yaroqsiz nom (bo'sh/takror) — xabar. */
import { nextTick, ref, watch } from 'vue'
import { showToast } from '../lib/ui'

const props = defineProps<{ value: string; testid: string; validate?: (v: string) => string | null; commit: (v: string) => Promise<boolean> | boolean; unsaved?: boolean; label?: string }>()
const emit = defineEmits<{ unsaved: [] }>()
const editing = defineModel<boolean>('editing', { default: false })
const text = ref(props.value)
const inp = ref<HTMLInputElement>()
let done = false                                  // Enter/Esc dan keyin kelgan blur ikkinchi marta ishlamasin

function start() {
  if (props.unsaved) { emit('unsaved'); return }       // saqlanmagan yangi so'rov: avval "Saqlash" dialogi
  text.value = props.value; done = false; editing.value = true
}
watch(editing, async on => {
  if (!on) return
  text.value = props.value; done = false
  await nextTick()
  inp.value?.focus(); inp.value?.select()          // dinamik elementda autofocus ishonchsiz — qo'lda fokus + belgilash
})
async function finish(mode: 'enter' | 'blur') {
  if (done) return
  const v = text.value.trim()
  const err = props.validate?.(text.value) ?? (v ? null : "Nom bo'sh bo'lishi mumkin emas")
  if (err) {
    showToast(err, 'warn')
    if (mode === 'enter') { await nextTick(); inp.value?.focus(); return }      // Enter: tahrirda qoladi
    done = true; editing.value = false; return                                  // blur: bekor
  }
  done = true
  if (v !== props.value) await props.commit(v)
  editing.value = false
}
function cancel() { done = true; editing.value = false }
</script>

<template>
  <input v-if="editing" ref="inp" v-model="text" class="inline-name-input" :data-testid="testid + '-input'" :aria-label="label ?? 'Yangi nom'" @click.stop @keydown.stop @keydown.enter.prevent="finish('enter')" @keydown.esc.prevent="cancel" @blur="finish('blur')">
  <span v-else class="inline-name" role="button" tabindex="0" :data-testid="testid" :title="unsaved ? 'Saqlash uchun bosing' : 'Nomini o\'zgartirish uchun bosing'" @click="start" @keydown.enter.prevent="start" @keydown.f2.prevent="start"><slot>{{ value }}</slot></span>
</template>
