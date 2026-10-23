import { FEE_KEYS, FEE_LABELS, CONDITION_KEYS, CONDITION_LABELS, parseMoney, extractQuote, compareQuotes, makeReport, formatCents } from './engine.js';
import { SAMPLES, getSample } from './samples.js';

const $ = (id) => document.getElementById(id);
const DRAFT_KEY = 'quote-lens-draft-v1';
const state = { a: null, b: null, comparison: null, sample: null, ready: false };
let feedbackTimer;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function notify(message) {
  const feedback = $('feedback');
  feedback.textContent = message;
  feedback.classList.add('visible');
  clearTimeout(feedbackTimer);
  feedbackTimer = setTimeout(() => feedback.classList.remove('visible'), 6500);
}

function moneyInput(cents) { return cents === null ? '' : (cents / 100).toFixed(cents % 100 ? 2 : 0); }
function validCondition(value) { return typeof value === 'string' && value.trim().length > 0 && !/(未知|未说明|待定|不详|未提供|未报价|不确定|未明确|尚未|未提及)/.test(value); }
function isValid(field, kind) { return kind === 'fee' ? Number.isSafeInteger(field.value) && field.value >= 0 : validCondition(field.value); }
function canConfirm(field, kind) { return isValid(field, kind) && (field.source !== 'manual' || Boolean(field._manualSource?.trim())); }
function ensureInput(field, kind) {
  if (field._input === undefined) field._input = kind === 'fee' ? moneyInput(field.value) : (field.value ?? '');
}

function clearEvidence() {
  for (const side of ['a', 'b']) {
    const box = $(`evidence-${side}`);
    box.classList.remove('active');
    box.replaceChildren(el('span', 'evidence-label', '原文定位'), el('p', '', '点击下方金额，即可回到对应原文。'));
  }
}

function showEvidence(side, field) {
  const box = $(`evidence-${side}`);
  box.replaceChildren();
  box.classList.add('active');
  if (field.source === 'manual') {
    box.append(el('span', 'evidence-label', '人工补充，未沿用原文证据'), el('p', '', field._manualSource || '尚未填写补充来源。请在修改区填写来源后确认。'));
  } else if (field.evidence?.length) {
    box.append(el('span', 'evidence-label', `${field.label} · 报价 ${side.toUpperCase()} 原文`));
    for (const item of field.evidence) box.append(el('p', '', `第 ${item.lineIndex + 1} 行：${item.line}`));
    const first = field.evidence[0];
    const raw = $(`raw-${side}`);
    const text = raw.value;
    const lines = text.split(/\r?\n/);
    const start = lines.slice(0, first.lineIndex).reduce((sum, line) => sum + line.length + 1, 0);
    raw.setSelectionRange(start, start + (lines[first.lineIndex]?.length ?? 0));
  } else {
    box.append(el('span', 'evidence-label', `${field.label} · 无对应原文`), el('p', '', '原文没有明确的有效值。请取得补充答复，或在修改区录入金额与来源。'));
  }
  box.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  box.focus({ preventScroll: true });
}

