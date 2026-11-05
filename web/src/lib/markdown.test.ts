import { describe, expect, it } from 'vitest'
import { renderMarkdown, safeUrl } from './markdown'

describe('renderMarkdown', () => {
  it('renders common blocks', () => {
    const h = renderMarkdown('# Title\n\nSome **bold**, *it* and `code`.\n\n- a\n- b\n\n1. x\n2. y\n\n> quote\n\n---\n\n```json\n{"a": 1}\n```')
    expect(h).toContain('<h1>Title</h1>')
    expect(h).toContain('<strong>bold</strong>')
    expect(h).toContain('<em>it</em>')
    expect(h).toContain('<code>code</code>')
    expect(h).toContain('<ul><li>a</li><li>b</li></ul>')
    expect(h).toContain('<ol><li>x</li><li>y</li></ol>')
    expect(h).toContain('<blockquote><p>quote</p></blockquote>')
    expect(h).toContain('<hr>')
    expect(h).toContain('<pre><code class="lang-json">{&quot;a&quot;: 1}</code></pre>')
  })
  it('renders tables and links', () => {
    const h = renderMarkdown('| a | b |\n|---|---|\n| 1 | [x](https://e.com/?q=1&r=2) |')
    expect(h).toContain('<th>a</th>')
    expect(h).toContain('<a href="https://e.com/?q=1&amp;r=2" target="_blank" rel="noopener noreferrer">x</a>')
  })
  it('never lets raw HTML or dangerous URLs through', () => {
    const h = renderMarkdown('<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n**<img src=x onerror=alert(1)>**\n\n[y](https://a.com/"onmouseover="x)\n\n```\n<b>raw</b>\n```')
    expect(h).not.toMatch(/<script|<img|<b>|href="javascript|onmouseover="x/i)
    expect(h).toContain('&lt;script&gt;')
    expect(h).toContain('[x](javascript:alert(1))')
  })
  it('code spans are not processed further', () => {
    expect(renderMarkdown('`**x**`')).toBe('<p><code>**x**</code></p>')
  })
  it('safeUrl', () => {
    expect(safeUrl('https://a.b')).toBe('https://a.b')
    expect(safeUrl('mailto:a@b.c')).toBe('mailto:a@b.c')
    expect(safeUrl('javascript:1')).toBeNull()
    expect(safeUrl('//evil.com')).toBeNull()
    expect(safeUrl('data:text/html,x')).toBeNull()
  })
})
