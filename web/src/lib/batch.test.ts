import { describe, expect, it } from 'vitest'
import { newBatchState, statsOf, toCSV } from './batch'

describe('batch helpers', () => {
  it('stats group 2xx/4xx/5xx, ok/err, avg', () => {
    const b = newBatchState(); b.total = 4
    b.results = [{ status: 200, time: 1, error: false }, { status: 404, time: 3, error: true }, { status: 503, time: 2, error: true }]
    expect(statsOf(b)).toMatchObject({ s2: 1, s4: 1, s5: 1, ok: 1, err: 2, total: 4, avg: 2 })
    expect(statsOf(newBatchState()).avg).toBeNull()
  })
  it('csv escapes quotes and objects', () => {
    const csv = toCSV([{ index: 1, status: 200, time: 0.1, size: 5, url: 'u', response: { a: '"x"' }, error: false }])
    expect(csv.split('\n')[0]).toBe('index,status,time,size,url,response,error')
    expect(csv).toContain('"{""a"":""\\""x\\""""}"')
  })
})
