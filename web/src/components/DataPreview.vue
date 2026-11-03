<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ rows: Record<string, unknown>[]; limit?: number }>()
const cols = computed(() => [...new Set(props.rows.slice(0, 20).flatMap(r => Object.keys(r ?? {})))].slice(0, 12))
const shown = computed(() => props.rows.slice(0, props.limit ?? 5))
</script>

<template>
  <div class="data-preview" data-testid="data-preview">
    <table class="kv">
      <thead><tr><th>#</th><th v-for="c in cols" :key="c">{{ c }}</th></tr></thead>
      <tbody><tr v-for="(r, i) in shown" :key="i"><td class="muted">{{ i + 1 }}</td><td v-for="c in cols" :key="c">{{ typeof r?.[c] === 'object' ? JSON.stringify(r?.[c]) : r?.[c] }}</td></tr></tbody>
    </table>
    <div v-if="rows.length > shown.length" class="muted">… yana {{ rows.length - shown.length }} qator</div>
  </div>
</template>
