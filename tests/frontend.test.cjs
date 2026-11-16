const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('static/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
// Parse the whole script; execute the actual result/history code with a small DOM.
new vm.Script(script);

function attributes() {
  const entries = new Map();
  return {
    setAttribute(name, value) { entries.set(name, value); },
    getAttribute(name) { return entries.get(name) ?? null; },
    removeAttribute(name) { entries.delete(name); }
  };
}

function field(id, value) {
  return { ...attributes(), id, value, style: {}, textContent: '', children: [],
    labels: [{ textContent: { idPaciente: 'ID del paciente', edad: 'Edad' }[id] || id }],
    classList: { add() {}, remove() {}, toggle() {} },
    querySelectorAll: () => [], replaceChildren() {},
    parentElement: { clientWidth: 320, clientHeight: 100 }, getContext: () => ({}) };
}

function context() {
  const nodes = new Map();
  function element() {
    return { ...attributes(), style: {}, classList: { add() {} }, children: [], querySelectorAll: () => [],
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); },
      addEventListener(name, handler) { this[name] = handler; } };
  }
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto, t: key => key,
    document: { createElement: element, getElementById: id => {
      if (!nodes.has(id)) nodes.set(id, element());
      return nodes.get(id);
    } } });
  vm.runInContext('let history = []; let lastResult = null; let formResult = null; let resultRevision = 0; let formRevision = 0;\n' + script.slice(script.indexOf('const contentAnimations'),
    script.indexOf('// Restore the language')), scope);
  return { scope, nodes };
}

test('empty history renders without shadowing the translation function', () => {
  const { scope, nodes } = context();
  vm.runInContext('renderHistory()', scope);
  assert.equal(nodes.get('historyStrip').children[0].textContent, 'sin_evals');
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

test('explicit result navigation scrolls and focuses on repeated activation', () => {
  const actions = [];
  const scope = vm.createContext({
    event: { currentTarget: { hash: '#resultSection' }, preventDefault() { actions.push('prevent'); } },
    document: { getElementById(id) {
      assert.equal(id, 'resultSection');
      return {
        focus(options) { actions.push(options.preventScroll); },
        scrollIntoView(options) { actions.push(options.block); }
      };
    } }
  });
  vm.runInContext(script.slice(script.indexOf('function goToSection'), script.indexOf('function viewFormResult')), scope);
  vm.runInContext('goToSection(event); goToSection(event);', scope);
  assert.deepEqual(actions, ['prevent', true, 'start', 'prevent', true, 'start']);
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
  assert.equal(nodes.get('historyStrip').children[0].getAttribute('aria-pressed'), 'true');
  assert.equal(nodes.get('viewHistoryResult').hidden, false);
  assert.equal(nodes.get('reasoningDetails').hidden, false);
});

test('plain explanation uses only the decisive observations, preserving ties and groups', () => {
  const { scope, nodes } = context();
  scope.result = {
    id_paciente: 'EXPERT-1', nivel_prioridad: 2,
    metadata_motor: { explicaciones: {
      how: { nivel_asignado: 2 },
      why: [
        { regla: 'R012', razon: 'Texto técnico', evidencia: [
          { hecho: 'dificultad_respiratoria', actual: true },
          { hecho: 'spo2', actual: 92, esperado: 94 }
        ] },
        { regla: 'R040', razon: 'Texto de ampliación', evidencia: [
          { hecho: 'sx_desconocido', actual: true }
        ] }
      ],
      trace: [{ regla_id: 'R042', activa: true, decisiva: false, conclusion: 'No decisiva' }],
      hechos_finales: { spo2: 92 },
      conocimiento: { snapshot: { version: '4.0.0' } }
    } }
  };
  vm.runInContext('showResult(result)', scope);
  const reasons = nodes.get('resultReasons').children.map(item => item.textContent);
  assert.deepEqual(reasons, ['Dificultad para respirar: sí · Saturación de oxígeno: 92 %', 'Texto de ampliación']);
  assert.match(nodes.get('reasoningTrace').textContent, /R042/);
  assert.match(nodes.get('reasoningFacts').textContent, /spo2/);
  assert.match(nodes.get('reasoningSnapshot').textContent, /4.0.0/);

  scope.result.nivel_prioridad = 5;
  vm.runInContext('showResult(result)', scope);
  assert.equal(nodes.get('resultReasons').hidden, true);
  assert.match(nodes.get('resMotivo').textContent, /no está disponible/);
});

test('fallback uses the attached inference and a legacy result shows its saved reason', () => {
  const { scope, nodes } = context();
  scope.result = { nivel_prioridad: 5, motivo_clinico: 'Motivo histórico',
    metadata_motor: { explicaciones: { why: [{ razon: 'Criterio de respaldo', evidencia: [] }] } } };
  vm.runInContext('showResult(result)', scope);
  assert.equal(nodes.get('resultReasons').children[0].textContent, 'Criterio de respaldo');
  vm.runInContext('delete result.metadata_motor; showResult(result)', scope);
  assert.equal(nodes.get('resMotivo').textContent, 'Motivo registrado: Motivo histórico');
  assert.equal(nodes.get('resultReasons').children.length, 0);
});

test('a saved Quechua language initializes the full script and allows evaluation', async () => {
  const nodes = new Map();
  const title = { textContent: '', getAttribute: () => 'app_title' };
  const buttons = ['es', 'qu'].map(lang => ({ ...attributes(), dataset: { lang },
    classList: { toggle(_name, active) { this.active = active; } } }));
  const stored = new Map([['triaje_lang', 'qu']]);
  const values = { idPaciente: 'P-1', edad: '30', fc: '80', spo2: '98',
    pas: '120', pad: '80', temp: '36.5', conciencia: 'Alerta' };
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    localStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) },
    document: { documentElement: {},
      querySelectorAll: selector => selector === '[data-i18n]' ? [title] :
        selector === '.lang-btn' ? buttons : [],
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, field(id, values[id] ?? ''));
        return nodes.get(id);
      } },
    window: { addEventListener() {} }, setInterval() {}, requestAnimationFrame() {},
    fetch: async path => path === '/conocimiento/sintomas' ? { ok: true, json: async () => ({ sintomas: [] }) } : ({ ok: false, json: async () => ({ detail: 'validation' }) }),
  });
  assert.doesNotThrow(() => vm.runInContext(script, scope));
  assert.equal(scope.document.documentElement.lang, 'qu');
  assert.equal(title.textContent, vm.runInContext('I18N.qu.app_title', scope));
  assert.equal(buttons[1].classList.active, true);
  assert.ok(nodes.get('clock').textContent);
  assert.equal(vm.runInContext('lastResult', scope), null);
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  await vm.runInContext('evaluar({ preventDefault() {} })', scope);
  assert.equal(buttons[1].getAttribute('aria-pressed'), 'true');
  assert.equal(nodes.get('translationNotice').hidden, false);
  assert.match(nodes.get('evaluationError').textContent, /validation/);
  assert.equal(nodes.get('btnEval').getAttribute('aria-disabled'), null);
});

