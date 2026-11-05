<script setup lang="ts">
/** Muhit "ko'z" popover'i (Postman'dagidek): faol muhit va Globals o'zgaruvchilari joriy qiymatlari bilan, joyida tahrirlash. */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useWorkspace } from '../stores/workspace'
import { useTabs } from '../stores/tabs'
import { showToast } from '../lib/ui'
import type { EnvValue } from '../types/model'

const emit = defineEmits<{ close: [] }>()
const ws = useWorkspace(), tabs = useTabs()
const root = ref<HTMLElement>()
const shown = ref<Record<string, boolean>>({})
const eff = (v: EnvValue) => v.current ?? v.value ?? ''
const masked = (v: EnvValue, scope: string) => v.type === 'secret' && !shown.value[scope + v.key]

async function setCurrent(scope: 'env' | 'globals', v: EnvValue, val: string) {
  if (val === eff(v)) return
  try {
    if (scope === 'globals') {
      await ws.saveGlobals(ws.globals.map(g => (g.key === v.key ? { ...g, current: val } : g)))
    } else if (ws.activeEnv) {
      const e = ws.activeEnv
      await ws.saveEnv({ ...e, values: e.values.map(g => (g.key === v.key ? { ...g, current: val } : g)) })
    }
  } catch (e: any) { showToast(e.message, 'error') }
}
function openAll() {
  const e = ws.activeEnv
  if (e) tabs.open('environment', e.id, e.name, { permanent: true }); else tabs.open('environment', 'globals', 'Globals', { permanent: true })
  emit('close')
}
const onDoc = (e: MouseEvent) => { if (root.value && !root.value.contains(e.target as Node) && !(e.target as HTMLElement).closest('[data-testid=env-vars-btn]')) emit('close') }
const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
onMounted(() => { document.addEventListener('mousedown', onDoc); document.addEventListener('keydown', onKey); root.value?.querySelector<HTMLInputElement>('input')?.focus() })
onBeforeUnmount(() => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey) })
</script>

<template>
  <div ref="root" class="qlook" role="dialog" aria-label="Muhit o'zgaruvchilari" data-testid="env-quicklook">
    <div class="ql-body">
      <section v-for="sec in [{ id: 'env' as const, title: ws.activeEnv ? `Faol muhit — ${ws.activeEnv.name}` : 'Faol muhit yo\'q', rows: ws.activeEnv?.values ?? [] }, { id: 'globals' as const, title: 'Globals', rows: ws.globals }]" :key="sec.id" :data-testid="'ql-' + sec.id">
        <h3>{{ sec.title }}</h3>
        <p v-if="!sec.rows.filter(v => v.key).length" class="muted ql-empty">{{ sec.id === 'env' && !ws.activeEnv ? 'Muhit tanlanmagan' : "O'zgaruvchi yo'q" }}</p>
        <div v-for="v in sec.rows.filter(x => x.key)" :key="v.key" class="ql-row" data-testid="ql-row">
          <code :title="v.key">{{ v.key }}</code>
          <input :type="masked(v, sec.id) ? 'password' : 'text'" :value="eff(v)" :aria-label="`${v.key} — joriy qiymat`" data-testid="ql-cur" @change="setCurrent(sec.id, v, ($event.target as HTMLInputElement).value)" @keydown.enter="($event.target as HTMLInputElement).blur()">
          <button v-if="v.type === 'secret'" class="ib" :aria-label="shown[sec.id + v.key] ? 'Yashirish' : 'Ko\'rsatish'" @click="shown[sec.id + v.key] = !shown[sec.id + v.key]">👁</button>
        </div>
      </section>
    </div>
    <footer class="ql-foot"><span class="muted">Joriy qiymatlar faqat shu kompyuterda saqlanadi</span><button class="linkbtn" data-testid="ql-open-all" @click="openAll">Hammasini ochish</button></footer>
  </div>
</template>
