/* Offline tests: never request or click a real advertisement. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const code = fs.readFileSync(`${__dirname}/site/adsense.js`, 'utf8');
function harness(client, enabled) {
  const nodes = [], attributes = {};
  const document = {
    documentElement: {setAttribute: (key, value) => {attributes[key] = value;}},
    head: {append: node => {nodes.push(node); node.parentNode = document.head;}},
    createElement: tag => ({tag}),
    querySelector: () => nodes.find(node => node.name === 'google-adsense-account'),
    getElementById: id => nodes.find(node => node.id === id)
  };
  const context = vm.createContext({document, window: {
    WORLD_DESK_ADSENSE_CLIENT: client, WORLD_DESK_ADSENSE_ENABLED: enabled
  }});
  const run = () => vm.runInContext(code, context);
  return {nodes, attributes, run};
}
test('missing or malformed publisher ID never loads third-party code', () => {
  for (const id of [undefined, '', 'ca-pub-123', 'https://untrusted.example/script', '<script>']) {
    const h = harness(id, true); h.run();
    assert.equal(h.nodes.length, 0);
    assert.equal(h.attributes['data-adsense-state'], 'not-configured');
  }
});
test('valid ID alone supports review without starting ads', () => {
  for (const enabled of [false, undefined, 'true', 1]) {
    const h = harness('ca-pub-1234567890123456', enabled); h.run(); h.run();
    assert.equal(h.nodes.length, 1);
    assert.equal(h.nodes[0].name, 'google-adsense-account');
    assert.equal(h.attributes['data-adsense-state'], 'awaiting-activation');
  }
});
test('explicit activation inserts the official script exactly once', () => {
  const h = harness('ca-pub-1234567890123456', true); h.run(); h.run();
  assert.equal(h.nodes.length, 2);
  const script = h.nodes.find(node => node.tag === 'script');
  assert.equal(script.src, 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1234567890123456');
  assert.equal(script.async, true);
  assert.equal(script.crossOrigin, 'anonymous');
  assert.equal(h.attributes['data-adsense-state'], 'script-requested');
  script.onload(); h.run();
  assert.equal(h.attributes['data-adsense-state'], 'script-loaded');
});
test('blocked or failed network script is reported without retry loops', () => {
  const h = harness('ca-pub-1234567890123456', true); h.run();
  h.nodes.find(node => node.tag === 'script').onerror(); h.run();
  assert.equal(h.attributes['data-adsense-state'], 'script-unavailable');
  assert.equal(h.nodes.length, 2);
});
