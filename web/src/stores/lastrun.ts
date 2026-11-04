import { defineStore } from 'pinia'
import { ref } from 'vue'

/** Har so'rovning oxirgi natijasi va har doira (collection/papka) uchun oxirgi Runner natijalari — brauzerda (localStorage). */
export interface LastResult { status: number | string; time: number; at: number }
export interface LastRun { at: number; items: { id: string; status: number | string }[] }
const KEY = 'apirunner.lastrun.v1'

function load(): { results: Record<string, LastResult>; runs: Record<string, LastRun> } {
  try { const d = JSON.parse(localStorage.getItem(KEY) ?? 'null'); if (d?.results && d?.runs) return d } catch { /* bo'sh */ }
  return { results: {}, runs: {} }
}

export const isOkStatus = (s: number | string) => typeof s === 'number' && s < 400

export const useLastRun = defineStore('lastrun', () => {
  const init = load()
  const results = ref<Record<string, LastResult>>(init.results)
  const runs = ref<Record<string, LastRun>>(init.runs)
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ results: results.value, runs: runs.value })) } catch { /* to'lgan/bloklangan */ } }
  function setResult(ref_: string | null | undefined, status: number | string, time: number) {
    if (!ref_) return
    results.value[ref_] = { status, time, at: Date.now() }; save()
  }
  function setRun(scope: string, items: LastRun['items']) { runs.value[scope] = { at: Date.now(), items }; save() }
  return { results, runs, setResult, setRun }
})
