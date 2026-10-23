import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../../', import.meta.url);
const engine = await readFile(new URL('docs/quote-lens/engine.js', root));
const E = await import('data:text/javascript;base64,' + engine.toString('base64'));
const oracle = JSON.parse(await readFile(new URL('skills/quote-evidence-check/fixtures/oracle-cases.json', root), 'utf8'));
function confirmedPair() {
  return ['A', 'B'].map((side) => {
    const q = E.extractQuote(oracle.ownInputSyntheticCase['raw' + side]);
    for (const item of [...Object.values(q.fields), ...Object.values(q.conditions)]) {
      if (item.value !== null) item.status = 'confirmed';
    }
    return q;
  });
}

test('invalid or unsupported expressions keep audit and cannot yield a suffix amount', () => {
  for (const value of ['1e309元', '500—800元', '500元—800元', '- 100元',
    '+100元', '.5元', 'abc5000元', '5000.111元', '1,00元', '5000']) {
    const f = E.extractQuote('保险：' + value).fields.insurance;
    assert.equal(f.value, null, value);
    assert.equal(f.status, 'unknown', value);
    assert.ok(f.amounts.some((a) => a.valid === false), value);
  }
});

test('adjacent fee labels and gift labels preserve ownership', () => {
  const q = E.extractQuote('服务费：待确认，其他费用：0元；保险：5000元 上牌：500元；赠送保险价值2000元');
  assert.equal(q.fields.service.value, null);
  assert.equal(q.fields.other.value, 0);
  assert.equal(q.fields.insurance.value, 500000);
  assert.equal(q.fields.plate.value, 50000);
  assert.deepEqual(q.fields.insurance.candidates.map((c) => c.cents), [500000]);
});

test('confirmed status cannot admit NaN, infinity, fractional, unsafe, negative or null cents', () => {
  for (const value of [NaN, Infinity, -1, 1.5, Number.MAX_SAFE_INTEGER, null, undefined, true, '100']) {
    const [a, b] = confirmedPair();
    Object.assign(b.fields.service, { value, status: 'confirmed', source: 'manual', note: '合成用户补充' });
    const cmp = E.compareQuotes(a, b);
    assert.notEqual(cmp.status, 'comparable', String(value));
    assert.equal(cmp.diff, null, String(value));
    assert.equal(cmp.totals.b.completeTotalCents, null, String(value));
    assert.ok(Number.isSafeInteger(cmp.totals.b.knownSubtotalCents));
  }
});

test('manual amount or condition without note/evidence cannot unlock comparison', () => {
  for (const [kind, key] of [['fields', 'service'], ['conditions', 'model']]) {
    const [a, b] = confirmedPair();
    Object.assign(b[kind][key], { source: 'manual', note: '', evidence: [], status: 'confirmed' });
    assert.equal(E.compareQuotes(a, b).diff, null, kind);
    b[kind][key].note = '公开合成用户补充，经逐项核对';
    assert.equal(E.compareQuotes(a, b).status, 'comparable', kind);
  }
});

test('only trim condition values; internal whitespace remains significant', () => {
  const [a, b] = confirmedPair();
  Object.assign(a.conditions.model, { value: 'AB C', source: 'manual', note: '合成配置 A' });
  Object.assign(b.conditions.model, { value: 'A BC', source: 'manual', note: '合成配置 B' });
  assert.equal(E.compareQuotes(a, b).status, 'condition-mismatch');
  b.conditions.model.value = '  AB C  ';
  assert.equal(E.compareQuotes(a, b).status, 'comparable');
  const q = E.extractQuote('车型/配置：合成云杉 2026 标准款');
  assert.equal(q.conditions.model.value, '合成云杉 2026 标准款');
});

test('default export excludes all free-text channels; full export keeps literal source', () => {
  const marker = 'PRIVATE-CANARY-ALL-CHANNELS';
  const [a, b] = confirmedPair();
  for (const quote of [a, b]) {
    quote.raw += '\n' + marker;
    quote.issues.push(marker);
    for (const item of Object.values(quote.fields)) {
      item.note = marker;
      item.evidence.forEach((e) => e.line += marker);
      item.amounts.forEach((amount) => { amount.error = marker; amount.token = marker; });
      item.candidates.forEach((candidate) => { candidate.lineIndex = marker; });
    }
    for (const item of Object.values(quote.conditions)) {
      item.value += marker;
      item.candidates = [item.value];
      item.note = marker;
      item.evidence.forEach((e) => e.line += marker);
    }
    quote.declaredTotals.push({ cents: 100, lineIndex: marker });
  }
  const report = E.makeReport(a, b, E.compareQuotes(a, b));
  assert.ok(!report.json.includes(marker));
  assert.ok(!report.markdown.includes(marker));
  const data = JSON.parse(report.json);
  assert.ok(!Object.hasOwn(data.conditionResults[0], 'detail'));
  assert.ok(!Object.hasOwn(data.conditionResults[0].a, 'value'));
  assert.ok(!Object.hasOwn(data.quotes.a.conditions.model, 'value'));
  assert.ok(!Object.hasOwn(data.quotes.a.fields.carPrice, 'note'));
  assert.ok(data.quotes.a.fields.carPrice.evidence.every((e) => !Object.hasOwn(e, 'line')));
  const source = '原文\n```\n<img src=x onerror=alert(1)>\n````\n结束';
  a.raw = source;
  a.fields.carPrice.note = source;
  const full = E.makeReport(a, b, E.compareQuotes(a, b), { includeOriginal: true });
  assert.ok(full.json.includes(marker));
  assert.equal(JSON.parse(full.json).quotes.a.raw, source);
  assert.ok(full.markdown.includes('`````text\n' + source + '\n`````'));
});

test('export recomputes current comparison rather than trusting a prior complete result', () => {
  const [a, b] = confirmedPair();
  const old = E.compareQuotes(a, b);
  assert.equal(old.status, 'comparable');
  b.fields.service.value = null;
  const report = JSON.parse(E.makeReport(a, b, old).json);
  assert.notEqual(report.status, 'comparable');
  assert.equal(report.diff, null);
});
