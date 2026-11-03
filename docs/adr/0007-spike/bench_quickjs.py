import json, statistics, time, quickjs
LIBS = ['chai.js', 'lodash.min.js', 'crypto-js.js', 'dayjs.min.js']
src = {l: open('libs/' + l, encoding='utf-8').read() for l in LIBS}
def ms(f, n=1):
    t = time.perf_counter(); r = None
    for _ in range(n): r = f()
    return (time.perf_counter() - t) / n * 1000, r
out = {}
out['import_ver'] = quickjs.__file__.split('site-packages/')[1]
out['ctx_create_ms'] = round(ms(lambda: quickjs.Context(), 500)[0], 3)
out['trivial_script_fresh_ctx_ms'] = round(ms(lambda: quickjs.Context().eval('var a=1;a+1'), 500)[0], 3)
for l in LIBS:
    def load(l=l):
        c = quickjs.Context(); c.eval(src[l]); return c
    t, _ = ms(load, 20)
    out['load_' + l + '_ms'] = round(t, 2)
def all_libs():
    c = quickjs.Context()
    for l in LIBS: c.eval(src[l])
    return c
out['load_all_ms'] = round(ms(all_libs, 10)[0], 2)
# kutubxonalar ishlaydimi
c = all_libs()
res = {}
for name, code in {
    'chai': "typeof chai !== 'undefined' && chai.expect(5).to.be.above(3) && chai.expect({a:1}).to.have.property('a') && 'ok'",
    'lodash': "_.chunk([1,2,3,4],2).length + _.get({a:{b:3}},'a.b')",
    'cryptojs_md5': "CryptoJS.MD5('abc').toString()",
    'cryptojs_hmac': "CryptoJS.HmacSHA256('msg','key').toString()",
    'cryptojs_aes': "CryptoJS.AES.decrypt(CryptoJS.AES.encrypt('hello','pw').toString(),'pw').toString(CryptoJS.enc.Utf8)",
    'dayjs': "dayjs('2026-11-03').add(1,'day').format('YYYY-MM-DD')",
}.items():
    try: res[name] = c.eval(code)
    except Exception as e: res[name] = 'ERR ' + str(e)[:80]
out['libs_work'] = res
# ish tezligi
fib = "function fib(n){return n<2?n:fib(n-1)+fib(n-2)}"
c2 = quickjs.Context(); c2.eval(fib)
out['fib27_ms'] = round(ms(lambda: c2.eval('fib(27)'))[0], 1)
out['loop_1e7_ms'] = round(ms(lambda: c2.eval('var s=0;for(var i=0;i<1e7;i++)s+=i;s'))[0], 1)
big = json.dumps({'items': [{'id': i, 'name': 'x' * 20, 'v': i * 1.5} for i in range(20000)]})
out['json_payload_MB'] = round(len(big) / 1e6, 2)
c2.set_memory_limit(512 * 1024 * 1024)
c2.eval('var BIG=' + json.dumps(big))   # satr sifatida
out['json_parse_stringify_ms'] = round(ms(lambda: c2.eval('JSON.stringify(JSON.parse(BIG)).length'))[0], 1)
out['json_parse_via_python_roundtrip_ms'] = round(ms(lambda: c2.eval('JSON.parse(BIG).items.length'))[0], 1)
# 1000 ta ketma-ket "so'rov skripti" (yangi kontekst + chai + tekshiruv)
def one():
    c = quickjs.Context(); c.eval(src['chai.js']); c.eval("chai.expect(200).to.equal(200)")
out['1_script_with_chai_fresh_ctx_ms'] = round(ms(one, 20)[0], 2)
# kontekstni qayta ishlatish (kutubxonalar bir marta)
cc = all_libs()
out['reused_ctx_script_ms'] = round(ms(lambda: cc.eval("chai.expect(_.sum([1,2,3])).to.equal(6)"), 2000)[0], 4)
# Python <-> JS ko'prigi
cb = quickjs.Context(); cb.add_callable('py', lambda x: x + 1)
out['bridge_10k_callbacks_ms'] = round(ms(lambda: cb.eval('var s=0;for(var i=0;i<10000;i++)s=py(s);s'))[0], 1)
# limitlar
lim = {}
c3 = quickjs.Context(); c3.set_time_limit(0.3)
t = time.perf_counter()
try: c3.eval('while(true){}'); lim['infinite_loop'] = 'NOT STOPPED'
except Exception as e: lim['infinite_loop'] = f'stopped after {time.perf_counter()-t:.2f}s: {str(e)[:60]}'
c4 = quickjs.Context(); c4.set_memory_limit(16 * 1024 * 1024)
try: c4.eval("var a=[];while(true)a.push(new Array(10000).fill(1))"); lim['memory_bomb'] = 'NOT STOPPED'
except Exception as e: lim['memory_bomb'] = 'stopped: ' + str(e)[:60]
c5 = quickjs.Context(); c5.set_max_stack_size(256 * 1024)
try: c5.eval('function r(){return r()+1}r()'); lim['deep_recursion'] = 'NOT STOPPED'
except Exception as e: lim['deep_recursion'] = 'stopped: ' + str(e)[:60]
c6 = quickjs.Context(); c6.set_time_limit(0.3)
try: c6.eval('function f(){ try { while(true){} } catch(e){} } f()'); lim['catch_swallow'] = 'NOT STOPPED'
except Exception as e: lim['catch_swallow'] = 'stopped: ' + str(e)[:50]
out['limits'] = lim
# izolyatsiya
iso = quickjs.Context()
globs = {}
for g in ['require', 'process', 'fetch', 'XMLHttpRequest', 'std', 'os', 'window', 'globalThis.module', 'setTimeout', 'Buffer', 'WebSocket', 'import']:
    try: globs[g] = iso.eval(f"typeof {g}")
    except Exception as e: globs[g] = 'err'
out['typeof_globals'] = globs
try: iso.eval("import('os')"); out['dynamic_import'] = 'possible?'
except Exception as e: out['dynamic_import'] = 'blocked: ' + str(e)[:50]
try:
    out['escape_via_constructor'] = iso.eval("this.constructor.constructor('return typeof process')()")
except Exception as e: out['escape_via_constructor'] = 'err ' + str(e)[:40]
print(json.dumps(out, indent=1, ensure_ascii=False))