function buildEntry(side, key, kind) {
  const field = kind === 'fee' ? state[side].fields[key] : state[side].conditions[key];
  ensureInput(field, kind);
  const cell = el('div', 'entry');
  cell.dataset.side = side;
  cell.dataset.field = key;
  const sideLabel = el('span', 'entry-side', `报价 ${side.toUpperCase()}`);
  const amount = el('button', 'amount-link');
  amount.type = 'button';
  amount.addEventListener('click', () => showEvidence(side, field));
  const tools = el('div', 'entry-tools');
  const status = el('span', 'entry-status');
  const confirm = el('button', 'confirm-button');
  confirm.type = 'button';
  const edit = el('button', 'text-button', '修改');
  edit.type = 'button';
  const note = el('p', 'entry-note');
  const editBox = el('div', 'edit-box');
  editBox.hidden = true;
  const inputId = `input-${side}-${key}`;
  const inputLabel = el('label', '', `${side.toUpperCase()} ${field.label}${kind === 'fee' ? '（元或万元）' : ''}`);
  inputLabel.htmlFor = inputId;
  const input = el('input');
  input.id = inputId;
  input.type = 'text';
  input.autocomplete = 'off';
  input.value = field._input;
  if (kind === 'fee') input.inputMode = 'decimal';
  input.placeholder = kind === 'fee' ? '未报价留空；明确免费填 0' : '填写明确条件';
  const sourceWrap = el('div');
  sourceWrap.hidden = field.source !== 'manual';
  const sourceId = `source-${side}-${key}`;
  const sourceLabel = el('label', 'source-label', '补充来源（必填）');
  sourceLabel.htmlFor = sourceId;
  const source = el('input');
  source.id = sourceId;
  source.type = 'text';
  source.autocomplete = 'off';
  source.value = field._manualSource || '';
  source.placeholder = '例如：销售 10 月 23 日补充回复';
  sourceWrap.append(sourceLabel, source);
  const error = el('p', 'entry-error');
  error.id = `error-${side}-${key}`;
  input.setAttribute('aria-describedby', error.id);
  const hint = el('p', 'edit-hint', '手工修改单独标记来源；不会沿用原文作为金额证据。');
  editBox.append(inputLabel, input, sourceWrap, error, hint);
  tools.append(status, confirm, edit);
  cell.append(sideLabel, amount, tools, note, editBox);

  function refresh() {
    const valid = isValid(field, kind);
    cell.classList.toggle('unknown', !valid);
    amount.textContent = kind === 'fee' ? formatCents(field.value) : (field.value || '未明确');
    amount.setAttribute('aria-label', `${side.toUpperCase()} ${field.label}：${amount.textContent}。查看来源`);
    const confirmed = field.status === 'confirmed';
    status.className = `entry-status ${confirmed ? 'confirmed' : !valid ? 'missing' : ''}`;
    status.textContent = confirmed ? (field.source === 'manual' ? '已确认 · 人工补充' : '已确认 · 原文') : !valid ? '未知 / 待补齐' : field.source === 'manual' ? '人工补充 · 待确认' : '候选 · 待确认';
    confirm.textContent = confirmed ? '撤回确认' : '确认';
    confirm.setAttribute('aria-pressed', String(confirmed));
    confirm.setAttribute('aria-label', `${confirmed ? '撤回确认' : '确认'}报价 ${side.toUpperCase()} 的${field.label}`);
    confirm.disabled = !canConfirm(field, kind);
    sourceWrap.hidden = field.source !== 'manual';
    note.textContent = field.source === 'manual' ? (field._manualSource ? `补充来源：${field._manualSource}` : '填写补充来源后才能确认。') : field.note;
    note.classList.toggle('warning', !valid);
    if (field._error) error.textContent = field._error;
    else if (field.source === 'manual' && !field._manualSource?.trim() && valid) error.textContent = '请填写补充来源，再确认此项。';
    else error.textContent = '';
    input.setAttribute('aria-invalid', String(Boolean(field._error)));
  }

  edit.addEventListener('click', () => {
    editBox.hidden = !editBox.hidden;
    edit.textContent = editBox.hidden ? '修改' : '收起';
    edit.setAttribute('aria-expanded', String(!editBox.hidden));
    if (!editBox.hidden) input.focus();
  });
  input.addEventListener('input', () => {
    field._input = input.value;
    field.source = 'manual';
    field.evidence = [];
    field.candidates = [];
    if (kind === 'fee') {
      field.amounts = [];
      const parsed = parseMoney(input.value);
      field.value = parsed.ok ? parsed.cents : null;
      field._error = input.value.trim() && !parsed.ok ? parsed.error : '';
    } else {
      field.value = input.value.trim() || null;
      field._error = field.value && !validCondition(field.value) ? '条件仍不明确，请先取得明确答复。' : '';
    }
    field.status = isValid(field, kind) ? 'unconfirmed' : 'unknown';
    field.note = field._manualSource ? `人工补充来源：${field._manualSource}` : '人工补充，待填写来源';
    refresh();
    renderResult();
  });
  source.addEventListener('input', () => {
    field._manualSource = source.value;
    field.note = source.value.trim() ? `人工补充来源：${source.value.trim()}` : '人工补充，待填写来源';
    field.status = isValid(field, kind) ? 'unconfirmed' : 'unknown';
    refresh();
    renderResult();
  });
  confirm.addEventListener('click', () => {
    if (!canConfirm(field, kind)) return;
    field.status = field.status === 'confirmed' ? 'unconfirmed' : 'confirmed';
    refresh();
    renderResult();
  });
  refresh();
  return cell;
}

