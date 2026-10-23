import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../../', import.meta.url);
const engine = await readFile(new URL('docs/quote-lens/engine.js', root));
const E = await import('data:text/javascript;base64,' + engine.toString('base64'));
const samples = await readFile(new URL('docs/quote-lens/samples.js', root));
const { SAMPLES } = await import('data:text/javascript;base64,' + samples.toString('base64'));

test('original known subtotal stays a subtotal after supplement; an actual total mismatch still warns', () => {
  const sample = SAMPLES.find((s) => s.id === 'sample-1');
  function pair(rawB) {
    const [a, b] = [sample.textA, rawB].map((raw) => {
      const q = E.extractQuote(raw);
      for (const item of [...Object.values(q.fields), ...Object.values(q.conditions)]) {
        if (item.value !== null) item.status = 'confirmed';
      }
      return q;
    });
    Object.assign(b.fields.service, { value: 120000, status: 'confirmed', source: 'manual',
      note: '公开合成补充回复：服务费 1200 元', evidence: [] });
    return [a, b];
  }
  const [a, b] = pair(sample.textB);
  const cmp = E.compareQuotes(a, b);
  assert.equal(cmp.status, 'comparable');
  assert.equal(cmp.totals.b.completeTotalCents, 15180000);
  assert.equal(cmp.totals.b.declaredTotalCents, 15060000);
  assert.match(cmp.totals.b.declaredNote, /小计.*150,600元/);
  assert.match(cmp.totals.b.declaredNote, /不是完整总额/);
  assert.ok(!cmp.totals.b.declaredNote.includes('不一致，请复核'));
  assert.ok(!E.makeReport(a, b, cmp).markdown.includes('不一致，请复核'));

  const [totalA, totalB] = pair(sample.textB.replace('已知小计：150600元', '合计：150600元'));
  const totalCmp = E.compareQuotes(totalA, totalB);
  assert.equal(totalCmp.totals.b.completeTotalCents, 15180000);
  assert.match(totalCmp.totals.b.declaredNote, /不一致，请复核/);
});
