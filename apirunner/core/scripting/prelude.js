/* API Runner skript sandbox prelude'i (quickjs-ng). Host bilan FAQAT navbat orqali gaplashadi (quickjs vaqt limiti bilan
 * JS'dan Python callable chaqirib bo'lmaydi): pm.sendRequest / cookie jar so'rovlari `hostCall()` bilan navbatga tushadi, Python event loop
 * ularni bajarib `__hostResolve()` bilan Promise'ni hal qiladi. Kutubxona matnlari (`__LIBS`) va tasodifiy bayt havzasi (`__POOL`) oldindan beriladi.
 * Fayl, tarmoq, modul yuklovchi yo'q. Holat (o'zgaruvchilar, so'rov/javob, testlar, loglar) shu yerda JS ob'ektlarida turadi;
 * Python skript tugagach __collect() bilan JSON sifatida oladi va workspace'ga O'ZI yozadi. */
'use strict';
(function () {
  const G = globalThis;
  G.global = G;
  const S = {
    scopes: { globals: {}, collection: {}, environment: {}, data: {}, local: {} }, changed: {},
    request: null, response: null, info: {}, tests: [], next: undefined, nextSet: false, skip: false,
    logs: [], errors: [], origin: {}, activeEnv: true, envName: null, warned: {}, legacyDone: {}, pendingDone: 0, sendDepth: 0,
  };
  const now = () => Date.now();

  /* ───────── console ───────── */
  const inspect = v => {
    try {
      if (v instanceof Error) return String(v) + (v.stack ? '\n' + v.stack : '');
      if (typeof v === 'function') return '[Function ' + (v.name || 'anonymous') + ']';
      if (typeof v === 'undefined') return 'undefined';
      if (typeof v === 'symbol') return v.toString();
      return JSON.stringify(v, null, 2);
    } catch (e) { return String(v); }
  };
  const fmt = args => args.map(a => (typeof a === 'string' ? a : inspect(a))).join(' ');
  const log = (level, text) => S.logs.push({ level, text, ts: now(), origin: S.origin });
  const mkLog = level => (...a) => { log(level, fmt(a)); };
  G.console = { log: mkLog('log'), info: mkLog('info'), warn: mkLog('warn'), error: mkLog('error'), debug: mkLog('debug'), clear() {} };
  const warnOnce = (key, text) => { if (!S.warned[key]) { S.warned[key] = 1; log('warn', text); } };
  const unsupported = what => warnOnce(what, `⚠ ${what} — bu sandbox'da qo'llab-quvvatlanmaydi (e'tiborsiz qoldirildi)`);

  /* ───────── lazy kutubxonalar ───────── */
  const libSources = { chai: 'chai', _: 'lodash', CryptoJS: 'crypto-js', dayjs: 'dayjs', moment: 'moment' };
  const loaded = {};
  const loadLib = name => {
    if (loaded[name]) return;
    loaded[name] = true;
    for (const g in libSources) if (libSources[g] === name) delete G[g];
    (0, eval)(G.__LIBS[name]);
  };
  Object.keys(libSources).forEach(g => {
    Object.defineProperty(G, g, {
      configurable: true,
      get() { loadLib(libSources[g]); return G[g]; },
      set(v) { Object.defineProperty(G, g, { value: v, writable: true, configurable: true, enumerable: false }); },
    });
  });

  /* ───────── polyfill'lar ───────── */
  const b64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
  G.btoa = s => {
    s = String(s); let out = '';
    for (let i = 0; i < s.length;) {
      const a = s.charCodeAt(i++), b = s.charCodeAt(i++), c = s.charCodeAt(i++);
      if (a > 255 || b > 255 || c > 255) throw new Error('btoa: Latin1 bo\'lmagan belgi');
      const n = (a << 16) | ((b || 0) << 8) | (c || 0);
      out += b64[(n >> 18) & 63] + b64[(n >> 12) & 63] + (isNaN(b) ? '=' : b64[(n >> 6) & 63]) + (isNaN(c) ? '=' : b64[n & 63]);
    }
    return out;
  };
  G.atob = s => {
    s = String(s).replace(/[\s=]+$/g, ''); let out = '', bits = 0, buf = 0;
    for (const ch of s) { const v = b64.indexOf(ch); if (v < 0 || v > 63) throw new Error('atob: noto\'g\'ri base64'); buf = (buf << 6) | v; bits += 6; if (bits >= 8) { bits -= 8; out += String.fromCharCode((buf >> bits) & 255); } }
    return out;
  };
  const utf8Enc = s => unescape(encodeURIComponent(s));
  G.TextEncoder = class { encode(s) { const b = utf8Enc(String(s)); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; } };
  G.TextDecoder = class { decode(u) { let s = ''; for (const x of u || []) s += String.fromCharCode(x); try { return decodeURIComponent(escape(s)); } catch (e) { return s; } } };
  if (!G.structuredClone) G.structuredClone = v => (v === undefined ? v : JSON.parse(JSON.stringify(v)));
  G.crypto = {
    getRandomValues(a) {
      const pool = G.__POOL || []; for (let i = 0; i < a.length; i++) { poolIdx = (poolIdx + 1) % (pool.length || 1); a[i] = ((pool[poolIdx] || 0) ^ Math.floor(Math.random() * 256)) & 255; }
      return a;
    },
    randomUUID() { return uuid.v4(); },
  };
  let poolIdx = 0;
  const uuid = {
    NIL: '00000000-0000-0000-0000-000000000000',
    v4() { const b = new Uint8Array(16); G.crypto.getRandomValues(b); b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80; const h = [...b].map(x => x.toString(16).padStart(2, '0')).join(''); return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`; },
    validate: s => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(s)),
    version: s => parseInt(String(s).charAt(14), 16),
  };
  uuid.v1 = uuid.v4;   // vaqtga asoslangan v1 kerak emas — noyob qiymat yetarli

  /* ───────── timerlar (haqiqiy kutish bilan; Python event loop boshqaradi) ───────── */
  let timerSeq = 0, timers = [];
  const addTimer = (fn, ms, args, interval) => { const id = ++timerSeq; timers.push({ id, at: now() + Math.max(0, +ms || 0), fn, args, interval: interval ? Math.max(1, +ms || 1) : 0 }); return id; };
  G.setTimeout = (fn, ms, ...a) => addTimer(fn, ms, a, false);
  G.setInterval = (fn, ms, ...a) => addTimer(fn, ms, a, true);
  G.clearTimeout = G.clearInterval = id => { timers = timers.filter(t => t.id !== id); };
  G.setImmediate = (fn, ...a) => addTimer(fn, 0, a, false);
  G.__nextTimerDelay = () => (timers.length ? Math.max(0, Math.min(...timers.map(t => t.at)) - now()) : -1);
  G.__runDueTimers = () => {
    const due = timers.filter(t => t.at <= now()).sort((a, b) => a.at - b.at);
    for (const t of due) {
      if (t.interval) t.at = now() + t.interval; else timers = timers.filter(x => x !== t);
      try { t.fn(...t.args); } catch (e) { onError(e); }
    }
  };

  /* ───────── xato yozuvi ───────── */
  const lineOf = st => { const m = /<input>:(\d+)/.exec(String(st || '')); return m ? +m[1] : null; };
  const errRec = e => { const st = e && e.stack ? String(e.stack) : ''; return { name: (e && e.name) || 'Error', message: e && e.message !== undefined ? String(e.message) : String(e), stack: st, line: lineOf(st), origin: S.origin }; };
  const onError = e => { S.errors.push(errRec(e)); };
  G.__onScriptError = onError;

  /* ───────── o'zgaruvchi scope'lari ───────── */
  const DYN = {
    $guid: () => uuid.v4(), $randomUUID: () => uuid.v4(), $timestamp: () => String(Math.floor(now() / 1000)), $isoTimestamp: () => new Date().toISOString(),
    $randomInt: () => String(Math.floor(Math.random() * 1001)),
  };
  const ORDER = ['local', 'data', 'environment', 'collection', 'globals'];
  const lookup = k => { for (const n of ORDER) if (Object.prototype.hasOwnProperty.call(S.scopes[n], k)) return S.scopes[n][k]; return undefined; };
  const replaceIn = (s, depth = 0) => {
    if (typeof s !== 'string') return s;
    const out = s.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (m, k) => { const v = lookup(k); if (v !== undefined) return typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v); if (DYN[k]) return DYN[k](); return m; });
    return out !== s && depth < 4 ? replaceIn(out, depth + 1) : out;
  };
  const mkScope = (name, label) => ({
    get: k => S.scopes[name][k],
    set(k, v) { if (name === 'environment' && !S.activeEnv) warnOnce('noenv', "⚠ Faol muhit yo'q: pm.environment.set faqat shu so'rov davomida amal qiladi (saqlanmaydi)"); S.scopes[name][k] = v; S.changed[name] = true; },
    unset(k) { delete S.scopes[name][k]; S.changed[name] = true; },
    has: k => Object.prototype.hasOwnProperty.call(S.scopes[name], k),
    clear() { for (const k of Object.keys(S.scopes[name])) delete S.scopes[name][k]; S.changed[name] = true; },
    toObject: () => Object.assign({}, S.scopes[name]),
    replaceIn: s => replaceIn(s),
    get name() { return name === 'environment' ? S.envName : label; },
  });
  const pmVariables = {
    get: lookup,
    set(k, v) { S.scopes.local[k] = v; },
    unset(k) { delete S.scopes.local[k]; },
    has: k => lookup(k) !== undefined,
    clear() { for (const k of Object.keys(S.scopes.local)) delete S.scopes.local[k]; },
    toObject() { const o = {}; for (const n of [...ORDER].reverse()) Object.assign(o, S.scopes[n]); return o; },
    replaceIn: s => replaceIn(s),
  };
  const iterationData = {
    get: k => S.scopes.data[k], has: k => Object.prototype.hasOwnProperty.call(S.scopes.data, k), toObject: () => Object.assign({}, S.scopes.data),
    unset(k) { delete S.scopes.data[k]; }, set(k, v) { S.scopes.data[k] = v; unsupported('pm.iterationData.set (faqat joriy iteratsiyada)'); }, replaceIn: s => replaceIn(s),
    toJSON() { return Object.assign({}, S.scopes.data); },
  };

  /* ───────── PropertyList / URL / so'rov ───────── */
  class PropertyList {
    constructor(items, ci) { this._a = items; this._ci = !!ci; }
    _m(k, name) { return this._ci ? String(k).toLowerCase() === String(name).toLowerCase() : k === name; }
    _find(name) { return this._a.find(i => this._m(i.key, name)); }
    get(name) { const i = this._find(name); return i ? i.value : undefined; }
    has(name) { return !!this._find(name); }
    add(item) { if (typeof item === 'string') { const [k, ...v] = item.split(':'); item = { key: k.trim(), value: v.join(':').trim() }; } this._a.push({ key: item.key, value: item.value === undefined ? '' : item.value, ...(item.disabled ? { disabled: true } : {}) }); S.requestDirty = true; }
    upsert(item) { const i = this._find(item.key); if (i) { i.value = item.value; } else this.add(item); S.requestDirty = true; }
    remove(arg) { const name = typeof arg === 'string' ? arg : arg && arg.key; const n = this._a.length; this._a = this._a.filter(i => !this._m(i.key, name)); if (n !== this._a.length) S.requestDirty = true; }
    clear() { this._a.length = 0; S.requestDirty = true; }
    each(fn) { this._a.slice().forEach(fn); }
    all() { return this._a.slice(); }
    count() { return this._a.length; }
    toObject() { const o = {}; this._a.forEach(i => { o[i.key] = i.value; }); return o; }
    map(fn) { return this._a.map(fn); }
    filter(fn) { return this._a.filter(fn); }
    toString() { return this._a.map(i => `${i.key}: ${i.value}`).join('\n'); }
    toJSON() { return this._a.slice(); }
  }
  class Url {
    constructor(raw) { this.update(raw); this._dirty = false; }
    update(raw) {
      raw = raw && typeof raw === 'object' && !(raw instanceof Url) ? (raw.raw || '') : String(raw === undefined ? '' : raw);
      if (raw instanceof Url) raw = raw.toString();
      this._raw = raw; this._dirty = true;
      const m = /^(?:([a-zA-Z][\w+.-]*):\/\/)?([^/?#]*)([^?#]*)(?:\?([^#]*))?(?:#(.*))?$/.exec(raw) || [];
      this.protocol = m[1] || undefined;
      const hp = m[2] || '', pi = /:(\d+)$/.exec(hp);
      this.port = pi ? pi[1] : undefined; this.host = (pi ? hp.slice(0, -pi[0].length) : hp).split('.').filter(Boolean);
      this.path = (m[3] || '').replace(/^\//, '').split('/').filter((x, i, a) => x !== '' || i < a.length - 1);
      if (this.path.length === 1 && this.path[0] === '') this.path = [];
      const q = (m[4] || '').split('&').filter(Boolean).map(p => { const e = p.indexOf('='); return e < 0 ? { key: p, value: null } : { key: p.slice(0, e), value: p.slice(e + 1) }; });
      this.query = new PropertyList(q); this.hash = m[5] || undefined;
    }
    getHost() { return this.host.join('.'); }
    getPath() { return '/' + this.path.join('/'); }
    getQueryString() { return this.query.all().map(q => (q.value === null ? q.key : `${q.key}=${q.value}`)).join('&'); }
    getPathWithQuery() { const q = this.getQueryString(); return this.getPath() + (q ? '?' + q : ''); }
    addQueryParams(p) { (typeof p === 'string' ? p.split('&').filter(Boolean).map(x => { const [k, ...v] = x.split('='); return { key: k, value: v.join('=') }; }) : [].concat(p)).forEach(i => this.query.add(i)); }
    removeQueryParams(names) { [].concat(names).forEach(n => this.query.remove(typeof n === 'string' ? n : n.key)); }
    toString() {
      const parts = this.protocol !== undefined ? this.protocol + '://' : '';
      const q = this.getQueryString();
      const rebuilt = parts + this.getHost() + (this.port ? ':' + this.port : '') + (this.path.length ? '/' + this.path.join('/') : '') + (q ? '?' + q : '') + (this.hash ? '#' + this.hash : '');
      return S.requestDirty || this._dirty ? rebuilt : this._raw;
    }
    toJSON() { return this.toString(); }
  }
  const STATUS = { 100: 'Continue', 200: 'OK', 201: 'Created', 202: 'Accepted', 204: 'No Content', 301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 405: 'Method Not Allowed', 409: 'Conflict', 422: 'Unprocessable Entity', 429: 'Too Many Requests', 500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable', 504: 'Gateway Timeout' };
  const titleCase = k => String(k).replace(/(^|-)([a-z])/g, (m, a, b) => a + b.toUpperCase());

  const buildRequest = spec => {
    const url = new Url(spec.url || '');
    const headers = new PropertyList((spec.headers || []).map(h => ({ key: h.key, value: h.value })), true);
    const body = { mode: spec.body_mode || 'raw', raw: spec.body || '', toString() { return this.raw; }, update(v) { this.raw = typeof v === 'string' ? v : JSON.stringify(v && v.raw !== undefined ? v.raw : v); S.requestDirty = true; } };
    let method = spec.method || 'GET';
    const req = {
      get method() { return method; }, set method(v) { method = String(v).toUpperCase(); S.requestDirty = true; },
      get url() { return url; }, set url(v) { url.update(v); S.requestDirty = true; },
      headers, body, auth: spec.auth || null,
      toJSON() { return { method, url: url.toString(), header: headers.all(), body: { mode: body.mode, raw: body.raw } }; },
      _view: { url, headers, body, getMethod: () => method },
    };
    return req;
  };

  /* ───────── javob ───────── */
  const jsonParse = t => JSON.parse(String(t).replace(/^﻿/, ''));
  const mkResponse = r => {
    const text = typeof r.body === 'string' ? r.body : (r.body === undefined || r.body === null ? '' : JSON.stringify(r.body));
    const headers = new PropertyList(Object.entries(r.headers || {}).map(([k, v]) => ({ key: titleCase(k), value: String(v) })), true);
    const res = {
      code: r.code, status: r.status || STATUS[r.code] || '', headers, responseTime: r.time, responseSize: r.size,
      text: () => text, json() { try { return jsonParse(text); } catch (e) { throw new Error('JSON tahlil xatosi: javob JSON emas (' + e.message + ')'); } },
      reason: () => r.status || STATUS[r.code] || '', size: () => ({ body: r.size, header: 0, total: r.size }),
      cookies: new PropertyList((r.cookies || []).map(c => Object.assign({ key: c.name }, c)), false),
      stream: { toString: () => text, length: text.length, toJSON: () => text }, _raw: { text, headers: r.headers || {} },
    };
    res.to = mkAssert(res, false);
    return res;
  };
  const mkAssert = (res, neg) => {
    const A = {};
    const fail = m => { throw new (G.chai || chai).AssertionError(m); };
    const ok = (cond, yes, no) => { if (neg ? cond : !cond) fail(neg ? no : yes); };
    ['be', 'have', 'and', 'is', 'that', 'which', 'with', 'an', 'a', 'to'].forEach(k => Object.defineProperty(A, k, { get: () => A }));
    Object.defineProperty(A, 'not', { get: () => mkAssert(res, !neg) });
    const cls = (name, fnc, desc) => Object.defineProperty(A, name, { get() { ok(fnc(res.code), `expected response to be ${desc} but got ${res.code}`, `expected response not to be ${desc} but got ${res.code}`); return A; } });
    cls('ok', c => c === 200, 'ok (200)'); cls('success', c => c >= 200 && c < 300, 'success (2xx)'); cls('error', c => c >= 400 && c < 600, 'an error (4xx/5xx)');
    cls('clientError', c => c >= 400 && c < 500, 'a client error (4xx)'); cls('serverError', c => c >= 500 && c < 600, 'a server error (5xx)'); cls('redirection', c => c >= 300 && c < 400, 'a redirection (3xx)'); cls('info', c => c >= 100 && c < 200, 'informational (1xx)');
    cls('accepted', c => c === 202, 'accepted (202)'); cls('badRequest', c => c === 400, 'bad request (400)'); cls('unauthorized', c => c === 401, 'unauthorized (401)'); cls('forbidden', c => c === 403, 'forbidden (403)'); cls('notFound', c => c === 404, 'not found (404)'); cls('rateLimited', c => c === 429, 'rate limited (429)');
    Object.defineProperty(A, 'withBody', { get() { ok(res.text().length > 0, 'expected response to have a body', 'expected response not to have a body'); return A; } });
    Object.defineProperty(A, 'json', { get() { let good = true; try { res.json(); } catch (e) { good = false; } ok(good, 'expected response body to be JSON', 'expected response body not to be JSON'); return A; } });
    A.status = v => { const m = typeof v === 'number' ? res.code === v : String(res.status).toLowerCase() === String(v).toLowerCase(); ok(m, `expected response to have status ${typeof v === 'number' ? 'code' : 'reason'} '${v}' but got '${typeof v === 'number' ? res.code : res.status}'`, `expected response to not have status ${typeof v === 'number' ? 'code' : 'reason'} '${v}'`); return A; };
    A.header = (name, val) => { const h = res.headers.get(name); ok(val === undefined ? h !== undefined : h === String(val), `expected response to have header '${name}'${val !== undefined ? ` with value '${val}' but got '${h}'` : ''}`, `expected response not to have header '${name}'${val !== undefined ? ` with value '${val}'` : ''}`); return A; };
    A.body = v => { const t = res.text(); const m = v instanceof RegExp ? v.test(t) : v === undefined ? t.length > 0 : t === String(v); ok(m, `expected response body to ${v instanceof RegExp ? 'match ' + v : "equal '" + v + "'"}`, `expected response body not to ${v instanceof RegExp ? 'match ' + v : "equal '" + v + "'"}`); return A; };
    A.jsonBody = (path, val) => {
      let j; try { j = res.json(); } catch (e) { fail('expected response body to be JSON'); }
      if (path === undefined) return A;
      const parts = String(path).replace(/\[(\w+)\]/g, '.$1').split('.').filter(Boolean); let cur = j;
      for (const p of parts) { cur = cur == null ? undefined : cur[p]; }
      const exists = cur !== undefined;
      ok(val === undefined ? exists : JSON.stringify(cur) === JSON.stringify(val), `expected json body to have '${path}'${val !== undefined ? ' = ' + JSON.stringify(val) + ' but got ' + JSON.stringify(cur) : ''}`, `expected json body not to have '${path}'${val !== undefined ? ' = ' + JSON.stringify(val) : ''}`);
      return A;
    };
    A.jsonSchema = () => { unsupported("pm.response.to.have.jsonSchema (tv4/ajv yo'q)"); return A; };
    return A;
  };

  /* ───────── pm.test ───────── */
  const failRec = (rec, e) => { rec.passed = false; rec.error = { name: (e && e.name) || 'Error', message: e && e.message !== undefined ? String(e.message) : String(e), stack: e && e.stack ? String(e.stack) : '', line: lineOf(e && e.stack) }; };
  const pmTest = (name, fn) => {
    const rec = { name: String(name), passed: true, error: null, skipped: false, origin: S.origin };
    S.tests.push(rec);
    if (typeof fn !== 'function') return;
    try {
      if (fn.length > 0) {                      // done callback uslubi
        rec._waiting = true; S.pendingDone++;
        fn(err => { if (rec._waiting) { rec._waiting = false; S.pendingDone--; if (err) failRec(rec, err instanceof Error ? err : new Error(String(err))); } });
      } else {
        const r = fn();
        if (r && typeof r.then === 'function') { rec._waiting = true; S.pendingDone++; r.then(() => { rec._waiting = false; S.pendingDone--; }, e => { rec._waiting = false; S.pendingDone--; failRec(rec, e); }); }
      }
    } catch (e) { failRec(rec, e); if (rec._waiting) { rec._waiting = false; S.pendingDone--; } }
  };
  pmTest.skip = (name) => { S.tests.push({ name: String(name), passed: true, error: null, skipped: true, origin: S.origin }); };
  pmTest.index = () => S.tests.length;

  /* ───────── host navbati ───────── */
  let hostSeq = 0; const hostq = []; const hostWait = {};
  const hostCall = (kind, payload) => new Promise((res) => { const id = ++hostSeq; hostWait[id] = res; hostq.push({ id, kind, payload }); });
  G.__takeHost = () => { const q = hostq.splice(0); return q.length ? JSON.stringify(q) : ''; };
  G.__hostResolve = (id, json) => { const w = hostWait[id]; delete hostWait[id]; if (w) w(JSON.parse(json)); };

  /* ───────── pm.sendRequest ───────── */
  const normReq = r => {
    if (typeof r === 'string') r = { url: r };
    const out = { url: typeof r.url === 'object' && r.url ? (r.url.raw || String(r.url)) : r.url, method: (r.method || 'GET').toUpperCase(), header: [], body: null, auth: r.auth || null, timeout: r.timeout };
    const h = r.header || r.headers;
    if (Array.isArray(h)) out.header = h.map(x => ({ key: x.key, value: x.value })); else if (h && typeof h === 'object') out.header = Object.entries(h.toObject ? h.toObject() : h).map(([key, value]) => ({ key, value: String(value) }));
    if (r.body) out.body = r.body.mode ? { mode: r.body.mode, raw: r.body.raw, urlencoded: r.body.urlencoded, formdata: r.body.formdata, graphql: r.body.graphql } : { mode: 'raw', raw: String(r.body) };
    return out;
  };
  const sendRequest = (req, cb) => {
    const depth = S.sendDepth + 1;
    const p = hostCall('send', { req: normReq(req), depth }).then(out => { if (out.error) throw new Error(out.error.message); return mkResponse(out.response); });
    if (typeof cb === 'function') {
      const run = (e, r) => { const prev = S.sendDepth; S.sendDepth = depth; try { cb(e, r); } catch (x) { onError(x); } finally { S.sendDepth = prev; } };
      p.then(res => run(null, res), err => run(err, undefined));
      return undefined;
    }
    return p;
  };

  /* ───────── cookies ───────── */
  const cookieCall = (op, args) => hostCall('cookie', { op, ...args }).then(o => { if (o && o.error) throw new Error(o.error); return o ? o.value : undefined; });
  const cbOrPromise = (p, cb) => { if (typeof cb === 'function') { p.then(v => cb(null, v), e => cb(e)); return undefined; } return p; };
  const cookies = {
    get: n => { const c = (S.cookies || []).find(x => x.name === n); return c ? c.value : undefined; },
    has: n => (S.cookies || []).some(x => x.name === n), toObject() { const o = {}; (S.cookies || []).forEach(c => { o[c.name] = c.value; }); return o; },
    jar: () => ({
      get: (url, name, cb) => cbOrPromise(cookieCall('get', { url: String(url), name }), cb),
      getAll: (url, cb) => cbOrPromise(cookieCall('getAll', { url: String(url) }), cb),
      set: (url, name, value, cb) => { if (typeof value === 'function') { cb = value; value = undefined; } const o = typeof name === 'object' ? name : { name, value }; return cbOrPromise(cookieCall('set', { url: String(url), cookie: o }), cb); },
      unset: (url, name, cb) => cbOrPromise(cookieCall('unset', { url: String(url), name: typeof name === 'object' ? name.name : name }), cb),
      clear: (url, cb) => cbOrPromise(cookieCall('clear', { url: String(url) }), cb),
    }),
  };

  /* ───────── xml2js (kichik) ───────── */
  const parseXml = (xml, explicitArray) => {
    const re = /<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<!\[CDATA\[([\s\S]*?)\]\]>|<\/([\w:.-]+)\s*>|<([\w:.-]+)((?:\s+[\w:.-]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>|([^<]+)/g;
    const dec = s => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
    const root = {}; const stack = [{ name: null, node: root }]; let m;
    const add = (parent, name, child) => { if (parent === root) parent[name] = child; else if (explicitArray) (parent[name] = parent[name] || []).push(child); else if (name in parent) { if (!Array.isArray(parent[name])) parent[name] = [parent[name]]; parent[name].push(child); } else parent[name] = child; };
    while ((m = re.exec(xml))) {
      const top = stack[stack.length - 1];
      if (m[1] !== undefined) top.node._ = (top.node._ || '') + m[1];
      else if (m[2]) { const e = stack.pop(); if (e.text !== undefined && Object.keys(e.node).length === 0) { /* oddiy matn tugun */ } }
      else if (m[3]) {
        const node = {}; const attrs = {}; let has = false;
        (m[4] || '').replace(/([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g, (x, k, a, b2) => { attrs[k] = dec(a !== undefined ? a : b2); has = true; return x; });
        if (has) node.$ = attrs;
        add(top.node, m[3], node);
        if (!m[5]) stack.push({ name: m[3], node });
      } else if (m[6] !== undefined && m[6].trim()) top.node._ = (top.node._ || '') + dec(m[6].trim());
    }
    const simplify = n => { for (const k of Object.keys(n)) { if (k === '$' || k === '_') continue; const v = n[k]; (Array.isArray(v) ? v : [v]).forEach(simplify); } return n; };
    const flat = n => { if (n && typeof n === 'object') { for (const k of Object.keys(n)) { const v = n[k]; if (Array.isArray(v)) v.forEach(flat); else if (v && typeof v === 'object') { flat(v); if (Object.keys(v).length === 1 && '_' in v) n[k] = v._; } } } return n; };
    const collapse = n => { for (const k of Object.keys(n)) { if (k === '$' || k === '_') continue; const v = n[k]; if (Array.isArray(v)) n[k] = v.map(x => { collapse(x); return Object.keys(x).length === 0 ? '' : (Object.keys(x).length === 1 && '_' in x ? x._ : x); }); else if (v && typeof v === 'object') collapse(v); } return n; };
    simplify(root); return explicitArray ? collapse(root) : flat(root);
  };
  const xml2js = {
    parseString(xml, opts, cb) { if (typeof opts === 'function') { cb = opts; opts = {}; } let r, e = null; try { r = parseXml(String(xml), !opts || opts.explicitArray !== false); } catch (x) { e = x; } if (cb) cb(e, r); },
    parseStringPromise(xml, opts) { return new Promise((res, rej) => { try { res(parseXml(String(xml), !opts || opts.explicitArray !== false)); } catch (e) { rej(e); } }); },
  };
  xml2js.Parser = class { constructor(o) { this.o = o || {}; } parseString(x, cb) { xml2js.parseString(x, this.o, cb); } parseStringPromise(x) { return xml2js.parseStringPromise(x, this.o); } };
  G.xml2Json = x => parseXml(String(x), false);

  /* ───────── require ───────── */
  const MODS = { lodash: () => G._, 'crypto-js': () => G.CryptoJS, moment: () => G.moment, chai: () => G.chai, dayjs: () => G.dayjs, uuid: () => uuid, xml2js: () => xml2js, atob: () => G.atob, btoa: () => G.btoa };
  const UNSUPPORTED = ['cheerio', 'ajv', 'tv4', 'postman-collection', 'csv-parse/lib/sync', 'csv-parse', 'buffer', 'util', 'url', 'path', 'fs', 'crypto', 'events', 'os', 'child_process', 'http', 'https', 'stream', 'zlib', 'querystring', 'assert', 'node-forge', 'jsrsasign', 'sync-request'];
  G.require = name => {
    name = String(name);
    if (MODS[name]) return MODS[name]();
    if (name !== 'crypto' && name !== 'util') unsupported(`require('${name}')${UNSUPPORTED.includes(name) ? '' : ' (noma\'lum modul)'}`);   // crypto/util — kutubxonalar o'zi tekshirib ko'radi
    throw new Error(`Cannot find module '${name}': bu sandbox'da qo'llab-quvvatlanmaydi (bor: ${Object.keys(MODS).join(', ')})`);
  };

  /* ───────── pm ───────── */
  const noop = function () { return noopProxy; };
  const noopProxy = new Proxy(noop, { get: (t, p) => (p === Symbol.toPrimitive ? () => '' : p === 'then' ? undefined : noopProxy), apply: () => noopProxy });
  const pmTarget = {
    info: { get eventName() { return S.info.eventName; }, get iteration() { return S.info.iteration; }, get iterationCount() { return S.info.iterationCount; }, get requestName() { return S.info.requestName; }, get requestId() { return S.info.requestId; } },
    get request() { return S.request; }, get response() { return S.response; },
    environment: mkScope('environment'), globals: mkScope('globals', 'globals'), collectionVariables: mkScope('collection', 'collection'), variables: pmVariables, iterationData,
    test: pmTest, expect: (...a) => G.chai.expect(...a), sendRequest, cookies,
    execution: {
      setNextRequest(n) { if (n !== null && typeof n !== 'string') { log('warn', '⚠ setNextRequest: nom (matn) yoki null kutiladi'); return; } S.next = n; S.nextSet = true; },
      skipRequest() { if (S.origin.kind !== 'prerequest') { warnOnce('skipreq', '⚠ pm.execution.skipRequest faqat pre-request skriptida ishlaydi'); return; } S.skip = true; },
      get location() { return []; },
    },
    setNextRequest(n) { pmTarget.execution.setNextRequest(n); },
    visualizer: { set() { unsupported('pm.visualizer'); }, clear() {} },
  };
  const warnedPm = {};
  G.pm = new Proxy(pmTarget, {
    get(t, p) {
      if (p in t) return t[p];
      if (typeof p === 'symbol' || p === 'toJSON' || p === 'then') return undefined;
      if (!warnedPm[p]) { warnedPm[p] = 1; unsupported('pm.' + String(p)); }
      return noopProxy;
    },
  });

  /* ───────── legacy global'lar (eski Postman) ───────── */
  const envObj = () => Object.assign({}, S.scopes.environment), globObj = () => Object.assign({}, S.scopes.globals);
  const setVar = (scope, k, v) => { if (scope === 'environment' && !S.activeEnv) warnOnce('noenv', "⚠ Faol muhit yo'q: postman.setEnvironmentVariable faqat shu so'rov davomida amal qiladi"); S.scopes[scope][k] = typeof v === 'string' ? v : (v === undefined ? 'undefined' : (typeof v === 'object' ? JSON.stringify(v) : String(v))); S.changed[scope] = true; };
  G.postman = {
    setEnvironmentVariable: (k, v) => setVar('environment', k, v), getEnvironmentVariable: k => S.scopes.environment[k],
    clearEnvironmentVariable: k => { delete S.scopes.environment[k]; S.changed.environment = true; }, clearEnvironmentVariables: () => { for (const k of Object.keys(S.scopes.environment)) delete S.scopes.environment[k]; S.changed.environment = true; },
    setGlobalVariable: (k, v) => setVar('globals', k, v), getGlobalVariable: k => S.scopes.globals[k],
    clearGlobalVariable: k => { delete S.scopes.globals[k]; S.changed.globals = true; }, clearGlobalVariables: () => { for (const k of Object.keys(S.scopes.globals)) delete S.scopes.globals[k]; S.changed.globals = true; },
    setNextRequest: n => pmTarget.execution.setNextRequest(n === undefined ? null : n),
    getResponseHeader: n => (S.response ? S.response.headers.get(n) : undefined), getResponseCookie: n => (S.response ? S.response.cookies.get(n) : undefined),
    getBodyAsJson: () => (S.response ? S.response.json() : undefined),
  };
  const installLegacy = () => {
    G.tests = G.tests || {};
    G.globals = globObj(); G.environment = envObj(); G.data = Object.assign({}, S.scopes.data); G.iteration = S.info.iteration;
    if (S.request) {
      const h = {}; S.request.headers.all().forEach(x => { h[x.key] = x.value; });
      const rawBody = S.request.body.raw; let bodyData = rawBody;
      if (S.request.body.mode === 'urlencoded') { bodyData = {}; const dec = x => { try { return decodeURIComponent(x.replace(/\+/g, ' ')); } catch (_) { return x; } }; String(rawBody).split('&').filter(Boolean).forEach(p => { const e = p.indexOf('='); bodyData[dec(e < 0 ? p : p.slice(0, e))] = e < 0 ? '' : dec(p.slice(e + 1)); }); }
      G.request = { url: S.request.url.toString(), method: S.request.method, headers: h, data: bodyData };
    }
    if (S.response) {
      const r = S.response;
      G.responseBody = r.text(); G.responseCode = { code: r.code, name: r.status, detail: r.status }; G.responseTime = r.responseTime;
      const h = {}; r.headers.all().forEach(x => { h[x.key] = x.value; });
      G.responseHeaders = new Proxy(h, { get: (t, p) => { if (p in t) return t[p]; const k = Object.keys(t).find(x => x.toLowerCase() === String(p).toLowerCase()); return k ? t[k] : undefined; }, has: (t, p) => Object.keys(t).some(x => x.toLowerCase() === String(p).toLowerCase()) });
    }
  };
  ['tv4', 'cheerio', '$', 'jQuery'].forEach(n => Object.defineProperty(G, n, { configurable: true, get() { unsupported(n); return noopProxy; } }));

  /* ───────── host API (Python chaqiradi) ───────── */
  G.__init = json => {
    const d = JSON.parse(json);
    Object.assign(S.scopes, d.scopes); S.info = d.info || {}; S.activeEnv = d.activeEnv !== false; S.envName = d.envName || null; S.cookies = d.cookies || [];
    S.request = d.request ? buildRequest(d.request) : null; S.requestDirty = false; S.origRequest = d.request ? JSON.stringify(S.request.toJSON()) : null;
  };
  G.__setSent = json => { S.request = buildRequest(JSON.parse(json)); S.requestDirty = false; };
  G.__setEvent = n => { S.info.eventName = n; };
  G.__setResponse = json => { const r = JSON.parse(json); S.response = mkResponse(r); const own = r.cookies || []; S.cookies = [...own, ...(r.jar || []).filter(j => !own.some(c => c.name === j.name))]; };
  G.__begin = json => { S.origin = JSON.parse(json); installLegacy(); };
  G.__end = () => {
    const t = G.tests || {};
    for (const k of Object.keys(t)) { if (S.legacyDone[k] === undefined) { S.legacyDone[k] = true; S.tests.push({ name: k, passed: !!t[k], error: t[k] ? null : { name: 'AssertionError', message: 'tests["' + k + '"] = false', stack: '', line: null }, skipped: false, origin: S.origin, legacy: true }); } }
  };
  G.__finish = () => {
    for (const t of S.tests) if (t._waiting) { t._waiting = false; failRec(t, new Error("done() chaqirilmadi yoki Promise tugamadi")); }
  };
  G.__collect = () => {
    const req = S.request ? S.request.toJSON() : null;
    return JSON.stringify({
      scopes: S.scopes, changed: S.changed, tests: S.tests.map(t => ({ name: t.name, passed: t.passed, error: t.error, skipped: t.skipped, origin: t.origin, legacy: !!t.legacy })),
      logs: S.logs, errors: S.errors, next: S.nextSet ? (S.next === undefined ? null : S.next) : undefined, nextSet: S.nextSet, skip: S.skip,
      request: S.requestDirty ? req : null, orig: S.origRequest, pendingTests: S.pendingDone,
    });
  };
})();
