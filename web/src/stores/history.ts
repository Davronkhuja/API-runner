import { defineStore } from 'pinia'
import { ref } from 'vue'
import { del, get, post } from '../api/client'

export interface HistoryEntry { id: number; kind: 'request' | 'run' | 'url'; ts: number; source: string; payload: any }

export const useHistory = defineStore('history', () => {
  const items = ref<HistoryEntry[]>([])
  const urls = ref<HistoryEntry[]>([])
  const runs = ref<HistoryEntry[]>([])
  async function load() {
    items.value = await get('/api/history?kind=request&limit=30')
    urls.value = await get('/api/history?kind=url&limit=40')
    runs.value = await get('/api/history?kind=run&limit=15')
  }
  async function add(kind: HistoryEntry['kind'], payload: unknown) { await post('/api/history', { kind, payload }); await load() }
  async function remove(id: number) { await del(`/api/history?id=${id}`); await load() }
  async function clear(kind = 'request') { await del(`/api/history?kind=${kind}`); await load() }
  return { items, urls, runs, load, add, remove, clear }
})