function buildRows(keys, labels, kind, target) {
  const fragment = document.createDocumentFragment();
  for (const key of keys) {
    const row = el('div', `review-row ${kind === 'condition' ? 'condition-row' : 'fee-row'}`);
    row.id = `row-${key}`;
    const label = el('div', 'row-label');
    label.append(el('span', '', labels[key]));
    if (kind === 'fee') label.append(el('span', 'zero-note', key === 'tax' ? '按报价录入，不推算政策' : key === 'service' ? '未报价 ≠ 0 元' : ''));
    row.append(label, buildEntry('a', key, kind), buildEntry('b', key, kind));
    fragment.append(row);
  }
  $(target).replaceChildren(fragment);
}

function renderRows() {
  if (!state.ready) {
    $('condition-rows').replaceChildren(el('p', 'empty-review', '原文已变化。请点击「提取并核对」，重新核对全部条件。'));
    $('fee-rows').replaceChildren(el('p', 'empty-review', '旧确认已失效，不再沿用旧金额。'));
    $('supplement-box').hidden = true;
    return;
  }
  buildRows(CONDITION_KEYS, CONDITION_LABELS, 'condition', 'condition-rows');
  buildRows(FEE_KEYS, FEE_LABELS, 'fee', 'fee-rows');
  $('supplement-box').hidden = !state.sample?.supplement;
  $('supplement-text').textContent = state.sample?.supplement || '';
}

function totalBlock(side, total) {
  const block = el('div', 'total-block');
  const full = total.completeTotalCents !== null;
  block.append(el('div', 'total-header', `报价 ${side} · ${full ? '完整录入合计' : '已知小计'}`));
  block.append(el('p', 'total-money', formatCents(full ? total.completeTotalCents : total.knownSubtotalCents)));
  block.append(el('p', `total-caption ${full ? 'has-total' : ''}`, full ? '7 项费用均已确认；条件仍需另行核对。' : `${total.knownCount} / 7 项有有效金额，包含尚未确认候选。完整合计：暂不提供。`));
  block.append(el('p', 'declared-note', total.declaredNote));
  return block;
}

