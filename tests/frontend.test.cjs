const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
// Parse the whole script; execute the actual result/history code with a small DOM.
new vm.Script(script);

function context() {
  const nodes = new Map();
  function element() {
    return { style: {}, classList: { add() {} }, children: [],
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); },
      addEventListener(name, handler) { this[name] = handler; } };
  }
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto, LANG: 'es', COLOR_QU: {}, t: key => key,
    document: { createElement: element, getElementById: id => {
      if (!nodes.has(id)) nodes.set(id, element());
      return nodes.get(id);
    } } });
  vm.runInContext('let history = []; let lastResult = null;\n' + script.slice(script.indexOf('const contentAnimations'),
    script.indexOf('// Restore the language')), scope);
  return { scope, nodes };
}

test('empty history renders without shadowing the translation function', () => {
  const { scope, nodes } = context();
  vm.runInContext('renderHistory()', scope);
  assert.match(nodes.get('historyStrip').innerHTML, /sin_evals/);
});

test('content transitions cancel previous motion and respect reduced motion', () => {
  const { scope } = context();
  const animations = [];
  let cancelled = 0;
  scope.panel = { animate(frames, options) {
    animations.push({ frames, options });
    return { cancel() { cancelled++; } };
  } };
  scope.matchMedia = () => ({ matches: false });
  vm.runInContext('transitionContent(panel); transitionContent(panel)', scope);
  assert.equal(animations.length, 2);
  assert.equal(cancelled, 1);
  scope.matchMedia = () => ({ matches: true });
  vm.runInContext('transitionContent(panel)', scope);
  assert.equal(animations.length, 2);
  assert.equal(cancelled, 2);
  assert.doesNotThrow(() => vm.runInContext('transitionContent(null); transitionContent({})', scope));
});

test('patient identifiers and alerts are rendered as text', () => {
  const { scope, nodes } = context();
  const attack = '<img src=x onerror=alert(1)>';
  scope.result = { id_paciente: attack, nivel_prioridad: 5, color: 'Azul',
    motivo_clinico: 'test', recomendacion: 'test', signos_alerta: [attack] };
  vm.runInContext('showResult(result); pushHistory(result)', scope);
  const chip = nodes.get('historyStrip').children[0];
  assert.equal(chip.children[1].textContent, attack);
  assert.equal(chip.children[1].innerHTML, undefined);
  assert.equal(nodes.get('resAlertas').children[0].textContent, attack);
  assert.equal(chip.type, 'button');
  assert.doesNotThrow(() => chip.click());
});

test('reasoning is safe text and history keeps the selected explanation', () => {
  const { scope, nodes } = context();
  const attack = '<img src=x onerror=alert(1)>';
  scope.result = { id_paciente: 'EXPERT-1', nivel_prioridad: 2, color: 'Naranja',
    motivo_clinico: 'test', recomendacion: 'test', metadata_motor: {
      explicaciones: { trace: [{ regla_id: 'R011', activa: true, decisiva: true,
        iteracion: 1, conclusion: attack, condiciones_evaluadas: [] }],
        conocimiento: { version: '4.0.0', sha256: 'abc' } } } };
  vm.runInContext('pushHistory(result); showResult(result)', scope);
  const item = nodes.get('reasoningSteps').children[0];
  assert.ok(item.textContent.includes(attack));
  assert.equal(item.innerHTML, undefined);
  assert.equal(nodes.get('reasoningDetails').hidden, false);
  assert.match(nodes.get('reasoningKnowledge').textContent, /4\.0\.0/);
  scope.other = { id_paciente: 'EXPERT-2', nivel_prioridad: 5, color: 'Azul',
    motivo_clinico: 'other', recomendacion: 'other' };
  vm.runInContext('showResult(other)', scope);
  assert.equal(nodes.get('reasoningDetails').hidden, true);
  assert.equal(nodes.get('reasoningSteps').children.length, 0);
  nodes.get('historyStrip').children[0].click();
  assert.equal(vm.runInContext('lastResult === result', scope), true);
  assert.equal(nodes.get('reasoningDetails').hidden, false);
});

