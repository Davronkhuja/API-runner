<script setup lang="ts">
import { computed } from 'vue'
import { useTree } from '../stores/tree'
import type { Tab } from '../stores/tabs'
const props = defineProps<{ tab: Tab }>()
const tree = useTree()
const col = computed(() => tree.cols[props.tab.ref!])
const meta = computed(() => tree.metas.find(m => m.id === props.tab.ref))
</script>
<template>
  <div class="editor" data-testid="tab-collection">
    <h3>{{ col?.info.name }}</h3>
    <p class="muted">{{ meta?.requests ?? 0 }} ta so'rov</p>
    <p class="muted">Auth, o'zgaruvchilar, skriptlar va tavsif (meros) — keyingi bosqich.</p>
  </div>
</template>
