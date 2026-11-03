# ADR 0007 spike skriptlari

O'lchovlar `docs/adr/0007-script-sandbox.md` da. Qayta yurgizish:

```bash
mkdir spike && cd spike && npm init -y && npm i chai@4 lodash crypto-js dayjs
mkdir libs && cp node_modules/chai/chai.js node_modules/lodash/lodash.min.js node_modules/crypto-js/crypto-js.js node_modules/dayjs/dayjs.min.js libs/
cp ../docs/adr/0007-spike/* .
python3 -m venv ng && ng/bin/pip install quickjs-ng && ng/bin/python bench_quickjs.py   # (yoki `pip install quickjs` — sdist, kompilyator kerak)
node bench_node.js && node bench_node2.js && node --permission bench_node2.js
```
