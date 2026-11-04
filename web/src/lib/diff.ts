/** Javoblarni solishtirish (Tarix): qator bo'yicha diff, vaqt/ID maydonlarini e'tiborsiz qoldirish. */
export interface DiffLine { type: 'same' | 'add' | 'del'; text: string; a?: number; b?: number }

/** LCS asosida qator diff (kichik/o'rta javoblar uchun). Juda katta kirishda prefiks/suffiks kesiladi, o'rtasi to'liq almashtirilgan deb olinadi. */
export function lineDiff(a: string[], b: string[]): DiffLine[] {
  let s = 0
  while (s < a.length && s < b.length && a[s] === b[s]) s++
  let ea = a.length, eb = b.length
  while (ea > s && eb > s && a[ea - 1] === b[eb - 1]) { ea--; eb-- }
  const A = a.slice(s, ea), B = b.slice(s, eb)
  const out: DiffLine[] = []
  for (let i = 0; i < s; i++) out.push({ type: 'same', text: a[i], a: i + 1, b: i + 1 })
  if (A.length * B.length > 4_000_000) {
    A.forEach((t, i) => out.push({ type: 'del', text: t, a: s + i + 1 }))
    B.forEach((t, i) => out.push({ type: 'add', text: t, b: s + i + 1 }))
  } else {
    const n = A.length, m = B.length
    const L: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1))
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1])
    let i = 0, j = 0
    while (i < n && j < m) {
      if (A[i] === B[j]) { out.push({ type: 'same', text: A[i], a: s + i + 1, b: s + j + 1 }); i++; j++ }
      else if (L[i + 1][j] >= L[i][j + 1]) { out.push({ type: 'del', text: A[i], a: s + i + 1 }); i++ }
      else { out.push({ type: 'add', text: B[j], b: s + j + 1 }); j++ }
    }
    while (i < n) { out.push({ type: 'del', text: A[i], a: s + i + 1 }); i++ }
    while (j < m) { out.push({ type: 'add', text: B[j], b: s + j + 1 }); j++ }
  }
  for (let i = ea; i < a.length; i++) out.push({ type: 'same', text: a[i], a: i + 1, b: eb + (i - ea) + 1 })
  return out
}

/** Vaqt va identifikator maydonlari: id, *_id, uuid, timestamp, *_at, date, time, created/updated, expires, request/trace id. */
export const VOLATILE = /^(id|uuid|guid|_id|(.*[_-])?id|(.*[_-])?uuid|timestamp|ts|time|date|datetime|(.*[_-])?(at|time|date|timestamp)|created.*|updated.*|expires.*|exp|iat|nbf|trace.*|request.*)$/i

export function stripVolatile(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(stripVolatile)
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v as Record<string, unknown>).filter(([k]) => !VOLATILE.test(k)).map(([k, x]) => [k, stripVolatile(x)]))
  return v
}

/** Javob matni -> solishtiriladigan qatorlar (JSON bo'lsa chiroyli va tartiblangan kalitlar bilan). */
export function bodyLines(text: string, ignoreVolatile: boolean): string[] {
  const norm = (v: unknown): unknown => (Array.isArray(v) ? v.map(norm) : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v as object).sort().map(k => [k, norm((v as any)[k])])) : v)
  try { return JSON.stringify(norm(ignoreVolatile ? stripVolatile(JSON.parse(text)) : JSON.parse(text)), null, 2).split('\n') } catch { return String(text ?? '').split('\n') }
}

const HDR_VOLATILE = /^(date|x-request-id|x-trace-id|x-amzn-trace-id|etag|age|set-cookie|server-timing|cf-ray|x-correlation-id)$/i
/** Sarlavhalar farqi: [{key, a, b}] (faqat farq qilganlar). */
export function headerDiff(a: Record<string, string> = {}, b: Record<string, string> = {}, ignoreVolatile = true) {
  const lo = (h: Record<string, string>) => Object.fromEntries(Object.entries(h).map(([k, v]) => [k.toLowerCase(), v]))
  const A = lo(a), B = lo(b)
  return [...new Set([...Object.keys(A), ...Object.keys(B)])].filter(k => !(ignoreVolatile && HDR_VOLATILE.test(k)) && A[k] !== B[k]).sort().map(k => ({ key: k, a: A[k], b: B[k] }))
}

export const diffStats = (d: DiffLine[]) => ({ add: d.filter(x => x.type === 'add').length, del: d.filter(x => x.type === 'del').length })
