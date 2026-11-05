/** cURL buyrug'i uchun yengil CodeMirror tili (StreamLanguage): `curl`, bayroqlar (-X, --header) va qo'shtirnoqli matnlar. */
import { StreamLanguage } from '@codemirror/language'

export const curlLang = StreamLanguage.define<{ started: boolean }>({
  startState: () => ({ started: false }),
  token(stream, state) {
    if (stream.eatSpace()) return null
    if (!state.started && stream.match(/^curl\b/)) { state.started = true; return 'keyword' }
    if (stream.match(/^--?[A-Za-z][\w-]*/)) return 'attributeName'
    if (stream.match(/^'(?:[^']*)'?/) || stream.match(/^"(?:[^"\\]|\\.)*"?/)) return 'string'
    if (stream.match(/^#.*/)) return 'comment'
    stream.next()
    return null
  },
})
