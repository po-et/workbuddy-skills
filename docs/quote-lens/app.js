import { FEE_KEYS, FEE_LABELS, CONDITION_KEYS, CONDITION_LABELS, parseMoney, extractQuote, compareQuotes, makeReport, formatCents } from './engine.js';
import { SAMPLES, getSample } from './samples.js';

const $ = (id) => document.getElementById(id);
const DRAFT_KEY = 'quote-lens-draft-v1';
const SIDES = ['a', 'b'];
const FIELD_GROUPS = [['fields', FEE_KEYS, 'fee'], ['conditions', CONDITION_KEYS, 'condition']];

// state.a / state.b：各侧报价（quote）对象，可能为 null（尚未提取/已清空）。
// state.current.a / b：该侧 quote 是否与当前原文一致；原文一变即 false。
// state.ready（计算属性）：两侧都有 quote 且均为当前内容，才允许比较与导出。
const state = {
  a: null,
  b: null,
  comparison: null,
  sample: null,
  current: { a: false, b: false },
  get ready() { return Boolean(this.a) && Boolean(this.b) && this.current.a && this.current.b; },
};
let feedbackTimer;
// select 当前应显示的样例 id；用户取消载入时用它把下拉框拨回原值。
let selectAnchor = '';
let activeOverwriteDialog = null;

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

// 页面内确认框：弹窗期间其余页面不可交互；取消/Escape/异常关闭均不授权覆盖。
function confirmOverwrite(message) {
  if (activeOverwriteDialog) return Promise.resolve(false);
  return new Promise((resolve) => {
    const previousFocus = document.activeElement;
    const dialog = el('dialog', 'overwrite-dialog');
    const title = el('h2', '', '确认覆盖当前内容？');
    title.id = 'overwrite-dialog-title';
    const description = el('p', 'overwrite-description', message);
    description.id = 'overwrite-dialog-description';
    dialog.setAttribute('aria-labelledby', title.id);
    dialog.setAttribute('aria-describedby', description.id);
    dialog.setAttribute('aria-modal', 'true');
    const actions = el('div', 'overwrite-actions');
    const cancel = el('button', 'button secondary', '取消');
    cancel.type = 'button';
    cancel.autofocus = true;
    const accept = el('button', 'button primary', '确认覆盖');
    accept.type = 'button';
    actions.append(cancel, accept);
    dialog.append(title, description, actions);
    let settled = false;
    function finish(accepted) {
      if (settled) return;
      settled = true;
      if (dialog.open) dialog.close();
      dialog.remove();
      activeOverwriteDialog = null;
      if (previousFocus?.isConnected && typeof previousFocus.focus === 'function') previousFocus.focus({ preventScroll: true });
      resolve(accepted);
    }
    cancel.addEventListener('click', () => finish(false));
    accept.addEventListener('click', () => finish(true));
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); finish(false); });
    dialog.addEventListener('close', () => finish(false));
    activeOverwriteDialog = dialog;
    document.body.append(dialog);
    try {
      dialog.showModal();
      cancel.focus({ preventScroll: true });
    } catch {
      finish(false);
      notify('浏览器无法显示覆盖确认框，已取消操作，当前内容保留。');
    }
  });
}

function moneyInput(cents) { return cents === null ? '' : (cents / 100).toFixed(cents % 100 ? 2 : 0); }
function validCondition(value) { return typeof value === 'string' && value.trim().length > 0 && !/(未知|未说明|待定|不详|未提供|未报价|不确定|未明确|尚未|未提及)/.test(value); }
function isValid(field, kind) { return kind === 'fee' ? Number.isSafeInteger(field.value) && field.value >= 0 : validCondition(field.value); }
function canConfirm(field, kind) { return isValid(field, kind) && (field.source !== 'manual' || Boolean(field._manualSource?.trim())); }
function ensureInput(field, kind) {
  if (field._input === undefined) field._input = kind === 'fee' ? moneyInput(field.value) : (field.value ?? '');
}

