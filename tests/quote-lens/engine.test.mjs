import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

// Expectations come from the separately authored oracle, not application samples.
const root = new URL('../../', import.meta.url);
const engineUrl = new URL('docs/quote-lens/engine.js', root);
const bytes = await readFile(engineUrl);
const engineSha256 = createHash('sha256').update(bytes).digest('hex');
const E = await import('data:text/javascript;base64,' + bytes.toString('base64'));
const sampleBytes = await readFile(new URL('docs/quote-lens/samples.js', root));
const { SAMPLES } = await import('data:text/javascript;base64,' + sampleBytes.toString('base64'));
const samplesSha256 = createHash('sha256').update(sampleBytes).digest('hex');
const oracle = JSON.parse(await readFile(new URL('skills/quote-evidence-check/fixtures/oracle-cases.json', root), 'utf8'));
const mapping = {
  vehicle: 'carPrice', quoteTax: 'tax', insurance: 'insurance', registration: 'plate',
  service: 'service', mandatoryExtras: 'forcedExtras', other: 'other',
};
const cases = oracle.publicSyntheticCases;
console.log(JSON.stringify({ engine: fileURLToPath(engineUrl), engineSha256, samplesSha256,
  oracle: fileURLToPath(new URL('skills/quote-evidence-check/fixtures/oracle-cases.json', root)), execution: 'maintainer-independent-node-behavior-tests' }));

// The engine deliberately accepts confirmation state from its UI. These helpers
// model explicit user confirmation; extraction is always tested before them.
function confirmAvailable(q) {
  for (const f of Object.values(q.fields)) if (f.value !== null) f.status = 'confirmed';
  for (const c of Object.values(q.conditions)) if (c.value !== null) c.status = 'confirmed';
  return q;
}
function manual(q, key, cents) {
  Object.assign(q.fields[key], { value: cents, status: cents === null ? 'unknown' : 'confirmed',
    source: 'manual', note: '独立验收：用户补充', evidence: [] });
}
function assertAll(checks) {
  const errors = [];
  for (const [label, fn] of checks) try { fn(); } catch (e) { errors.push(label + ': ' + e.message); }
  assert.equal(errors.length, 0, errors.join('\n'));
}

test('01 money is integer cents, zero is valid, malformed values are rejected', () => {
  assertAll([
    ...[['0.00', 0], ['88888.88', 8888888], ['8000.02元', 800002],
      ['3,999.11元', 399911], ['10万元', 10000000]].map(([s, cents]) => [s, () => {
        assert.deepEqual(E.parseMoney(s), { ok: true, cents });
        assert.ok(Number.isSafeInteger(E.parseMoney(s).cents));
      }]),
    ...['', '-100', 'NaN', 'Infinity', '1e309', '3999.111', '500—800',
      '99,999,999,999,999.99'].map(s => [s, () => assert.equal(E.parseMoney(s).ok, false)]),
  ]);
});

test('02 independent oracle and public samples retain exact candidates, conditions and declared arithmetic', () => {
  const checks = [];
  for (const c of [...cases, oracle.ownInputSyntheticCase]) for (const side of ['A', 'B']) {
    const q = E.extractQuote(c['raw' + side]);
    for (const [okey, ekey] of Object.entries(mapping)) checks.push([c.id + side + '.' + okey, () => {
      assert.equal(q.fields[ekey].value, c.amountsCents[side][okey]);
      assert.equal(q.fields[ekey].status, c.amountsCents[side][okey] === null ? 'unknown' : 'unconfirmed');
    }]);
    for (const key of ['model', 'payment', 'scope']) checks.push([c.id + side + '.' + key, () => {
      assert.equal(q.conditions[key].value, c.conditions[side][key]);
      assert.equal(q.conditions[key].status, 'unconfirmed');
    }]);
    checks.push([c.id + side + ' raw', () => assert.equal(q.raw, c['raw' + side])]);
  }
  // Separately hand-summed public application samples. The source's declared
  // subtotal must equal its own seven listed fee values, never a copied claim.
  const sampleExpected = {
    'sample-1': { A: [13200000,1180000,450000,50000,0,0,0],
      B: [12900000,1150000,480000,50000,null,480000,0] },
    'sample-2': { A: [13200000,1180000,450000,50000,0,0,0],
      B: [12800000,1150000,480000,50000,100000,0,0] },
    'sample-3': { A: [13200000,1180000,450000,50000,0,0,0],
      B: [13200000,1180000,450000,50000,null,0,0] },
  };
  assert.deepEqual(SAMPLES.map(s => s.id).sort(), Object.keys(sampleExpected).sort());
  for (const sample of SAMPLES) for (const side of ['A', 'B']) {
    const raw = sample['text' + side], expected = sampleExpected[sample.id][side];
    const q = E.extractQuote(raw);
    const expectedSum = expected.reduce((s, n) => s + (n ?? 0), 0);
    const declaration = /^(?:合计|已知小计)\s*[：:]\s*(\d+)(?:\.([0-9]{1,2}))?元\s*$/m.exec(raw);
    checks.push([sample.id + side + ' independent declared arithmetic', () => {
      assert.ok(declaration, 'a clearly labeled synthetic sum must be present');
      const declared = Number(declaration[1]) * 100 + Number((declaration[2] ?? '').padEnd(2, '0'));
      assert.equal(declared, expectedSum, 'declared sum must match independent fee sum');
    }]);
    checks.push([sample.id + side + ' extracted fees', () => {
      assert.deepEqual(E.FEE_KEYS.map(k => q.fields[k].value), expected);
      assert.equal(E.compareQuotes(q, q).totals.a.knownSubtotalCents, expectedSum);
      assert.deepEqual(q.declaredTotals.map(d => d.cents), [expectedSum]);
    }]);
  }
  assertAll(checks);
});

