<script setup lang="ts">
/** Yagona yuklanish / xato / bo'sh holat bloki (ro'yxat va dialoglar uchun). Xatoda «Qayta urinish» tugmasi. */
defineProps<{ kind: 'loading' | 'error' | 'empty'; text?: string; testid?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="kind === 'loading'" class="state-loading" role="status" :data-testid="testid ?? 'state-loading'"><span class="spinner" aria-hidden="true" />{{ text ?? 'Yuklanmoqda…' }}</div>
  <div v-else-if="kind === 'error'" class="state-error" role="alert" :data-testid="testid ?? 'state-error'">
    <span>{{ text ?? 'Yuklab bo\'lmadi' }}</span>
    <button class="sm" data-testid="state-retry" @click="$emit('retry')">Qayta urinish</button>
  </div>
  <div v-else class="state-empty" role="status" :data-testid="testid ?? 'state-empty'">{{ text ?? 'Hozircha bo\'sh' }}</div>
</template>
