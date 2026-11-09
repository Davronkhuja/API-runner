<script setup lang="ts">
/** Workspace bo'ylab Find & Replace: oldindan ko'rish (har natija uchun tanlash), avtomatik zaxira bilan almashtirish. */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Dialog from './Dialog.vue'
import { askConfirm, showToast } from '../lib/ui'
import { useTree } from '../stores/tree'
import { useWorkspace } from '../stores/workspace'
import { ALL_TARGETS, frApply, frSearch, groupResults, TARGET_LABELS, type FrResult } from '../lib/findreplace'

const emit = defineEmits<{ close: [] }>()
const tree = useTree(), ws = useWorkspace()
const o = ref({ query: '', replacement: '', case: false, word: false, regex: false, targets: [...ALL_TARGETS] as string[], scope: '' })
const results = ref<FrResult[]>([]), total = ref(0), truncated = ref(false)
const picked = ref<Set<string>>(new Set())
const err = ref(''), busy = ref(false), searched = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined, seq = 0
const opts = () => ({ query: o.value.query, replacement: o.value.replacement, case: o.value.case, word: o.value.word, regex: o.value.regex, targets: o.value.targets, ...(o.value.scope ? { collection_ids: [o.value.scope] } : {}) })

async function run() {
  const my = ++seq
  if (!o.value.query) { results.value = []; total.value = 0; searched.value = false; err.value = ''; picked.value = new Set(); return }
  try {
    const d = await frSearch(opts())
    if (my !== seq) return
    results.value = d.results; total.value = d.total; truncated.value = d.truncated; err.value = ''; searched.value = true
    picked.value = new Set(d.results.map(r => r.id))                       // sukut: hammasi tanlangan; foydalanuvchi ko'rib chiqib olib tashlaydi
  } catch (e: any) { if (my === seq) { err.value = e.message; results.value = []; total.value = 0; picked.value = new Set() } }
}
watch(o, () => { clearTimeout(timer); timer = setTimeout(run, 300) }, { deep: true })
onMounted(() => document.querySelector<HTMLInputElement>('[data-testid=fr-query]')?.focus())
onBeforeUnmount(() => clearTimeout(timer))

const groups = computed(() => groupResults(results.value))
const pickedCount = computed(() => results.value.filter(r => picked.value.has(r.id)).length)
const pickedRepl = computed(() => results.value.filter(r => picked.value.has(r.id)).reduce((n, r) => n + r.count, 0))
function toggle(id: string) { const s = new Set(picked.value); if (s.has(id)) s.delete(id); else s.add(id); picked.value = s }
const allOn = computed(() => results.value.length > 0 && pickedCount.value === results.value.length)
const toggleAll = () => { picked.value = allOn.value ? new Set() : new Set(results.value.map(r => r.id)) }
function toggleTarget(t: string) { const a = o.value.targets; o.value.targets = a.includes(t) ? a.filter(x => x !== t) : [...a, t] }

