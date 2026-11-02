/** Data fayl (CSV/JSON) o'qish — Batch va Runner uchun yagona. */
export type DataRow = Record<string, any>

function splitCsvLine(l: string): string[] {
  const out: string[] = []
  let cur = '', q = false
  for (let i = 0; i < l.length; i++) {
    const c = l[i]
    if (q) { if (c === '"') { if (l[i + 1] === '"') { cur += '"'; i++ } else q = false } else cur += c }
    else if (c === '"') q = true
    else if (c === ',') { out.push(cur); cur = '' }
    else cur += c
  }
  out.push(cur)
  return out
}

export function parseCSV(text: string): Record<string, string>[] {
  const lines = text.split(/\r?\n/).filter(l => l.trim())
  if (!lines.length) return []
  const head = splitCsvLine(lines[0]).map(h => h.trim())
  return lines.slice(1).map(l => Object.fromEntries(splitCsvLine(l).map((v, i) => [head[i] ?? `col${i}`, v])))
}

export function parseDataFile(name: string, text: string): DataRow[] {
  const rows = /\.json$/i.test(name) ? JSON.parse(text) : parseCSV(text)
  if (!Array.isArray(rows)) throw new Error('JSON massiv bo\'lishi kerak')
  return rows
}

export const isDataFile = (f: { name: string; type?: string }) => /\.(csv|json)$/i.test(f.name) || f.type === 'text/csv'
