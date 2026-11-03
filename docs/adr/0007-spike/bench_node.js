const vm = require('vm'), fs = require('fs'), { performance } = require('perf_hooks')
const LIBS = ['chai.js', 'lodash.min.js', 'crypto-js.js', 'dayjs.min.js']
const src = Object.fromEntries(LIBS.map(l => [l, fs.readFileSync('libs/' + l, 'utf8')]))
const ms = (f, n = 1) => { const t = performance.now(); let r; for (let i = 0; i < n; i++) r = f(); return [(performance.now() - t) / n, r] }
const out = { node: process.version }
const newCtx = () => vm.createContext({})            // sandbox: bo'sh ob'ekt (hech narsa berilmagan)
out.ctx_create_ms = +ms(newCtx, 500)[0].toFixed(3)
out.trivial_script_fresh_ctx_ms = +ms(() => vm.runInContext('var a=1;a+1', newCtx()), 500)[0].toFixed(3)
for (const l of LIBS) out['load_' + l + '_ms'] = +ms(() => { const c = newCtx(); vm.runInContext(src[l], c); return c }, 20)[0].toFixed(2)
const allLibs = () => { const c = newCtx(); for (const l of LIBS) vm.runInContext(src[l], c); return c }
out.load_all_ms = +ms(allLibs, 10)[0].toFixed(2)
const c = allLibs(), run = code => { try { return vm.runInContext(code, c, { timeout: 1000 }) } catch (e) { return 'ERR ' + String(e.message).slice(0, 80) } }
out.libs_work = {
  chai: run("chai.expect(5).to.be.above(3) && 'ok'"), lodash: run("_.chunk([1,2,3,4],2).length + _.get({a:{b:3}},'a.b')"),
  cryptojs_md5: run("CryptoJS.MD5('abc').toString()"), cryptojs_hmac: run("CryptoJS.HmacSHA256('msg','key').toString()"),
  cryptojs_aes: run("CryptoJS.AES.decrypt(CryptoJS.AES.encrypt('hello','pw').toString(),'pw').toString(CryptoJS.enc.Utf8)"),
  dayjs: run("dayjs('2026-11-03').add(1,'day').format('YYYY-MM-DD')"),
}
const c2 = newCtx(); vm.runInContext('function fib(n){return n<2?n:fib(n-1)+fib(n-2)}', c2)
out.fib27_ms = +ms(() => vm.runInContext('fib(27)', c2))[0].toFixed(1)
out.loop_1e7_ms = +ms(() => vm.runInContext('var s=0;for(var i=0;i<1e7;i++)s+=i;s', c2))[0].toFixed(1)
out.reused_ctx_script_ms = +ms(() => vm.runInContext("chai.expect(_.sum([1,2,3])).to.equal(6)", c), 2000)[0].toFixed(4)
const t0 = performance.now(); let lim = {}
try { vm.runInContext('while(true){}', newCtx(), { timeout: 300 }); lim.infinite_loop = 'NOT STOPPED' } catch (e) { lim.infinite_loop = `stopped after ${((performance.now() - t0) / 1000).toFixed(2)}s: ${e.code}` }
try { vm.runInContext('function f(){ try { while(true){} } catch(e){} } f()', newCtx(), { timeout: 300 }); lim.catch_swallow = 'NOT STOPPED' } catch (e) { lim.catch_swallow = 'stopped: ' + e.code }
try { vm.runInContext('function r(){return r()+1}r()', newCtx()); lim.deep_recursion = 'NOT STOPPED' } catch (e) { lim.deep_recursion = 'stopped: ' + e.message }
lim.memory_bomb = 'vm: per-context xotira limiti YO\'Q (butun jarayon heap\'i; --max-old-space-size jarayonni o\'ldiradi) — pastda alohida o\'lchanadi'
out.limits = lim
// izolyatsiya: bo'sh sandbox
const iso = newCtx(), g = {}
for (const n of ['require', 'process', 'fetch', 'XMLHttpRequest', 'Buffer', 'setTimeout', 'WebSocket', 'module']) g[n] = vm.runInContext('typeof ' + n, iso)
out.typeof_globals = g
// vm qochish (hech qanday host ob'ekt berilmagan holda ham)
let esc
try { esc = vm.runInContext("this.constructor.constructor('return typeof process')()", newCtx()) } catch (e) { esc = 'blocked ' + e.message }
out.escape_via_constructor_in_vm_context = esc
try { esc = vm.runInContext("this.constructor.constructor('return process.mainModule.require(\"fs\").readdirSync(\".\").length')()", newCtx()) } catch (e) { esc = 'blocked ' + String(e.message).slice(0, 70) }
out.escape_reads_filesystem = esc
console.log(JSON.stringify(out, null, 1))