function renderResult() {
  const ready = state.ready;
  for (const id of ['export-md', 'export-json', 'copy-questions']) $(id).disabled = !ready;
  if (!ready) {
    state.comparison = null;
    $('result-badge').className = 'status-badge pending';
    $('result-badge').textContent = '待重新提取';
    $('result-verdict').textContent = '原文已更新，请重新核对。';
    $('result-explanation').textContent = '旧确认和旧比较结论已失效。点击「提取并核对」取得新的候选值。';
    $('totals').replaceChildren();
    $('blockers').replaceChildren();
    $('blockers-details').hidden = true;
    $('diff-section').hidden = true;
    $('questions').replaceChildren(el('li', '', '请先提取当前两份原文，再生成追问清单。'));
    return;
  }
  const cmp = compareQuotes(state.a, state.b);
  state.comparison = cmp;
  $('result-badge').className = `status-badge ${cmp.status}`;
  $('result-badge').textContent = cmp.statusLabel;
  let verdict;
  let explanation;
  if (cmp.status === 'comparable' && cmp.diff) {
    const diff = cmp.diff.totalCents;
    verdict = diff === 0 ? '录入范围内，两份报价合计相同。' : `录入范围内，B 比 A ${diff > 0 ? '高' : '低'} ${formatCents(Math.abs(diff))}。`;
    explanation = '两侧 7 项费用与 3 项条件均已确认，条件一致。下方展示逐项差额；范围以实际录入为准。';
  } else if (cmp.status === 'condition-mismatch') {
    verdict = '条件不同，先别比较谁便宜。';
    explanation = '车型、付款方式或费用范围尚未一致。请取得同条件报价，不把未知成本自行折算。';
  } else if (cmp.status === 'missing') {
    const names = cmp.missing.map((item) => `${item.sides.join('/')} 的${item.label}`).join('、');
    verdict = '还有费用没报，完整比较先等等。';
    explanation = `${names}尚未明确。已知小计可以核对，未知金额不能填成零。`;
  } else {
    verdict = '数字已经摊开，逐项确认再比较。';
    explanation = '候选来自关键词匹配，仍可能有歧义。请点击金额检查原文，再确认两侧费用和条件。';
  }
  $('result-verdict').textContent = verdict;
  $('result-explanation').textContent = explanation;
  $('totals').replaceChildren(totalBlock('A', cmp.totals.a), totalBlock('B', cmp.totals.b));
  $('blockers-details').hidden = cmp.blockers.length === 0;
  $('blockers-summary').textContent = `${cmp.blockers.length} 项待核对事项`;
  $('blockers').replaceChildren(...cmp.blockers.map((text) => el('li', '', text)));
  $('diff-section').hidden = !cmp.diff;
  if (cmp.diff) {
    $('diff-items').replaceChildren(...cmp.diff.items.map((item) => {
      const row = el('div', 'diff-item');
      row.append(el('span', '', item.label), el('span', `diff-money ${item.deltaCents > 0 ? 'positive' : ''}`, `${item.deltaCents > 0 ? '+' : ''}${formatCents(item.deltaCents)}`));
      return row;
    }));
  }
  const questions = cmp.questions.length ? cmp.questions : ['两份报价是否还存在本清单之外的必付项目、费用有效期或其他附带条件？请对方书面确认。'];
  $('questions').replaceChildren(...questions.map((text) => el('li', '', text)));
}

function extractCurrent(message = true) {
  state.a = extractQuote($('raw-a').value);
  state.b = extractQuote($('raw-b').value);
  state.ready = true;
  for (const side of ['a', 'b']) {
    $(`source-${side}-state`).textContent = '候选已提取，尚需确认';
    $(`source-${side}-state`).classList.remove('dirty');
  }
  $('input-hint').textContent = '候选已重新提取。请按原文逐项确认；未报价保留为未知。';
  clearEvidence();
  renderRows();
  renderResult();
  if (message) notify('已提取当前原文，全部确认状态重新开始。');
}

function loadSample(id, message = true) {
  const sample = getSample(id);
  if (!sample) return;
  state.sample = sample;
  $('sample-select').value = sample.id;
  $('sample-label').textContent = `公开合成案例，非真实车价或税费政策。${sample.preset}`;
  $('raw-a').value = sample.textA;
  $('raw-b').value = sample.textB;
  $('include-original').checked = false;
  $('copy-fallback').hidden = true;
  extractCurrent(false);
  if (message) notify('已载入合成案例。请逐项核对，所有值仍需确认。');
}

