<script setup lang="ts">
import { sidePanel, type SidePanel } from '../lib/ui'
import { useHistory } from '../stores/history'
import Icon from './Icon.vue'

const hist = useHistory()
const items: { id: SidePanel; label: string; icon: string; testid: string }[] = [
  { id: 'collections', label: 'Kolleksiya', icon: 'layers', testid: 'sb-collections' },
  { id: 'environments', label: 'Muhitlar', icon: 'globe', testid: 'sb-environments' },
  { id: 'history', label: 'Tarix', icon: 'clock', testid: 'sb-history' },
  { id: 'runner', label: 'Runner', icon: 'play', testid: 'sb-runner' },
]
function pick(id: SidePanel) { sidePanel.value = id; if (id === 'history') hist.load() }
</script>

<template>
  <nav class="rail" aria-label="Asosiy bo'limlar" data-testid="rail">
    <button v-for="i in items" :key="i.id" class="rail-btn" :class="{ on: sidePanel === i.id }" :data-testid="i.testid" :aria-pressed="sidePanel === i.id" :aria-label="i.label" @click="pick(i.id)">
      <Icon :name="i.icon" :size="18" /><span>{{ i.label }}</span>
    </button>
  </nav>
</template>
