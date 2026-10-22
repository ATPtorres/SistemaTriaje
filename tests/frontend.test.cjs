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
  const scope = vm.createContext({ LANG: 'es', COLOR_QU: {}, t: key => key,
    document: { createElement: element, getElementById: id => {
      if (!nodes.has(id)) nodes.set(id, element());
      return nodes.get(id);
    } } });
  vm.runInContext('let history = [];\n' + script.slice(script.indexOf('const bgMap'),
    script.indexOf('// Restore the language')), scope);
  return { scope, nodes };
}

test('empty history renders without shadowing the translation function', () => {
  const { scope, nodes } = context();
  vm.runInContext('renderHistory()', scope);
  assert.match(nodes.get('historyStrip').innerHTML, /sin_evals/);
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
  const scope = vm.createContext({
    localStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) },
    document: { documentElement: {},
      querySelectorAll: selector => selector === '[data-i18n]' ? [title] :
        selector === '.lang-btn' ? buttons : [],
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, { value: values[id] ?? '75', style: {}, textContent: '',
          classList: { add() {}, remove() {}, toggle() {} }, focus() {},
          parentElement: { clientWidth: 320, clientHeight: 100 }, getContext: () => canvasContext });
        return nodes.get(id);
      } },
    window: { addEventListener() {} }, setInterval() {}, requestAnimationFrame() {},
    fetch: async () => ({ ok: false, json: async () => ({ detail: 'validation' }) }),
    alert() {},
  });
  assert.doesNotThrow(() => vm.runInContext(script, scope));
  assert.equal(scope.document.documentElement.lang, 'qu');
  assert.equal(title.textContent, vm.runInContext('I18N.qu.app_title', scope));
  assert.equal(buttons[1].classList.active, true);
  assert.ok(nodes.get('clock').textContent);
  assert.equal(vm.runInContext('lastResult', scope), null);
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
  const scope = vm.createContext({
    localStorage: { getItem: () => 'es', setItem() {} },
    document: { documentElement: {},
      querySelectorAll: () => [],
      getElementById(id) {
        if (!nodes.has(id)) nodes.set(id, { value: values[id] ?? '75', style: {}, textContent: '',
          classList: { add() {}, remove() {}, toggle() {} }, focus() {},
          parentElement: { clientWidth: 320, clientHeight: 100 }, getContext: () => canvasContext });
        return nodes.get(id);
      } },
    window: { addEventListener() {} }, setInterval() {}, requestAnimationFrame() {},
    fetch: async () => { fetchCalls++; return { ok: false, json: async () => ({ detail: [] }) }; },
    alert: message => alerts.push(message),
  });
  assert.doesNotThrow(() => vm.runInContext(script, scope));
  await vm.runInContext('evaluar({ preventDefault() {} })', scope);
  assert.equal(fetchCalls, 0);
  assert.equal(alerts.length, 1);
  assert.match(alerts[0], /incompletos/);
  assert.match(alerts[0], /ID Paciente/);
  assert.match(alerts[0], /Edad/);
});
