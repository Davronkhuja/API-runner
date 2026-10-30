<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useHistory } from '../stores/history'
import { openFromHistory } from '../lib/history'

const open = defineModel<boolean>({ required: true })
const hist = useHistory()
const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape' && open.value) open.value = false }
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))
const pick = (h: any) => { openFromHistory(h); open.value = false }
const when = (ts: number) => new Date(ts * 1000).toLocaleString()
</script>

<template>
  <template v-if="open">
    <div class="drawer-backdrop" data-testid="drawer-backdrop" @click="open = false" />
    <aside class="hist-drawer" data-testid="history-drawer">
      <div style="display:flex;gap:8px;align-items:center;padding:10px;border-bottom:1px solid var(--bd)">
        <b style="flex:1">So'rovlar tarixi</b>
        <button class="ghost" data-testid="hd-clear" @click="hist.clear('request')">Tozalash</button>
        <button class="ghost" data-testid="hd-close" @click="open = false">×</button>
      </div>
      <div style="flex:1;overflow:auto">
        <div v-for="h in hist.items" :key="h.id" class="row" style="padding:6px 10px" data-testid="hd-row" @click="pick(h)">
          <span class="m" :class="'m-' + h.payload.method">{{ h.payload.method }}</span>
          <span class="name"><span>{{ h.payload.url }}</span><br><span class="muted">{{ when(h.ts) }}</span></span>
          <button class="ghost" @click.stop="hist.remove(h.id)">×</button>
        </div>
        <div v-if="!hist.items.length" class="empty" data-testid="hd-empty">Hali tarix yo'q</div>
      </div>
    </aside>
  </template>
</template>
