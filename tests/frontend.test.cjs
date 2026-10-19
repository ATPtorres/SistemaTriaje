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
  vm.runInContext('let history = [];\n' + script.slice(script.indexOf('const bgMap')), scope);
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