test('a saved Quechua language initializes the full script and allows evaluation', async () => {
  const nodes = new Map();
  const title = { textContent: '', getAttribute: () => 'app_title' };
  const buttons = ['es', 'qu'].map(lang => ({ dataset: { lang },
    classList: { toggle(_name, active) { this.active = active; } } }));
  const canvasContext = Object.fromEntries(['fillRect', 'beginPath', 'moveTo',
    'lineTo', 'stroke', 'arc', 'fill'].map(name => [name, () => {}]));
  const stored = new Map([['triaje_lang', 'qu']]);
  const values = { idPaciente: 'P-1', edad: '30', fc: '80', spo2: '98',
    pas: '120', pad: '80', temp: '36.5', conciencia: 'Alerta' };
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    localStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) },
    document: { documentElement: {},
      querySelectorAll: selector => selector === '[data-i18n]' ? [title] :
        selector === '.lang-btn' ? buttons : [],
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, { value: values[id] ?? '75', style: {}, textContent: '',
          classList: { add() {}, remove() {}, toggle() {} }, focus() {},
          querySelectorAll: () => [], replaceChildren() {}, children: [],
          parentElement: { clientWidth: 320, clientHeight: 100 }, getContext: () => canvasContext });
        return nodes.get(id);
      } },
    window: { addEventListener() {} }, setInterval() {}, requestAnimationFrame() {},
    fetch: async path => path === '/conocimiento/sintomas' ? { ok: true, json: async () => ({ sintomas: [] }) } : ({ ok: false, json: async () => ({ detail: 'validation' }) }),
    alert() {},
  });
  assert.doesNotThrow(() => vm.runInContext(script, scope));
  assert.equal(scope.document.documentElement.lang, 'qu');
  assert.equal(title.textContent, vm.runInContext('I18N.qu.app_title', scope));
  assert.equal(buttons[1].classList.active, true);
  assert.ok(nodes.get('clock').textContent);
  assert.equal(vm.runInContext('lastResult', scope), null);
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  await vm.runInContext('evaluar({ preventDefault() {} })', scope);
  assert.equal(nodes.get('btnEval').disabled, false);
  assert.equal(nodes.get('btnEval').textContent, vm.runInContext('I18N.qu.btn_eval', scope));
});

test('empty identifier or age blocks the request with a friendly message', async () => {
  const nodes = new Map();
  const canvasContext = Object.fromEntries(['fillRect', 'beginPath', 'moveTo',
    'lineTo', 'stroke', 'arc', 'fill'].map(name => [name, () => {}]));
  const values = { idPaciente: '', edad: '', fc: '80', spo2: '98',
    pas: '120', pad: '80', temp: '36.5', conciencia: 'Alerta' };
  const alerts = [];
  let fetchCalls = 0;
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    localStorage: { getItem: () => 'es', setItem() {} },
    document: { documentElement: {},
      querySelectorAll: () => [],
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, { value: values[id] ?? '75', style: {}, textContent: '',
          classList: { add() {}, remove() {}, toggle() {} }, focus() {},
          querySelectorAll: () => [], replaceChildren() {}, children: [],
          parentElement: { clientWidth: 320, clientHeight: 100 }, getContext: () => canvasContext });
        return nodes.get(id);
      } },
    window: { addEventListener() {} }, setInterval() {}, requestAnimationFrame() {},
    fetch: async path => { if (path === '/conocimiento/sintomas') return { ok: true, json: async () => ({ sintomas: [] }) }; fetchCalls++; return { ok: false, json: async () => ({ detail: [] }) }; },
    alert: message => alerts.push(message),
  });
  assert.doesNotThrow(() => vm.runInContext(script, scope));
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  await vm.runInContext('evaluar({ preventDefault() {} })', scope);
  assert.equal(fetchCalls, 0);
  assert.equal(alerts.length, 1);
  assert.match(alerts[0], /incompletos/);
  assert.match(alerts[0], /ID Paciente/);
  assert.match(alerts[0], /Edad/);
});


test('additional symptom catalog renders safe labels and three-state observations', async () => {
  function element() { return { children: [], dataset: {}, style: {},
    append(...items) { this.children.push(...items); }, replaceChildren() { this.children = []; },
    querySelectorAll() { return []; }, setAttribute() {} }; }
  const container = element();
  container.querySelectorAll = () => container.children.map(label => label.children[1]);
  const refreshButton = element();
  const catalogStatus = element();
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    document: { getElementById: id => id === 'additionalSymptoms' ? container : id === 'refreshCatalog' ? refreshButton : catalogStatus, createElement: element },
    fetch: async () => ({ok: true, json: async () => ({ sintomas: [
      { id: 'sx_'+'1'.repeat(32), nombre: '<img src=x onerror=alert(1)>', nivel: 3, activo: true },
      { id: 'sx_'+'2'.repeat(32), nombre: 'Desactivado', nivel: 2, activo: false }
    ] }) })
  });
  vm.runInContext(script.slice(script.indexOf('let additionalSymptomsReady'), script.indexOf('async function evaluar')), scope);
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  assert.equal(container.children.length, 1);
  assert.match(container.children[0].children[0].textContent, /<img/);
  const select = container.children[0].children[1];
  assert.equal(select.children.length, 3);
  assert.equal(select.value, '');
  assert.equal(vm.runInContext('additionalSymptomsReady', scope), true);
  assert.match(catalogStatus.textContent, /Catálogo actualizado: 1 síntoma activo/);
  assert.equal(refreshButton.disabled, false);
  select.value = 'true';
  let completeRefresh;
  scope.fetch = async (_path, options) => {
    assert.equal(options.cache, 'no-store');
    return new Promise(resolve => { completeRefresh = resolve; });
  };
  const refresh = vm.runInContext('loadAdditionalSymptoms()', scope);
  assert.equal(refreshButton.disabled, true);
  assert.equal(refreshButton.textContent, 'Actualizando…');
  completeRefresh({ok: true, json: async () => ({ sintomas: [
    {id: 'sx_'+'1'.repeat(32), nombre: 'Síntoma conservado', nivel: 3, activo: true},
    {id: 'sx_'+'3'.repeat(32), nombre: 'Síntoma nuevo', nivel: 2, activo: true}
  ] })});
  await refresh;
  assert.equal(container.children.length, 2);
  assert.equal(container.children[0].children[1].value, 'true');
  assert.equal(container.children[1].children[1].value, '');
  assert.match(catalogStatus.textContent, /2 síntomas activos/);
  scope.fetch = async () => ({ok: true, json: async () => ({ sintomas: [
    {id: 'sx_'+'1'.repeat(32), nombre: 'Síntoma conservado', nivel: 3, activo: false},
    {id: 'sx_'+'3'.repeat(32), nombre: 'Síntoma nuevo', nivel: 2, activo: true}
  ] })});
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  assert.equal(container.children.length, 1);
  assert.equal(container.children[0].children[1].dataset.symptom, 'sx_'+'3'.repeat(32));
  scope.fetch = async () => { throw new Error('offline'); };
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  assert.equal(vm.runInContext('additionalSymptomsReady', scope), false);
  assert.equal(refreshButton.disabled, false);
  assert.match(catalogStatus.textContent, /No se pudo actualizar/);
  assert.equal(container.children.length, 1);
});