async function apply() {
  if (!pickedCount.value || busy.value) return
  const risky = o.value.regex ? ' (regex)' : ''
  if (!(await askConfirm(`${pickedCount.value} ta maydonda ${pickedRepl.value} ta almashtirish${risky} bajariladi. Oldin avtomatik zaxira olinadi (Sozlamalar → Zaxira nusxalar orqali qaytarish mumkin). Davom etilsinmi?`, 'Almashtirish'))) return
  busy.value = true
  try {
    const r = await frApply(opts(), [...picked.value])
    await Promise.all([tree.load(), ws.load()])
    showToast(`${r.replacements} ta almashtirish (${r.documents} ta hujjat). Zaxira: ${r.backup}${r.skipped.length ? ` · ${r.skipped.length} ta o'tkazib yuborildi` : ''}`, 'success', 6000)
    await run()
  } catch (e: any) { showToast(e.message, 'error') } finally { busy.value = false }
}
</script>

<template>
  <Dialog title="Find & Replace — butun workspace" testid="fr-dialog" width="min(900px,94vw)" @close="emit('close')">
    <div class="fr-form">
      <label class="dlg-field"><span>Topish</span><input v-model="o.query" data-testid="fr-query" data-autofocus placeholder="Qidiriladigan matn" spellcheck="false" style="width:100%"></label>
      <label class="dlg-field"><span>Almashtirish</span><input v-model="o.replacement" data-testid="fr-replacement" :placeholder="o.regex ? 'Matn ($1 emas, \\1 guruhlari)' : 'Yangi matn'" spellcheck="false" style="width:100%"></label>
      <div class="fr-opts" role="group" aria-label="Qidiruv sozlamalari">
        <button class="seg" :class="{ on: o.case }" :aria-pressed="o.case" title="Katta-kichik harfni farqlash" data-testid="fr-case" @click="o.case = !o.case">Aa</button>
        <button class="seg" :class="{ on: o.word }" :aria-pressed="o.word" title="Butun so'z" data-testid="fr-word" @click="o.word = !o.word">So'z</button>
        <button class="seg" :class="{ on: o.regex }" :aria-pressed="o.regex" title="Regex" data-testid="fr-regex" @click="o.regex = !o.regex">.*</button>
        <select v-model="o.scope" class="sm" aria-label="Qayerda" data-testid="fr-scope"><option value="">Hamma collection va muhitlar</option><option v-for="m in tree.metas" :key="m.id" :value="m.id">Faqat: {{ m.name }}</option></select>
      </div>
      <fieldset class="fr-targets"><legend class="muted">Qayerda qidirish</legend>
        <label v-for="t in TARGET_LABELS" :key="t[0]"><input type="checkbox" :checked="o.targets.includes(t[0])" :data-testid="'fr-target-' + t[0]" @change="toggleTarget(t[0])">{{ t[1] }}</label>
      </fieldset>
    </div>
    <p v-if="err" class="state-error" role="alert" data-testid="fr-error" style="padding:6px 10px">{{ err }}</p>
    <p v-else-if="searched && !results.length" class="muted" data-testid="fr-none">Hech narsa topilmadi.</p>
    <div v-else-if="results.length" class="fr-results" data-testid="fr-results">
      <label class="fr-all"><input type="checkbox" :checked="allOn" data-testid="fr-all" @change="toggleAll"><b>{{ total }} ta moslik, {{ results.length }} ta maydon</b><span v-if="truncated" class="muted"> · (ro'yxat qisqartirilgan — so'rovni toraytiring)</span></label>
      <section v-for="g in groups" :key="g.key" class="fr-group" data-testid="fr-group">
        <header><b>{{ g.title }}</b><small class="muted">{{ g.sub }}</small></header>
        <label v-for="r in g.rows" :key="r.id" class="fr-row" data-testid="fr-row">
          <input type="checkbox" :checked="picked.has(r.id)" :aria-label="`${g.title}: ${r.field}`" @change="toggle(r.id)">
          <span class="fr-body">
            <span class="fr-field">{{ r.field }}<span v-if="r.count > 1" class="badge">×{{ r.count }}</span></span>
            <span v-if="r.secret" class="muted">maxfiy qiymat — ko'rsatilmaydi (baribir almashtiriladi)</span>
            <span v-for="(s, i) in r.snippets" v-else :key="i" class="fr-snip" data-testid="fr-snippet"><template v-if="s.lead">…</template>{{ s.before }}<del>{{ s.match }}</del><ins>{{ s.replacement }}</ins>{{ s.after }}<template v-if="s.trail">…</template></span>
          </span>
        </label>
      </section>
    </div>
    <template #footer>
      <span class="muted" style="margin-right:auto" data-testid="fr-summary">{{ results.length ? `${pickedCount} ta maydon tanlangan · ${pickedRepl} ta almashtirish` : '' }}</span>
      <button @click="emit('close')">Yopish</button>
      <button class="primary" data-testid="fr-apply" :disabled="!pickedCount || busy" @click="apply">Almashtirish</button>
    </template>
  </Dialog>
</template>