test('03 missing service never becomes zero; supplement reverses arithmetic only after confirmation', () => {
  const c = cases[0], a = E.extractQuote(c.rawA), b = E.extractQuote(c.rawB);
  let cmp = E.compareQuotes(a, b);
  assert.equal(cmp.diff, null);
  assert.equal(cmp.totals.a.completeTotalCents, null);
  assert.equal(cmp.totals.b.completeTotalCents, null);
  confirmAvailable(a); confirmAvailable(b);
  cmp = E.compareQuotes(a, b);
  assert.equal(b.fields.service.value, null);
  assert.equal(cmp.totals.a.completeTotalCents, 11550000);
  assert.equal(cmp.totals.b.knownSubtotalCents, 11250000);
  assert.equal(cmp.totals.b.completeTotalCents, null);
  assert.equal(cmp.diff, null);
  assert.ok(cmp.questions.some(q => q.includes('服务费')));
  manual(b, 'service', 600000);
  cmp = E.compareQuotes(a, b);
  assert.equal(cmp.status, 'comparable');
  assert.equal(cmp.totals.b.completeTotalCents, 11850000);
  assert.equal(cmp.diff.totalCents, 300000);
  assert.equal(b.raw, c.rawB);
  assert.equal(JSON.parse(E.makeReport(a, b, cmp).json).quotes.b.fields.service.source, 'manual');
});

test('04 explicit zero survives; one-cent delta is exact after missing other fee is confirmed zero', () => {
  const c = cases[2], a = confirmAvailable(E.extractQuote(c.rawA)), b = confirmAvailable(E.extractQuote(c.rawB));
  assert.equal(a.fields.other.value, 0);
  assert.equal(b.fields.other.value, null);
  assert.equal(b.fields.service.value, 0);
  assert.equal(E.compareQuotes(a, b).diff, null);
  manual(b, 'other', 0);
  const cmp = E.compareQuotes(a, b);
  assert.equal(cmp.totals.a.completeTotalCents, 10138800);
  assert.equal(cmp.totals.b.completeTotalCents, 10138801);
  assert.equal(cmp.diff.totalCents, 1);
  assert.equal(E.formatCents(cmp.diff.totalCents), '0.01元');
  const report = JSON.parse(E.makeReport(a, b, cmp).json);
  assert.equal(report.quotes.b.fields.service.valueCents, 0);
  assert.equal(report.quotes.b.fields.forcedExtras.valueCents, 0);
  assert.equal(report.quotes.b.fields.other.valueCents, 0);
  assert.equal(report.diff.totalCents, 1);
});

test('05 own input manual amount change and clearing a zero revoke comparison immediately', () => {
  const c = oracle.ownInputSyntheticCase;
  const a = confirmAvailable(E.extractQuote(c.rawA)), b = confirmAvailable(E.extractQuote(c.rawB));
  let cmp = E.compareQuotes(a, b);
  assert.equal(cmp.totals.a.completeTotalCents, 14857052);
  assert.equal(cmp.totals.b.completeTotalCents, 14869712);
  assert.equal(cmp.diff.totalCents, 12660);
  manual(b, 'plate', 45000);
  cmp = E.compareQuotes(a, b);
  assert.equal(cmp.totals.b.completeTotalCents, 14879712);
  assert.equal(cmp.diff.totalCents, 22660);
  manual(b, 'service', null);
  cmp = E.compareQuotes(a, b);
  assert.equal(cmp.totals.b.knownSubtotalCents, 14879712);
  assert.equal(cmp.totals.b.completeTotalCents, null);
  assert.equal(cmp.diff, null);
});

