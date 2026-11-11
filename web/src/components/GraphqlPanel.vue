<script setup lang="ts">
/** GraphQL tanasi: sxemani yuklash (introspection), schema explorer, so'rov muharriri (avtoto'ldirish + validatsiya), variables tekshiruvi. */
import { computed, onMounted, ref } from 'vue'
import CodeEditor from './CodeEditor.vue'
import GraphqlEditor from './GraphqlEditor.vue'
import { clearCached, fieldsOf, gqlState, introspect, loadCached, rootTypes, skeleton, skeletonVariables, userTypes, variableIssues } from '../lib/graphql'
import { getNamedType, isEnumType, isInputObjectType, type GraphQLField, type GraphQLNamedType } from 'graphql'
import { useTabs, type Tab } from '../stores/tabs'

const props = defineProps<{ tab: Tab }>()
const tabs = useTabs()
const d = computed(() => props.tab.draft!)
const st = computed(() => gqlState(props.tab.id))
const touch = () => tabs.touch(props.tab.id)
const open = ref(false)
onMounted(() => { loadCached(props.tab) })
const when = computed(() => (st.value.at ? new Date(st.value.at).toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''))
const q = ref('')
const picked = ref<any>(null)
const roots = computed(() => (st.value.schema ? rootTypes(st.value.schema) : []))
const types = computed(() => (st.value.schema ? userTypes(st.value.schema).filter(t => !q.value || t.name.toLowerCase().includes(q.value.toLowerCase())) : []))
const issues = computed(() => variableIssues(d.value.body.gql.query, d.value.body.gql.variables))
function useField(op: 'query' | 'mutation' | 'subscription', f: GraphQLField<any, any>) {
  const g = d.value.body.gql
  g.query = skeleton(op, f); g.variables = skeletonVariables(f); touch()
}
const argsText = (f: GraphQLField<any, any>) => f.args.map(a => `${a.name}: ${a.type}`).join(', ')
const kindOf = (t: GraphQLNamedType) => (isEnumType(t) ? 'enum' : isInputObjectType(t) ? 'input' : t.constructor.name.replace('GraphQL', '').replace('Type', '').toLowerCase())
</script>

<template>
  <div class="gql-panel2" data-testid="graphql-panel">
    <div class="gql-bar">
      <button data-testid="gql-introspect" :disabled="st.loading" @click="introspect(tab)">{{ st.loading ? 'Yuklanmoqda…' : st.schema ? 'Sxemani yangilash' : 'Sxemani yuklash (introspection)' }}</button>
      <button :class="{ on: open }" :aria-pressed="open" :disabled="!st.schema" data-testid="gql-explorer-toggle" @click="open = !open">Schema explorer</button>
      <span v-if="st.schema" class="muted" data-testid="gql-schema-info">{{ userTypes(st.schema).length }} ta tur · {{ roots.map(r => r[0]).join(', ') }} · <span data-testid="gql-cache-info">{{ st.fromCache ? 'diskdagi keshdan' : 'yuklandi' }} ({{ when }})</span></span>
      <button v-if="st.schema" class="ghost" data-testid="gql-cache-clear" title="Diskdagi sxema keshini o'chirish" @click="clearCached(tab)">Keshni tozalash</button>
      <span v-else-if="!st.error" class="muted">Sxema yuklanmagan — avtoto'ldirish va validatsiya o'chiq.</span>
      <span v-if="st.error" class="err" role="alert" data-testid="gql-error">{{ st.error }}</span>
    </div>
    <div class="gql-body">
      <aside v-if="open && st.schema" class="gql-explorer scroll" data-testid="gql-explorer" aria-label="Schema explorer">
        <template v-if="!picked">
          <section v-for="[op, t] in roots" :key="op"><h4>{{ op }}</h4>
            <button v-for="f in fieldsOf(t)" :key="f.name" class="gql-f" data-testid="gql-field" :title="f.description ?? ''" @click="useField(op.toLowerCase() as any, f)"><b>{{ f.name }}</b><small class="muted">{{ argsText(f) ? `(${argsText(f)})` : '' }}: {{ f.type }}</small></button>
          </section>
          <h4>Turlar</h4>
          <input v-model="q" type="search" placeholder="Tur qidirish…" aria-label="Tur qidirish" data-testid="gql-type-search">
          <button v-for="t in types" :key="t.name" class="gql-f" data-testid="gql-type" @click="picked = t"><b>{{ t.name }}</b><small class="muted">{{ kindOf(t) }}</small></button>
        </template>
        <template v-else>
          <button class="ghost" data-testid="gql-back" @click="picked = null">← Orqaga</button>
          <h4 data-testid="gql-type-name">{{ picked.name }} <small class="muted">{{ kindOf(picked) }}</small></h4>
          <p v-if="picked.description" class="muted">{{ picked.description }}</p>
          <template v-if="isEnumType(picked)"><div v-for="v in picked.getValues()" :key="v.name" class="gql-f static"><b>{{ v.name }}</b></div></template>
          <template v-else-if="isInputObjectType(picked)"><div v-for="f in Object.values(picked.getFields())" :key="f.name" class="gql-f static"><b>{{ f.name }}</b><small class="muted">: {{ f.type }}</small></div></template>
          <template v-else><button v-for="f in fieldsOf(picked)" :key="f.name" class="gql-f" :title="f.description ?? ''" @click="picked = getNamedType(f.type)"><b>{{ f.name }}</b><small class="muted">{{ argsText(f) ? `(${argsText(f)})` : '' }}: {{ f.type }}</small></button></template>
        </template>
      </aside>
      <div class="gql-edit">
        <b>Query</b>
        <GraphqlEditor v-model="d.body.gql.query" :schema="st.schema" testid="gql-query" class="body-editor gql-q" @update:model-value="touch" />
        <b>Variables (JSON)</b>
        <CodeEditor v-model="d.body.gql.variables" lang="json" testid="gql-vars" label="GraphQL variables" placeholder='{ "id": 1 }' class="body-editor gql-v" @update:model-value="touch" />
        <ul v-if="issues.length" class="gql-issues" role="alert" data-testid="gql-issues"><li v-for="i in issues" :key="i">⚠ {{ i }}</li></ul>
      </div>
    </div>
  </div>
</template>