function clearEvidence() {
  for (const side of SIDES) {
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
  const restore = el('button', 'text-button', '恢复原文');
  restore.type = 'button';
  restore.setAttribute('aria-label', `按当前原文恢复报价 ${side.toUpperCase()} 的${field.label}候选，不改动其他项`);
  restore.addEventListener('click', () => restoreFieldFromRaw(side, key, kind));
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
  tools.append(status, confirm, edit, restore);
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
    restore.hidden = field.source !== 'manual';
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

// 单项「恢复原文」：只把该字段替换为按“当前原文”重新抽取的候选（未确认），
// 其余字段、确认状态与人工补充一律不动。
function restoreFieldFromRaw(side, key, kind) {
  if (!state[side]) return;
  const fresh = extractQuote($(`raw-${side}`).value);
  const group = kind === 'fee' ? 'fields' : 'conditions';
  const field = state[side][group][key];
  const src = fresh[group][key];
  for (const prop of Object.keys(field)) if (prop.startsWith('_')) delete field[prop];
  for (const prop of Object.keys(src)) field[prop] = src[prop];
  renderRows();
  renderResult();
  notify(`已按当前原文恢复「${field.label}」候选（其余项未动）；请确认后采用。`);
}

function staleEntry(side) {
  const cell = el('div', 'entry unknown');
  cell.append(
    el('span', 'entry-side', `报价 ${side.toUpperCase()}`),
    el('p', 'entry-note warning', '原文已变化或尚未提取。本侧人工补充草稿已保留；点「提取并核对」刷新本侧，另一侧不受影响。'),
  );
  return cell;
}

function entryFor(side, key, kind) {
  if (state[side] && state.current[side]) return buildEntry(side, key, kind);
  return staleEntry(side);
}

function buildRows(keys, labels, kind, target) {
  const fragment = document.createDocumentFragment();
  for (const key of keys) {
    const row = el('div', `review-row ${kind === 'condition' ? 'condition-row' : 'fee-row'}`);
    row.id = `row-${key}`;
    const label = el('div', 'row-label');
    label.append(el('span', '', labels[key]));
    if (kind === 'fee') label.append(el('span', 'zero-note', key === 'tax' ? '按报价录入，不推算政策' : key === 'service' ? '未报价 ≠ 0 元' : ''));
    row.append(label, entryFor('a', key, kind), entryFor('b', key, kind));
    fragment.append(row);
  }
  $(target).replaceChildren(fragment);
}

function renderRows() {
  if (!state.a && !state.b) {
    $('condition-rows').replaceChildren(el('p', 'empty-review', '原文已变化或尚未提取。请点击「提取并核对」，重新核对全部条件。'));
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
  block.append(el('p', `total-caption ${full ? 'has-total' : ''}`, full ? '7 项费用均已确认；是否可比请看核对结果。' : `${total.knownCount} / 7 项有有效金额，包含尚未确认候选。完整合计：暂不提供。`));
  block.append(el('p', 'declared-note', total.declaredNote));
  return block;
}

function renderResult() {
  const ready = state.ready;
  $('review-shortcuts').hidden = !ready;
  $('jump-missing').hidden = true;
  for (const id of ['export-md', 'export-json', 'copy-questions']) $(id).disabled = !ready;
  if (!ready) {
    state.comparison = null;
    $('result-badge').className = 'status-badge pending';
    $('result-badge').textContent = '待重新提取';
    const issues = [];
    for (const side of SIDES) {
      const label = side.toUpperCase();
      if (!state[side]) issues.push(`报价 ${label} 尚未提取`);
      else if (!state.current[side]) issues.push(`报价 ${label} 原文已变化`);
    }
    $('result-verdict').textContent = issues.length ? `${issues.join('；')}，暂不比较。` : '原文已更新，请重新核对。';
    $('result-explanation').textContent = '修改原文只失效本侧确认（人工补充转为待确认草稿保留），另一侧的确认与人工补充不动。两侧都提取为当前内容后，才输出比较结论。';
    $('totals').replaceChildren();
    $('blockers').replaceChildren();
    $('blockers-details').hidden = true;
    $('diff-section').hidden = true;
    $('questions').replaceChildren(el('li', '', '请先把两侧原文都提取为当前内容，再生成追问清单。'));
    return;
  }
  const cmp = compareQuotes(state.a, state.b);
  state.comparison = cmp;
  if (cmp.missing.length > 0) {
    $('jump-missing').href = `#row-${cmp.missing[0].key}`;
    $('jump-missing').hidden = false;
  }
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

// 提取单侧：preserveManual=true 时保留该侧人工补充（降级为待确认草稿），
// 其余字段全部以当前原文的抽取结果为准；false 则整侧全新（载入样例/恢复草稿用）。
function extractSide(side, preserveManual) {
  const fresh = extractQuote($(`raw-${side}`).value);
  const prev = state[side];
  if (prev && preserveManual) {
    for (const [group, keys, kind] of FIELD_GROUPS) {
      for (const key of keys) {
        const old = prev[group][key];
        if (old.source === 'manual') {
          fresh[group][key] = old;
          old.status = isValid(old, kind) ? 'unconfirmed' : 'unknown';
        }
      }
    }
  }
  state[side] = fresh;
  state.current[side] = true;
}

// 提取并核对：默认只刷新“非当前”的一侧（另一侧的确认与人工补充原样保留）；
// force=true 用于样例载入/草稿恢复等程序化替换原文的场景（不触发 input 事件，必须强制重提取）。
function extractCurrent(opts = {}) {
  const message = opts.message !== false;
  const preserveManual = opts.preserveManual !== false;
  const force = opts.force === true;
  const touched = [];
  for (const side of SIDES) {
    if (force || !state[side] || !state.current[side]) {
      extractSide(side, preserveManual);
      touched.push(side);
    }
  }
  for (const side of touched) {
    $(`source-${side}-state`).textContent = '候选已提取，尚需确认';
    $(`source-${side}-state`).classList.remove('dirty');
  }
  if (!touched.length) {
    if (message) notify('两侧均已是当前原文的提取结果，未做改动；确认状态保持不变。');
    return;
  }
  $('input-hint').textContent = '候选已重新提取。请按原文逐项确认；未报价保留为未知。';
  clearEvidence();
  renderRows();
  renderResult();
  if (message) notify(preserveManual ? `已提取${touched.map((s) => `报价 ${s.toUpperCase()}`).join('、')}的当前原文；人工补充保留为待确认草稿，其余确认已重置。` : '已提取当前原文，全部确认状态重新开始。');
}

function loadSample(id, message = true) {
  const sample = getSample(id);
  if (!sample) return;
  state.sample = sample;
  selectAnchor = sample.id;
  $('sample-select').value = sample.id;
  $('sample-label').textContent = `公开合成案例，非真实车价或税费政策。${sample.preset}`;
  $('raw-a').value = sample.textA;
  $('raw-b').value = sample.textB;
  $('include-original').checked = false;
  $('copy-fallback').hidden = true;
  extractCurrent({ message: false, preserveManual: false, force: true });
  if (message) notify('已载入合成案例。请逐项核对，所有值仍需确认。');
}

// 是否存在“自有/已修改”的输入：样例被改动、非样例且有内容，或存在人工补充/手工修改。
// 原文与样例完全一致但字段被手工补充过，同样算数——否则切换样例/演示会静默丢掉补充。
function hasUnsavedInput() {
  for (const side of SIDES) {
    const quote = state[side];
    if (!quote) continue;
    for (const [group, keys] of [['fields', FEE_KEYS], ['conditions', CONDITION_KEYS]]) {
      for (const key of keys) if (quote[group][key].source === 'manual') return true;
    }
  }
  if (state.sample && $('raw-a').value === state.sample.textA && $('raw-b').value === state.sample.textB) return false;
  return $('raw-a').value.trim() !== '' || $('raw-b').value.trim() !== '';
}

async function guardOverwrite(action) {
  if (!hasUnsavedInput()) return true;
  return await confirmOverwrite(`${action}会覆盖当前输入与人工补充；未保存到本机草稿的修改将丢失。是否继续？`);
}

// 所有样例载入入口共用：取消时不改数据，并把下拉框拨回当前锚点。
async function tryLoadSample(id) {
  if (!(await guardOverwrite('载入合成案例'))) {
    $('sample-select').value = selectAnchor;
    return false;
  }
  loadSample(id);
  return true;
}

async function previewSample() {
  if (!(await guardOverwrite('载入合成案例演示'))) {
    $('sample-select').value = selectAnchor;
    return;
  }
  loadSample($('sample-select').value, false);
  for (const side of SIDES) {
    for (const [group, keys, kind] of FIELD_GROUPS) {
      for (const key of keys) {
        const field = state[side][group][key];
        if (field.source === 'extract' && field.candidates.length === 1 && field.evidence.length && isValid(field, kind)) field.status = 'confirmed';
      }
    }
  }
  $('sample-label').textContent = '合成演示：金额与条件按样例预设，真正缺项仍保留。自己的输入、原文变化及手工修改后需重新确认。';
  for (const side of SIDES) $(`source-${side}-state`).textContent = '合成案例 · 预设核对状态';
  renderRows();
  renderResult();
  notify('已载入预设核对演示，缺项仍为未知。可以补录合成回复后确认，查看复算。');
}

// 原文输入事件：只失效被编辑的一侧；另一侧（含确认与人工补充）保持不动。
function markRawChanged(side) {
  state.current[side] = false;
  $(`source-${side}-state`).textContent = '原文已变化，待重新提取';
  $(`source-${side}-state`).classList.add('dirty');
  $('input-hint').textContent = `报价 ${side.toUpperCase()} 原文已变化：本侧待重新提取；另一侧的确认与人工补充保留。`;
  $('sample-label').textContent = state.sample
    ? '原文已修改，与合成案例不同；修改侧待重新提取，另一侧不动。'
    : '当前为自有输入；修改侧确认失效，人工补充转为草稿。建议每项费用单独一行，并注明元或万元。';
  $('include-original').checked = false;
  clearEvidence();
  renderRows();
  renderResult();
}

// 粘贴自己的报价：两侧清空重来（人工草稿一并丢弃）。
function resetAll() {
  state.a = null;
  state.b = null;
  state.current.a = false;
  state.current.b = false;
  state.sample = null;
  $('include-original').checked = false;
  $('sample-label').textContent = '当前为自有输入；旧确认已失效。建议每项费用单独一行，并注明元或万元。';
  for (const side of SIDES) {
    $(`source-${side}-state`).textContent = '原文已变化，待重新提取';
    $(`source-${side}-state`).classList.add('dirty');
  }
  $('input-hint').textContent = '输入已变化。点击「提取并核对」，再重新确认；未识别内容不会自动猜测。';
  clearEvidence();
  renderRows();
  renderResult();
}

const SYNTHETIC_SERVICE_SOURCE = '公开合成补充回复：B 报价服务费 1200 元（模拟答复，非真实数据）';

async function applySupplement() {
  if (!state.b || !state.current.b || state.sample?.id !== 'sample-1') return;
  const field = state.b.fields.service;
  // 已存在不同内容的人工补充时，先确认再覆盖（重复点击同一合成补充不重复询问）。
  const sameSynthetic = field.source === 'manual' && field.value === 120000 && field._manualSource === SYNTHETIC_SERVICE_SOURCE;
  if (field.source === 'manual' && !sameSynthetic
    && !(await confirmOverwrite('B 服务费当前是人工补充；仍要用合成回复的 1,200 元覆盖吗？'))) return;
  field.value = 120000;
  field.source = 'manual';
  field.status = 'unconfirmed';
  field.evidence = [];
  field.candidates = [];
  field.amounts = [];
  field._input = '1200';
  field._manualSource = SYNTHETIC_SERVICE_SOURCE;
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

// 汇总当前两侧的人工补充（仅 source==='manual' 字段）；草稿保存与恢复比对共用。
function collectSupplemental() {
  const supplemental = {};
  for (const side of SIDES) {
    supplemental[side] = { fields: {}, conditions: {} };
    if (!state[side]) continue;
    for (const [group, keys] of [['fields', FEE_KEYS], ['conditions', CONDITION_KEYS]]) {
      for (const key of keys) {
        const field = state[side][group][key];
        if (field.source === 'manual') supplemental[side][group][key] = { input: field._input ?? '', source: field._manualSource ?? '' };
      }
    }
  }
  return supplemental;
}

// 补充集合的稳定签名：按键排序、丢弃非法项后序列化，用于“内容是否有差异”的比对。
function supplementalSignature(sup) {
  const out = {};
  for (const side of SIDES) {
    out[side] = { fields: {}, conditions: {} };
    for (const group of ['fields', 'conditions']) {
      const src = sup?.[side]?.[group] ?? {};
      for (const key of Object.keys(src).sort()) {
        const item = src[key];
        if (item && typeof item.input === 'string') out[side][group][key] = { input: item.input, source: typeof item.source === 'string' ? item.source : '' };
      }
    }
  }
  return JSON.stringify(out);
}

function draftPayload() {
  return { version: 1, savedAt: new Date().toISOString(), rawA: $('raw-a').value, rawB: $('raw-b').value, supplemental: collectSupplemental() };
}

function saveDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draftPayload()));
    notify('草稿已保存到当前浏览器，包含原文与人工补充。');
  } catch {
    notify('无法保存本机草稿，可能是浏览器禁止存储或空间不足。当前页面输入仍保留。');
  }
}

async function restoreDraft() {
  let draft;
  try {
    const stored = localStorage.getItem(DRAFT_KEY);
    if (!stored) { notify('这个浏览器还没有保存过草稿。'); return; }
    draft = JSON.parse(stored);
    if (draft.version !== 1 || typeof draft.rawA !== 'string' || typeof draft.rawB !== 'string') throw new Error('Invalid draft');
  } catch {
    notify('草稿读取失败或格式不正确。未改写已保存内容。');
    return;
  }
  // 原文相同但人工补充不同，同样会覆盖当前补充，必须守卫；取消则当前值原样保留。
  const rawDiffers = $('raw-a').value !== draft.rawA || $('raw-b').value !== draft.rawB;
  const supplementalDiffers = supplementalSignature(collectSupplemental()) !== supplementalSignature(draft.supplemental);
  if (hasUnsavedInput() && (rawDiffers || supplementalDiffers)
    && !(await confirmOverwrite('恢复草稿会覆盖当前的原文或人工补充；未保存的修改将丢失。是否继续？'))) return;
  state.sample = null;
  $('raw-a').value = draft.rawA;
  $('raw-b').value = draft.rawB;
  $('sample-label').textContent = '已恢复本机草稿。全部确认状态重新开始，人工补充仍需复核来源。';
  $('include-original').checked = false;
  extractCurrent({ message: false, preserveManual: false, force: true });
  for (const side of SIDES) {
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
}

for (const sample of SAMPLES) {
  const option = el('option', '', sample.name.replace(/^样例[一二三]：/, ''));
  option.value = sample.id;
  $('sample-select').append(option);
}
$('sample-select').addEventListener('change', async () => { await tryLoadSample($('sample-select').value); });
$('load-sample').addEventListener('click', async () => { await tryLoadSample($('sample-select').value); });
$('preview-sample').addEventListener('click', previewSample);
$('extract').addEventListener('click', () => extractCurrent());
$('own-input').addEventListener('click', async () => {
  if (hasUnsavedInput() && !(await confirmOverwrite('清空当前两份输入，开始新的核对？已保存的本机草稿会保留。'))) return;
  $('raw-a').value = '';
  $('raw-b').value = '';
  resetAll();
  $('raw-a').focus();
});
for (const side of SIDES) $(`raw-${side}`).addEventListener('input', () => markRawChanged(side));
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
