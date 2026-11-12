import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { del, get, post, put } from '../api/client'
import type { Environment, EnvValue } from '../types/model'
import { cleanSettings, DEFAULT_AUTH_OFFERS, DEFAULT_SAFETY, type AuthOffers, type ReqSettings, type Safety } from '../lib/settings'

export interface ScriptLimits { timeout_ms: number; memory_mb: number; max_requests: number }

export const useWorkspace = defineStore('workspace', () => {
  const environments = ref<Environment[]>([])
  const globals = ref<EnvValue[]>([])
  const activeEnvId = ref<string | null>(null)
  const version = ref('')
  const authOffers = ref<AuthOffers>({ ...DEFAULT_AUTH_OFFERS, nodes: {} })
  const safety = ref<Safety>({ ...DEFAULT_SAFETY })           // host/metod xavfsizligi (workspace meta)
  const nameCleanDismissed = ref(false)         // "Nomlarni tozalash" taklifi yopilgan (workspace meta'da saqlanadi)
  const settings = ref<ReqSettings>({})
  const scripts = ref<{ available: boolean; version: string | null; install: string; limits: ScriptLimits; defaults: ScriptLimits }>({ available: true, version: null, install: '', limits: { timeout_ms: 10000, memory_mb: 64, max_requests: 10 }, defaults: { timeout_ms: 10000, memory_mb: 64, max_requests: 10 } })

  async function load() {
    const w = await get('/api/workspace')
    environments.value = w.environments
    globals.value = w.globals.values
    activeEnvId.value = w.meta.active_environment_id ?? null
    settings.value = w.meta.settings ?? {}
    safety.value = { ...DEFAULT_SAFETY, ...(w.meta.safety ?? {}) }
    authOffers.value = { ...DEFAULT_AUTH_OFFERS, ...(w.meta.auth_offers ?? {}) }
    nameCleanDismissed.value = !!w.meta.nameclean_dismissed
    try { scripts.value = await get('/api/scripts/status') } catch { /* eski server */ }
    version.value = (await get('/api/version')).version
  }
  const activeEnv = computed(() => environments.value.find(e => e.id === activeEnvId.value) ?? null)
  /** Faol env'ning yoqilgan o'zgaruvchilari (globals ustiga). */
  const activeVars = computed<Record<string, string>>(() => {
    const out: Record<string, string> = {}
    for (const v of globals.value) if (v.enabled && v.key) out[v.key] = v.current ?? v.value
    for (const v of activeEnv.value?.values ?? []) if (v.enabled && v.key) out[v.key] = v.current ?? v.value
    return out
  })
  async function dismissNameClean() { nameCleanDismissed.value = true; await put('/api/workspace/meta', { nameclean_dismissed: true }) }
  async function setActive(id: string | null) { activeEnvId.value = id; await put('/api/workspace/meta', { active_environment_id: id }) }
  async function createEnv(name: string) { const r = await post('/api/environments', { name }); await load(); return r.id as string }
  async function saveEnv(env: Environment) { await put(`/api/environments/${env.id}`, env); await load() }
  async function saveGlobals(values: EnvValue[]) { await put('/api/globals', { values }); await load() }
  async function saveSettings(s: ReqSettings) { await put('/api/workspace/meta', { settings: cleanSettings(s) }); await load() }
  async function saveAuthOffers(o: AuthOffers) { authOffers.value = o; await put('/api/workspace/meta', { auth_offers: o }) }
  async function saveSafety(s: Safety) { await put('/api/workspace/meta', { safety: s }); await load() }
  async function saveScriptLimits(l: ScriptLimits) { await put('/api/workspace/meta', { script_limits: l }); await load() }
  async function deleteEnv(id: string) { await del(`/api/environments/${id}`); if (activeEnvId.value === id) await setActive(null); await load() }
  return { nameCleanDismissed, dismissNameClean, environments, globals, activeEnvId, activeEnv, activeVars, version, load, setActive, createEnv, saveEnv, saveGlobals, settings, saveSettings, safety, saveSafety, authOffers, saveAuthOffers, scripts, saveScriptLimits, deleteEnv }
})
