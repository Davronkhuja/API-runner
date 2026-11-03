/** pm.* (va legacy) API: avtoto'ldirish ro'yxati va tayyor snippet'lar. */
export interface Api { label: string; detail: string; type: 'function' | 'property' | 'class' | 'keyword' | 'constant' | 'variable' }
const fn = (label: string, detail: string): Api => ({ label, detail, type: 'function' })
const pr = (label: string, detail: string): Api => ({ label, detail, type: 'property' })
const scope = (p: string, what: string): Api[] => [
  fn(`${p}.get`, `(key) — ${what} qiymati`), fn(`${p}.set`, `(key, value) — ${what}ga yozish`), fn(`${p}.unset`, `(key) — o'chirish`), fn(`${p}.has`, '(key) → boolean'),
  fn(`${p}.clear`, '() — hammasini o\'chirish'), fn(`${p}.toObject`, '() → object'), fn(`${p}.replaceIn`, '(template) — {{var}} larni yechadi'),
]

export const PM_API: Api[] = [
  ...scope('pm.environment', 'muhit'), pr('pm.environment.name', 'faol muhit nomi'),
  ...scope('pm.globals', 'global'), ...scope('pm.collectionVariables', 'collection'),
  fn('pm.variables.get', '(key) — barcha scope\'lardan (Local > Data > Env > Collection > Global)'), fn('pm.variables.set', '(key, value) — local scope'), fn('pm.variables.has', '(key)'), fn('pm.variables.unset', '(key)'),
  fn('pm.variables.replaceIn', "(template) — {{var}}, {{$guid}}"), fn('pm.variables.toObject', '()'),
  fn('pm.iterationData.get', '(key) — Runner/Batch data qatori'), fn('pm.iterationData.has', '(key)'), fn('pm.iterationData.toObject', '()'),
  pr('pm.info.eventName', "'prerequest' | 'test'"), pr('pm.info.iteration', 'joriy iteratsiya (0 dan)'), pr('pm.info.iterationCount', 'jami iteratsiyalar'), pr('pm.info.requestName', "so'rov nomi"), pr('pm.info.requestId', "so'rov id"),
  pr('pm.request.method', 'GET | POST … (pre-request\'da o\'zgartirish mumkin)'), pr('pm.request.url', 'Url ob\'ekti'), pr('pm.request.headers', 'PropertyList'), pr('pm.request.body', '{ mode, raw }'),
  fn('pm.request.url.toString', '() → URL matn'), fn('pm.request.url.getHost', '()'), fn('pm.request.url.getPath', '()'), fn('pm.request.url.getQueryString', '()'), pr('pm.request.url.query', 'PropertyList'),
  fn('pm.request.url.query.add', '({ key, value })'), fn('pm.request.url.query.get', '(key)'), fn('pm.request.url.query.remove', '(key)'), fn('pm.request.url.addQueryParams', '(string | [{key,value}])'),
  fn('pm.request.headers.add', '({ key, value })'), fn('pm.request.headers.upsert', '({ key, value })'), fn('pm.request.headers.get', '(name)'), fn('pm.request.headers.has', '(name)'), fn('pm.request.headers.remove', '(name)'),
  fn('pm.request.body.update', '(string | object)'), pr('pm.request.body.raw', 'xom matn'),
  pr('pm.response.code', 'HTTP status kodi'), pr('pm.response.status', "'OK' …"), pr('pm.response.responseTime', 'ms'), pr('pm.response.responseSize', 'bayt'), pr('pm.response.headers', 'PropertyList (katta-kichik harfga sezgir emas)'), pr('pm.response.cookies', 'PropertyList'),
  fn('pm.response.json', '() → JSON'), fn('pm.response.text', '() → matn'), fn('pm.response.headers.get', '(name)'), fn('pm.response.headers.has', '(name)'),
  fn('pm.response.to.have.status', '(code | "OK")'), fn('pm.response.to.have.header', '(name[, value])'), fn('pm.response.to.have.body', '(string | RegExp)'), fn('pm.response.to.have.jsonBody', '([path[, value]])'),
  pr('pm.response.to.be.ok', '200'), pr('pm.response.to.be.success', '2xx'), pr('pm.response.to.be.error', '4xx/5xx'), pr('pm.response.to.be.clientError', '4xx'), pr('pm.response.to.be.serverError', '5xx'), pr('pm.response.to.be.json', 'JSON body'),
  pr('pm.response.to.be.notFound', '404'), pr('pm.response.to.be.unauthorized', '401'), pr('pm.response.to.be.forbidden', '403'), pr('pm.response.to.be.badRequest', '400'), pr('pm.response.to.have.withBody', 'body bor'),
  fn('pm.test', '(name, fn | async fn | fn(done))'), fn('pm.test.skip', '(name, fn)'), fn('pm.expect', '(value) — chai: .to.equal, .to.eql, .to.have.property …'),
  fn('pm.sendRequest', '(url | request, callback(err, res)) → Promise'), fn('pm.execution.setNextRequest', '(name | null)'), fn('pm.execution.skipRequest', '() — faqat pre-request'),
  fn('pm.cookies.get', '(name)'), fn('pm.cookies.has', '(name)'), fn('pm.cookies.toObject', '()'), fn('pm.cookies.jar', '() → { get, getAll, set, unset, clear }'),
  fn('console.log', '(...args)'), fn('console.info', '(...args)'), fn('console.warn', '(...args)'), fn('console.error', '(...args)'), fn('console.debug', '(...args)'),
  fn('require', "('lodash' | 'crypto-js' | 'moment' | 'chai' | 'dayjs' | 'uuid' | 'xml2js')"), fn('setTimeout', '(fn, ms)'), fn('setInterval', '(fn, ms)'), fn('clearTimeout', '(id)'), fn('atob', '(base64)'), fn('btoa', '(text)'),
  // legacy
  pr('tests', '["nom"] = boolean (eski uslub)'), pr('responseBody', 'javob matni (legacy)'), pr('responseCode', '{ code, name, detail } (legacy)'), pr('responseTime', 'ms (legacy)'), pr('responseHeaders', 'obyekt (legacy)'),
  fn('postman.setEnvironmentVariable', '(key, value)'), fn('postman.getEnvironmentVariable', '(key)'), fn('postman.clearEnvironmentVariable', '(key)'), fn('postman.setGlobalVariable', '(key, value)'), fn('postman.getGlobalVariable', '(key)'),
  fn('postman.setNextRequest', '(name | null)'), fn('postman.getResponseHeader', '(name)'), fn('xml2Json', '(xml) — legacy'),
  { label: '_', detail: 'lodash', type: 'variable' }, { label: 'CryptoJS', detail: 'crypto-js', type: 'variable' }, { label: 'moment', detail: 'moment', type: 'variable' }, { label: 'dayjs', detail: 'dayjs', type: 'variable' },
  { label: 'environment', detail: 'faol muhit obyekti (legacy)', type: 'variable' }, { label: 'globals', detail: 'global o\'zgaruvchilar obyekti (legacy)', type: 'variable' },
]

