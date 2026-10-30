import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { del, get, post, put } from '../api/client'
import type { Environment, EnvValue } from '../types/model'

export const useWorkspace = defineStore('workspace', () => {
  const environments = ref<Environment[]>([])
  const globals = ref<EnvValue[]>([])
  const activeEnvId = ref<string | null>(null)
  const version = ref('')

  async function load() {
    const w = await get('/api/workspace')
    environments.value = w.environments
    globals.value = w.globals.values
    activeEnvId.value = w.meta.active_environment_id ?? null
    version.value = (await get('/api/version')).version
  }
  const activeEnv = computed(() => environments.value.find(e => e.id === activeEnvId.value) ?? null)
  /** Faol env'ning yoqilgan o'zgaruvchilari (globals ustiga). */
  const activeVars = computed<Record<string, string>>(() => {
    const out: Record<string, string> = {}
    for (const v of globals.value) if (v.enabled && v.key) out[v.key] = v.value
    for (const v of activeEnv.value?.values ?? []) if (v.enabled && v.key) out[v.key] = v.value
    return out
  })
  async function setActive(id: string | null) { activeEnvId.value = id; await put('/api/workspace/meta', { active_environment_id: id }) }
  async function createEnv(name: string) { const r = await post('/api/environments', { name }); await load(); return r.id as string }
  async function saveEnv(env: Environment) { await put(`/api/environments/${env.id}`, env); await load() }
  async function deleteEnv(id: string) { await del(`/api/environments/${id}`); if (activeEnvId.value === id) await setActive(null); await load() }
  return { environments, globals, activeEnvId, activeEnv, activeVars, version, load, setActive, createEnv, saveEnv, deleteEnv }
})
