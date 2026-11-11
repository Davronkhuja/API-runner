<script setup lang="ts">
/** Runner xavfsizlik dialogi: tanlovda yozuvchi metod (POST/PUT/PATCH/DELETE) bo'lsa — har doim; Prod muhitda — har doim. Metodlar, host'lar, «Faqat xavfsiz metodlar» (tavsiya). */
import { computed, nextTick, ref, watch } from 'vue'
import { runGuard } from '../lib/ui'
import { hostLabel, SAFE_METHODS } from '../lib/safety'
import Dialog from './Dialog.vue'

const mode = ref<'get' | 'all'>('get')
const typed = ref('')
const g = runGuard
const input = ref<HTMLInputElement>()
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const counts = computed(() => g.value?.counts ?? {})
const safeN = computed(() => SAFE_METHODS.reduce((n, m) => n + (counts.value[m] ?? 0), 0))       // GET + HEAD + OPTIONS
const writes = computed(() => (g.value?.total ?? 0) - safeN.value)
const isProd = computed(() => g.value?.envKind === 'prod')
const word = computed(() => (isProd.value ? 'prod' : 'tasdiqlayman'))                           // «Hammasi» uchun tasdiq so'zi
const locked = computed(() => mode.value === 'all' && typed.value.trim() !== word.value)
const riskyHosts = computed(() => (g.value?.hosts ?? []).filter(h => !h.safe && h.writes))
const title = computed(() => (writes.value ? `${writes.value} ta so'rov ma'lumotni o'zgartirishi mumkin` : `Prod muhitida ${g.value?.total ?? 0} ta so'rov ishga tushadi`))
watch(g, v => { if (v) { mode.value = 'get'; typed.value = '' } })
watch(mode, async m => { if (m === 'all') { await nextTick(); input.value?.focus() } })
function go() { if (!g.value) return; if (mode.value === 'all' && locked.value) return; g.value.resolve(mode.value) }
</script>

<template>
  <Dialog v-if="g" :title="title" testid="runguard" width="600px" @close="g.resolve(null)">
    <p class="rg-sub">{{ g.envName ? `«${g.envName}» faol.` : 'Faol muhit yo\'q.' }}{{ writes ? " Tanlovda ma'lumotni o'zgartiradigan so'rovlar bor." : '' }}</p>
      <div class="rg-counts">
        <div v-for="m in METHODS" :key="m" :class="'c-' + m.toLowerCase()" :data-testid="'rg-count-' + m"><span class="m" :class="'m-' + m">{{ m }}</span><b>{{ counts[m] ?? 0 }}</b></div>
      </div>
      <div class="rg-hosts" data-testid="rg-hosts" role="list" aria-label="Host'lar">
        <div v-for="h in g.hosts" :key="h.host ?? '?'" role="listitem" class="rg-host" :class="{ risky: !h.safe && h.writes }" data-testid="rg-host">
          <code>{{ hostLabel(h.host) }}</code><span class="muted">{{ h.count }} ta so'rov{{ h.writes ? `, ${h.writes} tasi o'zgartiruvchi` : '' }}</span>
          <span class="status-pill" :class="h.safe ? 'ok' : 'err'">{{ h.safe ? 'test/dev host' : 'prod yoki noma\'lum' }}</span>
        </div>
      </div>
      <p v-if="riskyHosts.length" class="state-error rg-warn" role="alert" data-testid="rg-warn">O'zgartiruvchi so'rovlar test/dev ro'yxatida bo'lmagan host'larga ketadi: <b>{{ riskyHosts.map(h => hostLabel(h.host)).join(', ') }}</b></p>
      <label class="opt" :class="{ on: mode === 'get' }"><input v-model="mode" type="radio" value="get" aria-label="Faqat xavfsiz metodlar" data-testid="rg-get">
        <span><b>Faqat xavfsiz metodlar (GET/HEAD/OPTIONS) <small class="ok-t">tavsiya</small></b><span>{{ safeN }} ta so'rov · hech narsa o'zgarmaydi</span></span></label>
      <label class="opt" :class="{ on: mode === 'all' }"><input v-model="mode" type="radio" value="all" aria-label="Hammasi" data-testid="rg-all">
        <span><b>Hammasini ishga tushirish</b><span>{{ writes }} ta o'zgartiruvchi so'rov ham yuboriladi</span></span></label>
      <label v-if="mode === 'all'" class="rg-type">Tasdiqlash uchun <b data-testid="rg-word">{{ word }}</b> deb yozing:
        <input ref="input" v-model="typed" aria-label="Tasdiq so'zi" data-testid="rg-type" autocomplete="off" spellcheck="false" @keydown.enter="go"></label>
    <template #footer>
        <button data-testid="rg-cancel" @click="g.resolve(null)">Bekor qilish</button>
        <button v-if="mode === 'get'" class="primary" data-testid="rg-run" :disabled="!safeN" @click="go">{{ safeN }} ta xavfsiz so'rovni ishga tushirish</button>
        <button v-else class="danger" data-testid="rg-run-all" :disabled="locked" @click="go">{{ g.total }} tasini ishga tushirish</button>
    </template>
  </Dialog>
</template>