export interface Snippet { title: string; where: 'pre' | 'test' | 'both'; code: string }
export const SNIPPETS: Snippet[] = [
  { title: 'Status kodi 200', where: 'test', code: 'pm.test("Status kodi 200", function () {\n    pm.response.to.have.status(200);\n});\n' },
  { title: 'Javob vaqti < 500 ms', where: 'test', code: 'pm.test("Javob vaqti 500 ms dan kam", function () {\n    pm.expect(pm.response.responseTime).to.be.below(500);\n});\n' },
  { title: 'JSON qiymatini tekshirish', where: 'test', code: 'pm.test("JSON qiymati to\'g\'ri", function () {\n    var jsonData = pm.response.json();\n    pm.expect(jsonData.value).to.eql(100);\n});\n' },
  { title: 'Javobdan muhitga yozish', where: 'test', code: 'var jsonData = pm.response.json();\npm.environment.set("variable_key", jsonData.value);\n' },
  { title: 'Token olib Bearer sifatida saqlash', where: 'test', code: 'var jsonData = pm.response.json();\npm.environment.set("token", jsonData.access_token);\n' },
  { title: 'Header mavjudligi', where: 'test', code: 'pm.test("Content-Type header bor", function () {\n    pm.response.to.have.header("Content-Type");\n});\n' },
  { title: 'Body matn o\'z ichiga oladi', where: 'test', code: 'pm.test("Body matni bor", function () {\n    pm.expect(pm.response.text()).to.include("string_you_want_to_search");\n});\n' },
  { title: 'Javob JSON ekanini tekshirish', where: 'test', code: 'pm.test("Javob JSON", function () {\n    pm.response.to.be.json;\n    pm.response.to.have.withBody;\n});\n' },
  { title: 'Keyingi so\'rov (setNextRequest)', where: 'test', code: 'pm.execution.setNextRequest("So\'rov nomi");\n// run\'ni to\'xtatish: pm.execution.setNextRequest(null);\n' },
  { title: 'Muhit o\'zgaruvchisini olish', where: 'both', code: 'var value = pm.environment.get("variable_key");\n' },
  { title: 'Muhit o\'zgaruvchisini o\'chirish', where: 'both', code: 'pm.environment.unset("variable_key");\n' },
  { title: 'So\'rov yuborish (pm.sendRequest)', where: 'both', code: 'pm.sendRequest("https://example.com/get", function (err, res) {\n    if (err) { console.error(err); return; }\n    console.log(res.json());\n});\n' },
  { title: 'Pre-request: token bo\'lmasa olish', where: 'pre', code: 'if (!pm.environment.get("token")) {\n    pm.sendRequest({\n        url: pm.environment.get("base_url") + "/auth/token",\n        method: "POST",\n        header: { "Content-Type": "application/json" },\n        body: { mode: "raw", raw: JSON.stringify({ client_id: "id", client_secret: "secret" }) }\n    }, function (err, res) {\n        if (!err) pm.environment.set("token", res.json().access_token);\n    });\n}\n' },
  { title: 'Pre-request: header qo\'shish', where: 'pre', code: 'pm.request.headers.add({ key: "X-Request-Id", value: pm.variables.replaceIn("{{$guid}}") });\n' },
  { title: 'Pre-request: so\'rovni o\'tkazib yuborish', where: 'pre', code: 'if (!pm.environment.get("token")) {\n    pm.execution.skipRequest();\n}\n' },
  { title: 'Vaqt tamg\'asi (ISO)', where: 'both', code: 'pm.variables.set("now", new Date().toISOString());\n' },
  { title: 'Tasodifiy GUID', where: 'both', code: 'pm.variables.set("guid", pm.variables.replaceIn("{{$guid}}"));\n' },
  { title: 'HMAC-SHA256 (CryptoJS)', where: 'pre', code: 'const CryptoJS = require("crypto-js");\nconst sig = CryptoJS.HmacSHA256("message", "secret").toString();\npm.variables.set("signature", sig);\n' },
  { title: 'Legacy: tests["…"]', where: 'test', code: 'tests["Status kodi 200"] = responseCode.code === 200;\n' },
  { title: 'Console log', where: 'both', code: 'console.log("qiymat:", pm.variables.get("key"));\n' },
]