function previewSample() {
  loadSample($('sample-select').value, false);
  for (const side of ['a', 'b']) {
    for (const [group, keys, kind] of [['fields', FEE_KEYS, 'fee'], ['conditions', CONDITION_KEYS, 'condition']]) {
      for (const key of keys) {
        const field = state[side][group][key];
        if (field.source === 'extract' && field.candidates.length === 1 && field.evidence.length && isValid(field, kind)) field.status = 'confirmed';
      }
    }
  }
  $('sample-label').textContent = '当前为公开合成案例的预设核对演示：有唯一原文候选的费用和条件已预设确认，真正缺项仍保留。不是独立真人核对；自有输入、原文变化及手工修改均需重新确认。';
  for (const side of ['a', 'b']) $(`source-${side}-state`).textContent = '合成案例 · 预设核对状态';
  renderRows();
  renderResult();
  notify('已载入预设核对演示，缺项仍为未知。可以补录合成回复后确认，查看复算。');
}

function markRawChanged() {
  state.ready = false;
  state.a = null;
  state.b = null;
  state.sample = null;
  $('include-original').checked = false;
  $('sample-label').textContent = '当前为自有输入；旧确认已失效。建议每项费用单独一行，并注明元或万元。';
  for (const side of ['a', 'b']) {
    $(`source-${side}-state`).textContent = '原文已变化，待重新提取';
    $(`source-${side}-state`).classList.add('dirty');
  }
  $('input-hint').textContent = '输入已变化。点击「提取并核对」，再重新确认；未识别内容不会自动猜测。';
  clearEvidence();
  renderRows();
  renderResult();
}

function applySupplement() {
  if (!state.ready || state.sample?.id !== 'sample-1') return;
  const field = state.b.fields.service;
  field.value = 120000;
  field.source = 'manual';
  field.status = 'unconfirmed';
  field.evidence = [];
  field.candidates = [];
  field.amounts = [];
  field._input = '1200';
  field._manualSource = '公开合成补充回复：B 报价服务费 1200 元（模拟答复，非真实数据）';
  field.note = `人工补充来源：${field._manualSource}`;
  field._error = '';
  renderRows();
  renderResult();
  $('row-service').scrollIntoView({ block: 'center' });
  notify('已补录合成服务费 1,200 元；请确认 B 服务费后再比较。');
}

function downloadReport(type) {
  if (!state.ready || !state.comparison) return;
  try {
    const report = makeReport(state.a, state.b, state.comparison, { includeOriginal: $('include-original').checked });
    const content = type === 'md' ? report.markdown : report.json;
    const blob = new Blob([content], { type: type === 'md' ? 'text/markdown;charset=utf-8' : 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = el('a');
    link.href = url;
    link.download = `报价核对报告-${new Date().toISOString().slice(0, 10)}.${type}`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify(`已生成 ${type === 'md' ? 'Markdown' : 'JSON'} 报告（${$('include-original').checked ? '包含原文，请检查个人信息' : '省略原文与自由文本条件'}）。`);
  } catch {
    notify('报告生成失败。当前输入仍保留，请重试。');
  }
}

async function copyQuestions() {
  if (!state.ready) return;
  const text = [...$('questions').children].map((node, index) => `${index + 1}. ${node.textContent}`).join('\n');
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(text);
    $('copy-fallback').hidden = true;
    notify('追问清单已复制。请检查内容后自行发送。');
  } catch {
    const fallback = $('copy-fallback');
    fallback.hidden = false;
    fallback.value = text;
    fallback.focus();
    fallback.select();
    notify('浏览器未允许自动复制。清单已选中，请手工复制。');
  }
}

function draftPayload() {
  const supplemental = {};
  if (state.ready) {
    for (const side of ['a', 'b']) {
      supplemental[side] = { fields: {}, conditions: {} };
      for (const [group, keys] of [['fields', FEE_KEYS], ['conditions', CONDITION_KEYS]]) {
        for (const key of keys) {
          const field = state[side][group][key];
          if (field.source === 'manual') supplemental[side][group][key] = { input: field._input ?? '', source: field._manualSource ?? '' };
        }
      }
    }
  }
  return { version: 1, savedAt: new Date().toISOString(), rawA: $('raw-a').value, rawB: $('raw-b').value, supplemental };
}

function saveDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draftPayload()));
    notify('草稿已保存到当前浏览器，包含原文与人工补充。');
  } catch {
    notify('无法保存本机草稿，可能是浏览器禁止存储或空间不足。当前页面输入仍保留。');
  }
}

