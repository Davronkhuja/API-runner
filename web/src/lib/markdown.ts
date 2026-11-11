/** Kichik va XAVFSIZ Markdown → HTML: avval hamma narsa escape qilinadi, keyin faqat ma'lum naqshlar teg'ga aylanadi (xom HTML o'tmaydi). */
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')

/** Faqat http(s) va mailto havolalari; `javascript:` va boshqalar matn bo'lib qoladi. */
export function safeUrl(u: string): string | null {
  const t = u.trim()
  return /^(https?:\/\/|mailto:)/i.test(t) && !/[\s<>"]/.test(t) ? t : null
}

function inline(src: string): string {
  const codes: string[] = []
  let s = esc(src).replace(/`([^`\n]+)`/g, (_m, c) => { codes.push(`<code>${c}</code>`); return `\u0000${codes.length - 1}\u0000` })
  s = s.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (m, text, url) => {
    const real = url.replace(/&amp;/g, '&')
    const ok = safeUrl(real)
    return ok ? `<a href="${esc(ok)}" target="_blank" rel="noopener noreferrer">${text}</a>` : m
  })
  s = s.replace(/\*\*([^*\n]+)\*\*|__([^_\n]+)__/g, (_m, a, b) => `<strong>${a ?? b}</strong>`)
  s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>').replace(/(^|[^_\w])_([^_\n]+)_(?!\w)/g, '$1<em>$2</em>')
  s = s.replace(/~~([^~\n]+)~~/g, '<del>$1</del>')
  return s.replace(/\u0000(\d+)\u0000/g, (_m, i) => codes[Number(i)])
}

export function renderMarkdown(md: string): string {
  const lines = md.replace(/\u0000/g, '').replace(/\r\n?/g, '\n').split('\n')      // NUL — ichki o'rinbosar belgi
  const out: string[] = []
  let i = 0
  const isBlank = (l: string) => !l.trim()
  const special = (l: string) => /^(#{1,6}\s|```|>\s?|\s*([-*+]|\d+\.)\s+|\s*(-{3,}|\*{3,}|_{3,})\s*$|\s*\|)/.test(l)
  while (i < lines.length) {
    const l = lines[i]
    if (isBlank(l)) { i++; continue }
    const fence = /^```(\w*)\s*$/.exec(l)
    if (fence) {
      const buf: string[] = []
      i++
      while (i < lines.length && !/^```\s*$/.test(lines[i])) buf.push(lines[i++])
      i++
      out.push(`<pre><code${fence[1] ? ` class="lang-${esc(fence[1])}"` : ''}>${esc(buf.join('\n'))}</code></pre>`)
      continue
    }
    const h = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(l)
    if (h) { out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue }
    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(l)) { out.push('<hr>'); i++; continue }
    if (/^>\s?/.test(l)) {
      const buf: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''))
      out.push(`<blockquote>${renderMarkdown(buf.join('\n'))}</blockquote>`)
      continue
    }
    const ul = /^\s*([-*+])\s+/.test(l), ol = /^\s*\d+\.\s+/.test(l)
    if (ul || ol) {
      const re = ul ? /^\s*[-*+]\s+(.*)$/ : /^\s*\d+\.\s+(.*)$/
      const items: string[] = []
      while (i < lines.length && re.test(lines[i])) items.push(`<li>${inline(re.exec(lines[i++])![1])}</li>`)
      out.push(`<${ul ? 'ul' : 'ol'}>${items.join('')}</${ul ? 'ul' : 'ol'}>`)
      continue
    }
    if (/^\s*\|/.test(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(lines[i + 1])) {
      const cells = (r: string) => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
      const head = cells(l)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]))
      out.push(`<table><thead><tr>${head.map(c => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`)
      continue
    }
    const buf: string[] = []
    while (i < lines.length && !isBlank(lines[i]) && (buf.length === 0 || !special(lines[i]))) buf.push(lines[i++])
    out.push(`<p>${buf.map(inline).join('<br>')}</p>`)
  }
  return out.join('')
}