test('06 fees on the same line never borrow another fee amount or gift value', () => {
  assertAll([
    ['unknown beside zero', () => {
      const q = E.extractQuote('服务费：待确认；其他费用：0元');
      assert.equal(q.fields.service.value, null);
      assert.equal(q.fields.service.status, 'unknown');
      assert.equal(q.fields.other.value, 0);
    }],
    ['two distinct labeled fees', () => {
      const q = E.extractQuote('保险：5000元；上牌：500元');
      for (const [key, allowed] of [['insurance', 500000], ['plate', 50000]]) {
        assert.ok(q.fields[key].value === null || q.fields[key].value === allowed);
        assert.ok(q.fields[key].candidates.every(c => c.cents === allowed));
      }
    }],
    ['gift is not payable insurance', () => {
      const f = E.extractQuote('保险：5000元；赠送保养价值2000元').fields.insurance;
      assert.ok(f.value === null || f.value === 500000);
      assert.ok(f.candidates.every(c => c.cents === 500000));
    }],
  ]);
});

test('07 conflicting, range, exponent, negative and excess decimal raw amounts are never guessed', () => {
  assertAll([
    ...['保险：5000元或5500元，待定', '保险：-100元', '保险：3999.111元',
      '保险：NaN元', '保险：Infinity元', '保险：1e309元',
      '保险：500—800元', '保险：500-800元', '保险：1,00元']
      .map(raw => [raw, () => {
        const f = E.extractQuote(raw).fields.insurance;
        assert.equal(f.value, null);
        assert.equal(f.status, 'unknown');
      }]),
    ['conflicting same field retained', () => {
      const f = E.extractQuote('裸车价：100000元；裸车价：95000元，二选一待确认').fields.carPrice;
      assert.equal(f.value, null);
      assert.deepEqual(f.candidates.map(c => c.cents).sort((a,b) => a-b), [9500000, 10000000]);
    }],
  ]);
});

test('08 confirmed model, payment or scope mismatch independently blocks a complete amount comparison', () => {
  const c = oracle.ownInputSyntheticCase;
  for (const [key, value] of [['model', '合成云杉 旗舰款'], ['payment', '贷款24期'], ['scope', '上牌另计']]) {
    const a = confirmAvailable(E.extractQuote(c.rawA)), b = confirmAvailable(E.extractQuote(c.rawB));
    Object.assign(b.conditions[key], { value, status: 'confirmed', source: 'manual' });
    const cmp = E.compareQuotes(a, b);
    assert.equal(cmp.status, 'condition-mismatch', key);
    assert.equal(cmp.diff, null, key);
    assert.ok(cmp.conditionResults.some(r => r.key === key && r.status === 'mismatch'), key);
  }
  const a = confirmAvailable(E.extractQuote(cases[1].rawA));
  const b = confirmAvailable(E.extractQuote(cases[1].rawB));
  assert.equal(E.compareQuotes(a, b).diff, null);
});

test('09 exact raw and source line survive; source edit starts unconfirmed and cannot keep an old result', () => {
  const raw = '  服务费：6000元（<b>普通文本</b>）  \n其他费用：0元';
  const first = E.extractQuote(raw);
  assert.equal(first.raw, raw);
  assert.equal(first.fields.service.source, 'extract');
  assert.equal(first.fields.service.evidence[0].line, raw.split('\n')[0]);
  assert.equal(first.fields.service.evidence[0].lineIndex, 0);
  first.fields.service.status = 'confirmed';
  const changed = E.extractQuote(raw.replace('6000', '8000'));
  assert.equal(changed.fields.service.value, 800000);
  assert.equal(changed.fields.service.status, 'unconfirmed');
  assert.equal(first.fields.service.value, 600000);
  const empty = E.extractQuote('');
  assert.ok(Object.values(empty.fields).every(f => f.value === null && f.status === 'unknown'));
  assert.ok(Object.values(empty.conditions).every(c => c.value === null && c.status === 'unknown'));
});

test('10 makeReport omits original source text by default, including evidence lines and errors', () => {
  const marker = 'PRIVATE-RAW-SENTINEL-731';
  const a = E.extractQuote('保险：3999.111元（' + marker + '）');
  const b = E.extractQuote('保险：0元');
  const cmp = E.compareQuotes(a, b);
  const safe = E.makeReport(a, b, cmp, { generatedAt: '2026-10-23T00:00:00Z' });
  assertAll([
    ['default Markdown', () => assert.ok(!safe.markdown.includes(marker))],
    ['default JSON', () => assert.ok(!safe.json.includes(marker))],
    ['raw key absent', () => assert.ok(!Object.hasOwn(JSON.parse(safe.json).quotes.a, 'raw'))],
    ['explicit full export', () => {
      const full = E.makeReport(a, b, cmp, { includeOriginal: true, generatedAt: '2026-10-23T00:00:00Z' });
      assert.equal(JSON.parse(full.json).quotes.a.raw, a.raw);
      assert.ok(full.markdown.includes(marker));
    }],
  ]);
});