function restoreDraft() {
  try {
    const stored = localStorage.getItem(DRAFT_KEY);
    if (!stored) { notify('这个浏览器还没有保存过草稿。'); return; }
    const draft = JSON.parse(stored);
    if (draft.version !== 1 || typeof draft.rawA !== 'string' || typeof draft.rawB !== 'string') throw new Error('Invalid draft');
    state.sample = null;
    $('raw-a').value = draft.rawA;
    $('raw-b').value = draft.rawB;
    $('sample-label').textContent = '已恢复本机草稿。全部确认状态重新开始，人工补充仍需复核来源。';
    $('include-original').checked = false;
    extractCurrent(false);
    for (const side of ['a', 'b']) {
      for (const [group, keys] of [['fields', FEE_KEYS], ['conditions', CONDITION_KEYS]]) {
        for (const key of keys) {
          const saved = draft.supplemental?.[side]?.[group]?.[key];
          if (!saved || typeof saved.input !== 'string') continue;
          const field = state[side][group][key];
          field._input = saved.input;
          field._manualSource = typeof saved.source === 'string' ? saved.source : '';
          field.source = 'manual';
          field.evidence = [];
          field.candidates = [];
          if (group === 'fields') {
            const parsed = parseMoney(saved.input);
            field.amounts = [];
            field.value = parsed.ok ? parsed.cents : null;
            field._error = saved.input.trim() && !parsed.ok ? parsed.error : '';
          } else field.value = saved.input.trim() || null;
          field.status = isValid(field, group === 'fields' ? 'fee' : 'condition') ? 'unconfirmed' : 'unknown';
          field.note = field._manualSource ? `人工补充来源：${field._manualSource}` : '人工补充，待填写来源';
        }
      }
    }
    renderRows();
    renderResult();
    notify('已恢复原文与补充信息。旧确认未恢复，请重新逐项核对。');
  } catch {
    notify('草稿读取失败或格式不正确。未改写已保存内容。');
  }
}

for (const sample of SAMPLES) {
  const option = el('option', '', sample.name.replace(/^样例[一二三]：/, ''));
  option.value = sample.id;
  $('sample-select').append(option);
}
$('sample-select').addEventListener('change', () => loadSample($('sample-select').value));
$('load-sample').addEventListener('click', () => loadSample($('sample-select').value));
$('preview-sample').addEventListener('click', previewSample);
$('extract').addEventListener('click', () => extractCurrent());
$('own-input').addEventListener('click', () => {
  if (($('raw-a').value || $('raw-b').value) && !state.sample && !confirm('清空当前两份输入，开始新的核对？已保存的本机草稿会保留。')) return;
  $('raw-a').value = '';
  $('raw-b').value = '';
  markRawChanged();
  $('raw-a').focus();
});
for (const side of ['a', 'b']) $(`raw-${side}`).addEventListener('input', markRawChanged);
$('apply-supplement').addEventListener('click', applySupplement);
$('export-md').addEventListener('click', () => downloadReport('md'));
$('export-json').addEventListener('click', () => downloadReport('json'));
$('copy-questions').addEventListener('click', copyQuestions);
$('save-draft').addEventListener('click', saveDraft);
$('restore-draft').addEventListener('click', restoreDraft);
$('clear-draft').addEventListener('click', () => {
  try { localStorage.removeItem(DRAFT_KEY); notify('已清除本机草稿，当前页面输入保留。'); }
  catch { notify('浏览器未允许清除存储。请在浏览器设置中管理本站数据。'); }
});
loadSample(SAMPLES[0].id, false);