test('knowledge editor script parses', () => {
  const page = fs.readFileSync('static/conocimiento.html', 'utf8');
  new vm.Script(page.match(/<script>([\s\S]*?)<\/script>/)[1]);
});


test('Guardar retries a failed catalog and submits a persistent evaluation', async () => {
  const nodes = new Map();
  const context2d = Object.fromEntries(['fillRect','beginPath','moveTo','lineTo','stroke','arc','fill'].map(name => [name, () => {}]));
  const values = {idPaciente:'RETRY-TEST',edad:'30',fc:'80',spo2:'98',pas:'120',pad:'80',temp:'36.5',conciencia:'Alerta'};
  const calls = [];
  let catalogCalls = 0;
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    document: {documentElement:{},querySelectorAll:()=>[],getElementById(id){
      if(!nodes.has(id)) nodes.set(id,{value:values[id]??'',style:{},textContent:'',children:[],
        classList:{add(){},remove(){},toggle(){}},focus(){},querySelectorAll:()=>[],replaceChildren(){},
        parentElement:{clientWidth:320,clientHeight:100},getContext:()=>context2d});
      return nodes.get(id);
    }},
    localStorage:{getItem:()=> 'es',setItem(){}},window:{addEventListener(){}},
    setInterval(){},requestAnimationFrame(){},alert(){},
    fetch:async(path,options)=>{
      calls.push({path,options});
      if(path==='/conocimiento/sintomas') {
        catalogCalls++;
        if(catalogCalls===1) throw new Error('network failed');
        return {ok:true,json:async()=>({sintomas:[]})};
      }
      return {ok:true,json:async()=>({id_paciente:'RETRY-TEST',nivel_prioridad:5,metadata_motor:{guardado_en_bd:true}})};
    }
  });
  vm.runInContext(script,scope);
  // Let the failed startup catalog request settle.
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(vm.runInContext('additionalSymptomsReady',scope),false);
  vm.runInContext('showResult = () => {}; pushHistory = () => {};',scope);
  await vm.runInContext('evaluar({preventDefault(){}})',scope);
  assert.equal(catalogCalls,2);
  assert.equal(calls.at(-1).path,'/triaje');
  assert.equal(JSON.parse(calls.at(-1).options.body).id_paciente,'RETRY-TEST');
  assert.equal(nodes.get('btnSave').disabled,false);
  assert.equal(nodes.get('btnSave').textContent,'Guardar');
  assert.equal(vm.runInContext('lastResult.metadata_motor.guardado_en_bd',scope),true);
  assert.match(html, /id="btnSave"[^>]*onclick="evaluar\(event\)"/);
});

test('local file and Apache previews redirect to the running app', () => {
  const bootstrap = script.slice(0,script.indexOf('// ===================== I18N'));
  for(const address of ['file:///C:/xampp/htdocs/triaje/static/index.html','http://localhost/triaje/static/index.html']) {
    const url = new URL(address);let target;
    vm.runInNewContext(bootstrap,{location:{protocol:url.protocol,hostname:url.hostname,port:url.port,replace(value){target=value;}}});
    assert.equal(target,'http://localhost:8000/');
  }
  let redirected=false;
  vm.runInNewContext(bootstrap,{location:{protocol:'http:',hostname:'localhost',port:'8000',replace(){redirected=true;}}});
  assert.equal(redirected,false);
});
