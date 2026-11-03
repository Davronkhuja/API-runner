/** `Set-Cookie` sarlavhasini ko'rsatish uchun tahlil qilish. */
export interface ParsedCookie { name: string; value: string; domain: string; path: string; expires: string; maxAge: string; httpOnly: boolean; secure: boolean; sameSite: string }

export function parseSetCookie(line: string): ParsedCookie {
  const [pair, ...attrs] = line.split(';').map(s => s.trim())
  const eq = pair.indexOf('=')
  const c: ParsedCookie = { name: eq < 0 ? pair : pair.slice(0, eq), value: eq < 0 ? '' : pair.slice(eq + 1), domain: '', path: '', expires: '', maxAge: '', httpOnly: false, secure: false, sameSite: '' }
  for (const a of attrs) {
    const i = a.indexOf('='), k = (i < 0 ? a : a.slice(0, i)).toLowerCase(), v = i < 0 ? '' : a.slice(i + 1)
    if (k === 'domain') c.domain = v; else if (k === 'path') c.path = v; else if (k === 'expires') c.expires = v
    else if (k === 'max-age') c.maxAge = v; else if (k === 'httponly') c.httpOnly = true; else if (k === 'secure') c.secure = true; else if (k === 'samesite') c.sameSite = v
  }
  return c
}
