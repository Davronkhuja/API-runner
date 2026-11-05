<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { runGuard } from '../lib/ui'
import Icon from './Icon.vue'

const mode = ref<'get' | 'all'>('get')
const typed = ref('')
const g = runGuard
const input = ref<HTMLInputElement>()
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const counts = computed(() => g.value?.counts ?? {})
const gets = computed(() => counts.value.GET ?? 0)
const writes = computed(() => (g.value?.total ?? 0) - gets.value)
const locked = computed(() => mode.value === 'all' && typed.value.trim() !== 'prod')
watch(g, v => { if (v) { mode.value = 'get'; typed.value = '' } })
watch(mode, async m => { if (m === 'all') { await nextTick(); input.value?.focus() } })
function go() { if (!g.value) return; if (mode.value === 'all' && locked.value) return; g.value.resolve(mode.value) }
</script>

<template>
  <div v-if="g" class="overlay" @keydown.esc="g.resolve(null)">
    <div class="dialog runguard" role="dialog" aria-modal="true" aria-labelledby="rg-title" data-testid="runguard">
      <div style="display:flex;gap:14px">
        <span class="rg-icon"><Icon name="alert" :size="20" /></span>
        <div>
          <h2 id="rg-title">Prod muhitida {{ g.total }} ta so'rov ishga tushadi</h2>
          <p>«{{ g.envName }}» faol.{{ writes ? " Ma'lumotni o'zgartiradigan so'rovlar ham bor." : '' }}</p>
        </div>
      </div>
      <div class="rg-counts">
        <div v-for="m in METHODS" :key="m" :class="'c-' + m.toLowerCase()" :data-testid="'rg-count-' + m"><span class="m" :class="'m-' + m">{{ m }}</span><b>{{ counts[m] ?? 0 }}</b></div>
      </div>
      <label class="opt" :class="{ on: mode === 'get' }"><input v-model="mode" type="radio" value="get" aria-label="Faqat GET" data-testid="rg-get">
        <span><b>Faqat GET so'rovlarni ishga tushirish <small class="ok-t">tavsiya</small></b><span>{{ gets }} ta so'rov · hech narsa o'zgarmaydi</span></span></label>
      <label class="opt" :class="{ on: mode === 'all' }"><input v-model="mode" type="radio" value="all" aria-label="Hammasi" data-testid="rg-all">
        <span><b>Hammasini ishga tushirish</b><span>{{ writes }} ta o'zgartiruvchi so'rov ham yuboriladi</span></span></label>
      <label v-if="mode === 'all'" class="rg-type">Tasdiqlash uchun muhit turini yozing: <b>prod</b>
        <input ref="input" v-model="typed" aria-label="Muhit nomi" data-testid="rg-type" autocomplete="off" spellcheck="false" @keydown.enter="go"></label>
      <div class="btns">
        <button data-testid="rg-cancel" @click="g.resolve(null)">Bekor qilish</button>
        <button v-if="mode === 'get'" class="primary" data-testid="rg-run" :disabled="!gets" @click="go">{{ gets }} ta GET'ni ishga tushirish</button>
        <button v-else class="danger" data-testid="rg-run-all" :disabled="locked" @click="go">{{ g.total }} tasini ishga tushirish</button>
      </div>
    </div>
  </div>
</template>
