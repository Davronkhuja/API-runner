/** Yengil JSONPath: $ . .. [n] [-n] [a:b] [*] ['k'] va oddiy filtr [?(@.k OP literal)]. Natija — mos kelgan qiymatlar massivi. */
type Seg =
  | { t: 'key'; k: string } | { t: 'idx'; i: number } | { t: 'slice'; a: number | null; b: number | null }
  | { t: 'wild' } | { t: 'desc'; inner: Seg } | { t: 'filter'; key: string; op: string; val: any }

const isObj = (x: any) => x !== null && typeof x === 'object'
const children = (x: any): any[] => (Array.isArray(x) ? x : isObj(x) ? Object.values(x) : [])

function parse(path: string): Seg[] {
  const s = path.trim()
  if (!s.startsWith('$')) throw new Error('JSONPath "$" bilan boshlanishi kerak')
  const out: Seg[] = []
  let i = 1
  const name = () => { const m = /^[A-Za-z_$][\w$-]*/.exec(s.slice(i)); if (!m) throw new Error(`Noto'g'ri nom (${i}-belgi)`); i += m[0].length; return m[0] }
  const bracket = (): Seg => {
    const end = s.indexOf(']', i)
    if (end < 0) throw new Error('"]" yo\'q')
    const body = s.slice(i + 1, end).trim()
    i = end + 1
    if (body === '*') return { t: 'wild' }
    let m = /^(['"])(.*)\1$/.exec(body)
    if (m) return { t: 'key', k: m[2] }
    if (/^-?\d+$/.test(body)) return { t: 'idx', i: Number(body) }
    m = /^(-?\d*):(-?\d*)$/.exec(body)
    if (m) return { t: 'slice', a: m[1] === '' ? null : Number(m[1]), b: m[2] === '' ? null : Number(m[2]) }
    m = /^\?\(\s*@\.([\w$-]+)\s*(==|!=|<=|>=|<|>)\s*(.+?)\s*\)$/.exec(body)
    if (m) { let v: any; try { v = JSON.parse(m[3].replace(/^'(.*)'$/, '"$1"')) } catch { throw new Error('Filtr qiymati noto\'g\'ri') } return { t: 'filter', key: m[1], op: m[2], val: v } }
    throw new Error(`Noto'g'ri ifoda: [${body}]`)
  }
  while (i < s.length) {
    if (s.startsWith('..', i)) {
      i += 2
      out.push({ t: 'desc', inner: s[i] === '[' ? bracket() : s[i] === '*' ? (i++, { t: 'wild' }) : { t: 'key', k: name() } })
    } else if (s[i] === '.') {
      i++
      out.push(s[i] === '*' ? (i++, { t: 'wild' }) : { t: 'key', k: name() })
    } else if (s[i] === '[') out.push(bracket())
    else throw new Error(`Kutilmagan belgi "${s[i]}" (${i}-o'rin)`)
  }
  return out
}

const cmp = (a: any, op: string, b: any) => ({ '==': a === b, '!=': a !== b, '<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b } as Record<string, boolean>)[op]

function apply(seg: Seg, nodes: any[]): any[] {
  const out: any[] = []
  for (const n of nodes) {
    switch (seg.t) {
      case 'key': if (isObj(n) && !Array.isArray(n) && seg.k in n) out.push(n[seg.k]); break
      case 'idx': if (Array.isArray(n)) { const v = n[seg.i < 0 ? n.length + seg.i : seg.i]; if (v !== undefined) out.push(v) } break
      case 'slice': if (Array.isArray(n)) { const l = n.length, f = (x: number) => (x < 0 ? Math.max(0, l + x) : Math.min(l, x)); out.push(...n.slice(seg.a == null ? 0 : f(seg.a), seg.b == null ? l : f(seg.b))) } break
      case 'wild': out.push(...children(n)); break
      case 'filter': out.push(...children(n).filter(c => isObj(c) && seg.key in c && cmp(c[seg.key], seg.op, seg.val))); break
      case 'desc': {
        const all: any[] = []
        const walk = (x: any) => { all.push(x); children(x).forEach(walk) }
        walk(n)
        out.push(...apply(seg.inner, all))
      }
    }
  }
  return out
}

export function jsonPath(root: unknown, path: string): any[] {
  return parse(path).reduce<any[]>((nodes, seg) => apply(seg, nodes), [root])
}
