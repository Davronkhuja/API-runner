import { describe, expect, it } from 'vitest'
import { esc, highlightCurl, highlightJson } from './highlight'

describe('highlight', () => {
  it('escape qiladi', () => expect(esc('<a&b>')).toBe('&lt;a&amp;b&gt;'))
  it('JSON kalit/satr/son/literal', () => {
    const h = highlightJson('{"a": "x", "n": 1.5, "t": true, "z": null}')
    expect(h).toContain('<span class="hl-key">&quot;a&quot;'.replace(/&quot;/g, '"'))
    expect(h).toContain('hl-str'); expect(h).toContain('hl-num'); expect(h).toContain('hl-lit')
  })
  it('HTML in\'ektsiyasi mumkin emas', () => expect(highlightJson('"<script>"')).not.toContain('<script>'))
  it('cURL', () => {
    const h = highlightCurl("curl -X POST 'https://a.io'")
    expect(h).toContain('<span class="hl-cmd">curl</span>'); expect(h).toContain('hl-flag'); expect(h).toContain('hl-str')
  })
})