test('empty identifier or age blocks the request with a friendly message', async () => {
  const nodes = new Map();
  const values = { idPaciente: '', edad: '', fc: '80', spo2: '98',
    pas: '120', pad: '80', temp: '36.5', conciencia: 'Alerta' };
  let fetchCalls = 0;
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    localStorage: { getItem: () => 'es', setItem() {} },
    document: { documentElement: {},
      querySelectorAll: () => [],
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, field(id, values[id] ?? ''));
        return nodes.get(id);
      } },
    window: { addEventListener() {} }, setInterval() {}, requestAnimationFrame() {},
    fetch: async path => { if (path === '/conocimiento/sintomas') return { ok: true, json: async () => ({ sintomas: [] }) }; fetchCalls++; return { ok: false, json: async () => ({ detail: [] }) }; },
  });
  assert.doesNotThrow(() => vm.runInContext(script, scope));
  await vm.runInContext('loadAdditionalSymptoms()', scope);
  await vm.runInContext('evaluar({ preventDefault() {} })', scope);
  assert.equal(fetchCalls, 0);
  assert.match(nodes.get('evaluationError').textContent, /ID del paciente, Edad/);
  assert.equal(nodes.get('edad').getAttribute('aria-invalid'), 'true');
  assert.equal(nodes.get('edad').getAttribute('aria-describedby'), 'edadError');
  assert.equal(nodes.get('edadError').hidden, false);
  vm.runInContext("formEdited({ target: document.getElementById('edad') })", scope);
  assert.equal(nodes.get('edad').getAttribute('aria-invalid'), null);
  assert.equal(nodes.get('edadError').hidden, true);
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
  const values = {idPaciente:'RETRY-TEST',edad:'30',fc:'80',spo2:'98',pas:'120',pad:'80',temp:'36.5',conciencia:'Alerta'};
  const calls = [];
  let catalogCalls = 0;
  const scope = vm.createContext({ crypto: require("node:crypto").webcrypto,
    document: {documentElement:{},querySelectorAll:()=>[],getElementById(id){
      if (!nodes.has(id)) nodes.set(id, field(id, values[id] ?? ''));
      return nodes.get(id);
    }},
    localStorage:{getItem:()=> 'es',setItem(){}},window:{addEventListener(){}},
    setInterval(){},requestAnimationFrame(){},
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
  assert.equal(nodes.get('btnSave').getAttribute('aria-disabled'), null);
  assert.match(nodes.get('evaluationStatus').textContent, /Evaluación guardada/);
  assert.equal(vm.runInContext('formResult.metadata_motor.guardado_en_bd',scope),true);
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
