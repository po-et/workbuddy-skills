/**
 * engine.js — 「报价显微镜」纯核对逻辑模块
 *
 * 只依赖标准 JavaScript（ES Module），无 DOM、无网络、无存储，
 * 可在 Node 中独立运行，也可被 UI 层 import。
 *
 * ── 数据形状 ───────────────────────────────────────────────
 * Money：一律用「分」为单位的整数（cents），1 元 = 100 分。
 *   null = 未知 / 未报价（缺失 ≠ 0）；0 = 明确为 0 元（需确认）。
 *
 * FeeExtract = {
 *   key:        'carPrice'|'tax'|'insurance'|'plate'|'service'|'forcedExtras'|'other'
 *   label:      中文名
 *   status:     'unknown' | 'unconfirmed' | 'confirmed'
 *   value:      number | null（分）。status 为 'unknown' 时必为 null
 *   source:     'extract' | 'manual' | null   （extract=来自原文；manual=人工补充/人工标记）
 *   candidates: Array<{ cents:number, lineIndex:number }>  原文中出现的不同金额候选（含来源行号）
 *   amounts:    Array<{ cents:number|null, lineIndex:number, valid:boolean, error?:string }> 审计流水
 *   evidence:   Array<{ line:string, lineIndex:number }>   提及该费用的原文行（保留原文）
 *   note:       string（如「原文明确未报价」「出现多个金额待核对」）
 * }
 *
 * ConditionExtract = {
 *   key:'model'|'payment'|'scope', label, status, value:string|null,
 *   candidates:string[], evidence:Array<{line,lineIndex}>, source, note
 * }
 *
 * Quote = {
 *   raw: string,
 *   lines: string[],
 *   fields: { [feeKey]: FeeExtract },
 *   conditions: { model|payment|scope: ConditionExtract },
 *   declaredTotals: Array<{ cents:number, lineIndex:number }>,  // 原文中的合计/小计（仅交叉核对）
 *   issues: string[]
 * }
 *
 * Comparison = {
 *   status: 'condition-mismatch'|'missing'|'pending'|'comparable',
 *   statusLabel: string,
 *   blockers: string[],
 *   conditionResults: Array<{ key,label,status,detail,a:{value,status},b:{value,status} }>,
 *   missing:    Array<{ key,label,sides:['A'|'B'] }>,
 *   unconfirmed:Array<{ key,label,sides:['A'|'B'] }>,
 *   ambiguous:  Array<{ key,label,sides:['A'|'B'],values:string[] }>,
 *   totals: { a: SideTotals, b: SideTotals },
 *   diff: null | { totalCents:number, items:Array<{key,label,aCents,bCents,deltaCents}> },
 *   questions: string[]
 * }
 *
 * SideTotals = {
 *   knownSubtotalCents:number, knownCount:number,
 *   completeTotalCents:number|null,   // 仅 7 项全部确认后非 null
 *   allConfirmed:boolean,
 *   declaredTotalCents:number|null,   // 原文申报金额；优先单一总额，否则单一小计，类型见 declaredNote
 *   declaredNote:string
 * }
 * ─────────────────────────────────────────────────────────── */

export const ENGINE_VERSION = 2;

export const FEE_KEYS = ['carPrice', 'tax', 'insurance', 'plate', 'service', 'forcedExtras', 'other'];

export const FEE_LABELS = {
  carPrice: '裸车价',
  tax: '报价税费',
  insurance: '保险',
  plate: '上牌',
  service: '服务费',
  forcedExtras: '强制附加项',
  other: '其他费用',
};

export const CONDITION_KEYS = ['model', 'payment', 'scope'];

export const CONDITION_LABELS = {
  model: '车型/配置',
  payment: '付款方式',
  scope: '费用范围',
};

export const STATUS_LABELS = {
  'condition-mismatch': '条件不同',
  missing: '待补齐',
  pending: '待确认',
  comparable: '录入范围可比较',
};

/** 费用别名表。匹配时按「先长后短」顺序查找，避免「裸车价」被「车价」抢先。 */
const FEE_ALIASES = {
  carPrice: ['裸车价', '整车价', '车身价', '裸车', '车价'],
  tax: ['报价税费', '车辆购置税', '购置税', '税费', '增值税'],
  insurance: ['保险费', '交强险', '商业险', '保险', '保费', '车险'],
  plate: ['上牌费', '牌照费', '上户费', '上牌', '牌照', '上户'],
  service: ['服务费', '综合服务费', '出库费', '手续费'],
  forcedExtras: ['强制装潢及附加项', '强制附加项', '强制附加', '强制装潢', '强制购买', '强制捆绑', '装潢费', '精品费', '加装费'],
  other: ['其他费用', '其他杂费', '杂费', '其他'],
};

/** 条件别名表（同样先长后短）。 */
const CONDITION_PATTERNS = {
  model: ['车型 / 配置', '车型/配置', '车型／配置', '车型配置', '车辆型号', '车型', '车款', '配置'],
  payment: ['付款方式', '支付方式', '付款', '支付'],
  scope: ['费用范围', '报价范围', '报价包含', '费用包含', '清单范围'],
};

/** 原文中表示「这项没有报价」的词。出现即视为明确未报价（仍不等于 0）。 */
const UNQUOTED_RE = /未报价|未提供|未列明|未列|未含|不含|待定|待确认|面议/;

/** 原文中的合计/小计行关键词（只用于交叉核对，不参与 7 项费用）。 */
const TOTAL_KEYWORD_RE = /合计|小计|共计|总价|总额/;

/** 金额上限：99,999,999,999.99 元（约 100 亿元）。 */
const MAX_CENTS = 9999999999999;

// ── 金额解析 ────────────────────────────────────────────────

const MONEY_RE = /^(-?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(万[元]?|元)?$/;

/**
 * 解析单个金额文本（支持手工输入）。
 * 支持：132000 / 132000元 / 132,000元 / 13.2万 / 1.2万元 / 0 / 0.00
 * 拒绝：负数、Infinity、NaN、超大金额、小数超过 2 位、格式不明。
 * @returns {{ok:true, cents:number} | {ok:false, error:string}}
 */
export function parseMoney(text) {
  if (typeof text !== 'string') return { ok: false, error: '输入不是文本' };
  const t = text.trim();
  if (!t) return { ok: false, error: '空值' };
  const m = MONEY_RE.exec(t);
  if (!m) return { ok: false, error: '格式无法识别（仅支持 元/万元、千位逗号、至多 2 位小数）' };
  if (m[1] === '-') return { ok: false, error: '不允许负数' };
  const num = Number(m[2].replace(/,/g, '') + (m[3] ? '.' + m[3] : ''));
  if (!Number.isFinite(num)) return { ok: false, error: '数值无效（NaN/Infinity）' };
  const yuan = m[4] && m[4][0] === '万' ? num * 10000 : num;
  const cents = Math.round(yuan * 100);
  if (!Number.isSafeInteger(cents)) return { ok: false, error: '金额超出安全整数范围' };
  if (cents > MAX_CENTS) return { ok: false, error: '金额过大（上限约 100 亿元）' };
  return { ok: true, cents };
}

/**
 * 扫描完整金额表达式，再交给严格解析器。指数、范围和超精度属于一个
 * 无效表达式，不能从其尾部偷取一个貌似有效的数字。
 */
const LINE_AMOUNT_RE = /([+\-−]?\d[\d,.eE+\-−—–~～至到\s]*|[+\-]?(?:Infinity|NaN))\s*(万\s*元?|元)/gi;

function findAmounts(line) {
  const out = [];
  LINE_AMOUNT_RE.lastIndex = 0;
  let m;
  while ((m = LINE_AMOUNT_RE.exec(line)) !== null) {
    const before = line.slice(0, m.index).trimEnd();
    const after = line.slice(LINE_AMOUNT_RE.lastIndex);
    const prev = before.slice(-1);
    const invalidContext = /[\d.A-Za-z,+\-−—–~～至到]/.test(prev)
      || /^[\d.eE]/.test(after)
      || /^\s*[—–~～至到-]\s*[+\-]?\d/.test(after);
    out.push({ token: m[1].trim() + m[2].replace(/\s/g, ''), index: m.index, invalidContext });
  }
  return out;
}

/** 取条件值：优先取冒号后的内容，否则取关键词之后的文本。 */
function conditionValue(trimmed, keyword) {
  if (!trimmed.startsWith(keyword)) return null;
  const after = trimmed.slice(keyword.length);
  if (!/^(?:\s*[：:]|\s+)/.test(after)) return null;
  return after.replace(/^\s*[：:]?\s*/, '').trim() || null;
}

function normalizeCond(v) {
  return typeof v === 'string' ? v.trim() : '';
}

function conditionAtStart(segment) {
  for (const key of CONDITION_KEYS) {
    const patterns = [...CONDITION_PATTERNS[key]].sort((a, b) => b.length - a.length);
    const alias = patterns.find((p) => segment.startsWith(p) && conditionValue(segment, p) !== null);
    if (alias) return { key, value: conditionValue(segment, alias) };
  }
  return null;
}

function feeMentions(segment) {
  const matches = [];
  for (const key of FEE_KEYS) for (const alias of FEE_ALIASES[key]) {
    let index = segment.indexOf(alias);
    while (index !== -1) {
      matches.push({ key, alias, index, end: index + alias.length });
      index = segment.indexOf(alias, index + alias.length);
    }
  }
  matches.sort((a, b) => a.index - b.index || b.alias.length - a.alias.length);
  const kept = [];
  for (const match of matches) {
    if (!kept.some((m) => match.index < m.end && match.end > m.index)) kept.push(match);
  }
  return kept;
}

// ── 原文抽取 ────────────────────────────────────────────────

/**
 * 从报价原文中抽取 7 项费用与 3 项条件。
 * 规则（可解释）：
 *  1. 逐行按分号切分，费用只读取自身标签之后、下一标签或赠品/合计之前的局部文本；
 *  2. 只采信带单位（元/万/万元）的金额，年份、车型数字不会被当作费用；
 *  3. 该行若含「合计/小计」等词，则只采信该词出现之前的金额（防止合计混入费用行）；
 *  4. 同字段只出现一个金额 → 'unconfirmed'（建议值，待确认）；
 *     出现多个不同金额 → 'unknown'（保持未知，候选全部保留，不取第一个）；
 *     没有金额 → 'unknown'（未报价 ≠ 0）；
 *  5. 条件（车型/付款方式/费用范围）只做建议，必须人工确认后才参与比较。
 * @param {string} text 报价原文
 * @returns {Quote}
 */
export function extractQuote(text) {
  const raw = typeof text === 'string' ? text : '';
  const lines = raw.split(/\r?\n/);

  const fields = {};
  for (const key of FEE_KEYS) {
    fields[key] = {
      key, label: FEE_LABELS[key],
      status: 'unknown', value: null, source: null,
      candidates: [], amounts: [], evidence: [], note: '',
    };
  }
  const conditions = {};
  for (const key of CONDITION_KEYS) {
    conditions[key] = {
      key, label: CONDITION_LABELS[key],
      status: 'unknown', value: null, source: null,
      candidates: [], evidence: [], note: '',
    };
  }
  const declaredTotals = [];
  const issues = [];

  lines.forEach((rawLine, idx) => {
    const t = rawLine.trim();
    if (!t) return;

    for (const segment of t.split(/[；;]/).map((s) => s.trim()).filter(Boolean)) {
      const condition = conditionAtStart(segment);
      if (condition) {
        // 条件值中的费用清单不是费用报价，不把它算作金额证据。
        const c = conditions[condition.key];
        c.evidence.push({ line: rawLine, lineIndex: idx });
        if (!c.candidates.includes(condition.value)) c.candidates.push(condition.value);
        continue;
      }
      const mentions = feeMentions(segment);
      mentions.forEach((mention, mentionIndex) => {
        if (/赠送|赠品|礼品|保养价值/.test(segment.slice(0, mention.index))) return;
        const f = fields[mention.key];
        if (!f.evidence.some((e) => e.lineIndex === idx)) f.evidence.push({ line: rawLine, lineIndex: idx });
        let local = segment.slice(mention.end, mentions[mentionIndex + 1]?.index ?? segment.length);
        const stop = /合计|小计|共计|总价|总额|赠送|赠品|礼品|保养价值/.exec(local);
        if (stop) local = local.slice(0, stop.index);
        const amounts = findAmounts(local);
        for (const amount of amounts) {
          const parsed = amount.invalidContext
            ? { ok: false, error: '金额属于指数、范围或其他不支持的更大表达式' }
            : parseMoney(amount.token);
          f.amounts.push({ cents: parsed.ok ? parsed.cents : null, lineIndex: idx,
            valid: parsed.ok, error: parsed.ok ? undefined : parsed.error, token: amount.token });
          if (parsed.ok && !f.candidates.some((c) => c.cents === parsed.cents)) {
            f.candidates.push({ cents: parsed.cents, lineIndex: idx });
          } else if (!parsed.ok) {
            issues.push(`第 ${idx + 1} 行「${t}」的「${f.label}」金额无法采信：${parsed.error}`);
          }
        }
        if (amounts.length === 0 && /\d|NaN|Infinity/i.test(local)) {
          f.suspect = true;
          f.amounts.push({ cents: null, lineIndex: idx, valid: false, error: '未找到受支持的完整金额表达式' });
          issues.push(`第 ${idx + 1} 行「${t}」的「${f.label}」存在无法可靠识别的金额，需人工核对`);
        }
      });
    }

    // 3) 原文申报合计/小计（交叉核对用）：只取合计关键词之后的金额，
    //    避免把同一行里的费用金额误记成合计数
    if (TOTAL_KEYWORD_RE.test(t)) {
      const tkAll = TOTAL_KEYWORD_RE.exec(t);
      const afterTotal = t.slice(tkAll.index + tkAll[0].length);
      for (const a of findAmounts(afterTotal)) {
        const parsed = a.invalidContext ? { ok: false } : parseMoney(a.token);
        if (parsed.ok) declaredTotals.push({ cents: parsed.cents, lineIndex: idx });
      }
    }
  });

  // 4) 费用定级
  for (const key of FEE_KEYS) {
    const f = fields[key];
    if (f.amounts.some((a) => !a.valid)) {
      f.status = 'unknown';
      f.value = null;
      f.note = '原文存在无效或不明确金额，保留审计记录，需人工核对';
    } else if (f.candidates.length === 1) {
      f.status = 'unconfirmed';
      f.value = f.candidates[0].cents;
      f.source = 'extract';
      f.note = '原文单一金额，待确认';
    } else if (f.candidates.length > 1) {
      f.status = 'unknown'; // 多个金额：保持未知，绝不取第一个
      f.value = null;
      f.source = null;
      const list = f.candidates.map((c) => formatCents(c.cents)).join('、');
      f.note = `原文出现 ${f.candidates.length} 个不同金额（${list}），需人工确认后采用`;
      issues.push(`「${f.label}」出现多个金额（${list}），未自动采用任何一个`);
    } else {
      f.status = 'unknown';
      f.value = null;
      if (f.amounts.some((a) => !a.valid)) f.note = '原文金额无效（负数/超限/格式不明），需人工核对';
      else if (f.evidence.some((e) => UNQUOTED_RE.test(e.line))) f.note = '原文明确未报价';
      else if (f.suspect) f.note = '原文存在无法可靠识别的金额，需人工核对';
      else if (f.evidence.length) f.note = '原文提及但无有效金额';
      else f.note = '原文未提及';
    }
  }

  // 5) 条件定级
  for (const key of CONDITION_KEYS) {
    const c = conditions[key];
    if (c.candidates.length === 1) {
      c.status = 'unconfirmed';
      c.value = c.candidates[0];
      c.source = 'extract';
      c.note = '原文单一取值，待确认';
    } else if (c.candidates.length > 1) {
      c.status = 'unknown';
      c.value = null;
      c.note = `原文出现多个取值（${c.candidates.join('、')}），需人工确认`;
    } else {
      c.status = 'unknown';
      c.value = null;
      c.note = '原文未提及';
    }
  }

  return { raw, lines, fields, conditions, declaredTotals, issues };
}

// ── 比较 ────────────────────────────────────────────────────

function validCents(value) {
  return Number.isSafeInteger(value) && value >= 0 && value <= MAX_CENTS;
}

function visibleEvidence(item) {
  return Array.isArray(item.evidence) && item.evidence.some((e) =>
    typeof e.line === 'string' && e.line.trim() && Number.isInteger(e.lineIndex) && e.lineIndex >= 0);
}

function hasSource(item) {
  if (item.source === 'manual') return (typeof item.note === 'string' && item.note.trim()) || visibleEvidence(item);
  return item.source === 'extract' && visibleEvidence(item);
}

function confirmedFee(field) {
  if (!validCents(field.value) || field.status !== 'confirmed' || !hasSource(field)) return false;
  if (field.source === 'manual') return true;
  return field.candidates.length === 1 && field.candidates[0].cents === field.value
    && !field.amounts.some((amount) => !amount.valid);
}

function confirmedCondition(condition) {
  if (!normalizeCond(condition.value) || condition.status !== 'confirmed' || !hasSource(condition)) return false;
  return condition.source === 'manual' || condition.candidates.some((c) => c === condition.value);
}

function sideTotals(q) {
  let known = 0;
  let count = 0;
  let allConfirmed = true;
  for (const key of FEE_KEYS) {
    const f = q.fields[key];
    if (validCents(f.value)) { known += f.value; count += 1; }
    if (!confirmedFee(f)) allConfirmed = false;
  }
  const declarations = q.declaredTotals.filter((d) => validCents(d.cents)).map((d) => {
    const sourceLine = typeof q.lines?.[d.lineIndex] === 'string' ? q.lines[d.lineIndex] : '';
    const label = /(?:已知\s*)?小计|合计|共计|总价|总额/.exec(sourceLine)?.[0];
    return { cents: d.cents, kind: label?.includes('小计') ? 'subtotal' : label ? 'total' : 'unknown' };
  });
  const values = (kind) => [...new Set(declarations.filter((d) => d.kind === kind).map((d) => d.cents))];
  const totals = values('total'), subtotals = values('subtotal'), unknown = values('unknown');
  let declaredTotalCents = null;
  let declaredNote = '原文未申报总额或小计';
  if (totals.length === 1) {
    declaredTotalCents = totals[0];
    declaredNote = count === 7 && allConfirmed
      ? (known === declaredTotalCents ? '原文申报合计与 7 项已确认合计一致' : '原文申报合计与已录入 7 项不一致，请复核')
      : (declaredTotalCents > known
          ? `原文申报合计 ${formatCents(declaredTotalCents)} 大于已录入小计 ${formatCents(known)}；差额可能来自未报价项，不能据此补零`
          : '原文申报合计不大于已录入小计');
    if (subtotals.length) declaredNote += `；原文另列小计 ${subtotals.map(formatCents).join('、')}，小计不是完整总额`;
  } else if (totals.length > 1) {
    declaredNote = `原文出现多个合计数（${totals.map(formatCents).join('、')}），未采用`;
  } else if (subtotals.length) {
    if (subtotals.length === 1) declaredTotalCents = subtotals[0];
    declaredNote = `原文${subtotals.length === 1 ? '已知小计为' : '列出多个小计'} ${subtotals.map(formatCents).join('、')}；小计只反映原文当时已知的费用，不是完整总额`;
    if (allConfirmed) declaredNote += `；当前七项已确认合计为 ${formatCents(known)}，按当前录入范围计算`;
  } else if (unknown.length) {
    if (unknown.length === 1) declaredTotalCents = unknown[0];
    declaredNote = `原文申报金额 ${unknown.map(formatCents).join('、')} 的来源标签未辨明，不视为完整总额`;
  }
  return {
    knownSubtotalCents: known,
    knownCount: count,
    completeTotalCents: allConfirmed ? known : null,
    allConfirmed,
    declaredTotalCents,
    declaredNote,
  };
}

/**
 * 比较两份报价（Quote 对象，可含 UI 层的确认/人工补充状态）。
 * 任何一项缺失、未确认，或车型/付款方式/费用范围不一致 → 阻断，不输出差额。
 * @returns {Comparison}
 */
export function compareQuotes(qa, qb) {
  const conditionResults = [];
  let conditionMismatch = false;
  let conditionPending = false;
  for (const key of CONDITION_KEYS) {
    const a = qa.conditions[key];
    const b = qb.conditions[key];
    let status;
    let detail;
    if (a.status !== 'confirmed' || b.status !== 'confirmed' || !normalizeCond(a.value) || !normalizeCond(b.value)) {
      status = 'unconfirmed';
      conditionPending = true;
      detail = '两侧均需人工确认后才可比较';
    } else if (normalizeCond(a.value) !== normalizeCond(b.value)) {
      status = 'mismatch';
      conditionMismatch = true;
      detail = `A「${a.value}」 / B「${b.value}」`;
    } else if (!confirmedCondition(a) || !confirmedCondition(b)) {
      status = 'unconfirmed';
      conditionPending = true;
      detail = '已录入条件仍需有效来源或可见的人工补充说明';
    } else {
      status = 'match';
      detail = String(a.value);
    }
    conditionResults.push({
      key, label: CONDITION_LABELS[key], status, detail,
      a: { value: a.value, status: a.status },
      b: { value: b.value, status: b.status },
    });
  }

  const missing = [];
  const unconfirmed = [];
  const ambiguous = [];
  for (const key of FEE_KEYS) {
    const a = qa.fields[key];
    const b = qb.fields[key];
    const nullSides = [];
    if (!validCents(a.value)) nullSides.push('A');
    if (!validCents(b.value)) nullSides.push('B');
    if (nullSides.length > 0) {
      missing.push({ key, label: FEE_LABELS[key], sides: nullSides });
      continue;
    }
    if (!confirmedFee(a) || !confirmedFee(b)) {
      const sides = [];
      if (!confirmedFee(a)) sides.push('A');
      if (!confirmedFee(b)) sides.push('B');
      unconfirmed.push({ key, label: FEE_LABELS[key], sides });
    }
    const ambSides = [];
    const values = [];
    if (a.candidates.length > 1 && !(a.source === 'manual' && confirmedFee(a))) { ambSides.push('A'); values.push(...a.candidates.map((c) => formatCents(c.cents))); }
    if (b.candidates.length > 1 && !(b.source === 'manual' && confirmedFee(b))) { ambSides.push('B'); values.push(...b.candidates.map((c) => formatCents(c.cents))); }
    if (ambSides.length > 0) ambiguous.push({ key, label: FEE_LABELS[key], sides: ambSides, values: [...new Set(values)] });
  }

  let status;
  if (conditionMismatch) status = 'condition-mismatch';
  else if (missing.length > 0) status = 'missing';
  else if (conditionPending || unconfirmed.length > 0) status = 'pending';
  else status = 'comparable';

  const blockers = [];
  for (const cr of conditionResults) {
    if (cr.status === 'mismatch') blockers.push(`「${cr.label}」不一致：${cr.detail}——条件不同，不能判定谁便宜`);
    else if (cr.status === 'unconfirmed') blockers.push(`「${cr.label}」尚未人工确认`);
  }
  for (const m of missing) {
    blockers.push(`「${m.label}」缺失或金额无效（${m.sides.join('、')}）——未报价 ≠ 0，不能补零比较`);
  }
  for (const u of unconfirmed) {
    blockers.push(`「${u.label}」金额、确认状态或补充来源待核对（${u.sides.join('、')}）`);
  }
  for (const a of ambiguous) {
    blockers.push(`「${a.label}」原文有多个金额（${a.values.join('、')}），未自动采用`);
  }

  const totals = { a: sideTotals(qa), b: sideTotals(qb) };

  let diff = null;
  if (status === 'comparable') {
    const items = FEE_KEYS.map((key) => ({
      key,
      label: FEE_LABELS[key],
      aCents: qa.fields[key].value,
      bCents: qb.fields[key].value,
      deltaCents: qb.fields[key].value - qa.fields[key].value,
    }));
    diff = { totalCents: items.reduce((s, i) => s + i.deltaCents, 0), items };
  }

  const questions = buildQuestions(conditionResults, missing, ambiguous, unconfirmed);

  return {
    status,
    statusLabel: STATUS_LABELS[status],
    blockers,
    conditionResults,
    missing,
    unconfirmed,
    ambiguous,
    totals,
    diff,
    questions,
  };
}

function buildQuestions(conditionResults, missing, ambiguous, unconfirmed) {
  const qs = [];
  for (const cr of conditionResults) {
    if (cr.status === 'mismatch') {
      qs.push(`两份报价的「${cr.label}」不一致（A：${cr.a.value}；B：${cr.b.value}）。请确认是否同条件；若确实不同，请提供同条件的报价后再比较，本工具不替您折算差异。`);
    } else if (cr.status === 'unconfirmed') {
      qs.push(`请人工确认两份报价的「${cr.label}」是否一致（A：${cr.a.value ?? '未提及'}；B：${cr.b.value ?? '未提及'}）。`);
    }
  }
  for (const m of missing) {
    const where = m.sides.map((s) => `报价 ${s}`).join('、');
    qs.push(`请向销售明确${where}中「${m.label}」的金额；若为 0 元请明示，未报价不能按 0 元计算。`);
  }
  for (const a of ambiguous) {
    const where = a.sides.map((s) => `报价 ${s}`).join('、');
    qs.push(`${where}中「${a.label}」出现多个金额（${a.values.join('、')}），请确认以哪一个为准。`);
  }
  for (const u of unconfirmed) {
    const where = u.sides.map((s) => `报价 ${s}`).join('、');
    qs.push(`请确认${where}中「${u.label}」的抽取值是否与报价原文一致。`);
  }
  return qs;
}

// ── 报告 ────────────────────────────────────────────────────

function group(n) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** 分 → 中文金额展示，如 13200000 → 「132,000元」；null → 「未报价」。 */
export function formatCents(cents) {
  if (cents === null || cents === undefined || !Number.isFinite(cents)) return '未报价';
  const neg = cents < 0 ? '-' : '';
  const abs = Math.round(Math.abs(cents));
  if (abs % 100 === 0) return neg + group(abs / 100) + '元';
  return neg + group(Math.floor(abs / 100)) + '.' + String(abs % 100).padStart(2, '0') + '元';
}

function mdCell(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/[\\`*_\[\]{}|~]/g, '\\$&').replace(/\r?\n/g, ' ');
}

function literalBlock(text) {
  const value = String(text ?? '');
  const runs = value.match(/`+/g) || [];
  const fence = '`'.repeat(Math.max(3, ...runs.map((run) => run.length + 1)));
  return `${fence}text\n${value}\n${fence}`;
}

function fieldValueLabel(f) {
  return validCents(f.value) ? formatCents(f.value) : '未报价/金额无效';
}

function fieldStatusLabel(f) {
  if (confirmedFee(f)) return f.source === 'manual' ? '已确认·人工补充' : '已确认·原文';
  if (validCents(f.value)) return '待确认/来源待核对';
  if (f.source === 'manual') return '人工标记未报价/无效';
  return '未报价/未知';
}

function sourceEnum(source) {
  return source === 'extract' || source === 'manual' ? source : null;
}

function statusEnum(status) {
  return ['unknown', 'unconfirmed', 'confirmed'].includes(status) ? status : 'unknown';
}

function reportBlockers(cmp) {
  const out = [];
  for (const cr of cmp.conditionResults) {
    if (cr.status === 'mismatch') out.push(`「${CONDITION_LABELS[cr.key]}」不一致，不能判定谁便宜。`);
    else if (cr.status !== 'match') out.push(`「${CONDITION_LABELS[cr.key]}」缺失、未确认或来源待核对。`);
  }
  for (const item of cmp.missing) out.push(`「${FEE_LABELS[item.key]}」缺失或金额无效（${item.sides.join('、')}）；未报价不能补零。`);
  for (const item of cmp.unconfirmed) out.push(`「${FEE_LABELS[item.key]}」金额、确认或来源待核对（${item.sides.join('、')}）。`);
  for (const item of cmp.ambiguous) out.push(`「${FEE_LABELS[item.key]}」存在多个原文候选，需明确采用值（${item.sides.join('、')}）。`);
  return out;
}

function reportQuestions(cmp) {
  const out = [];
  for (const cr of cmp.conditionResults) {
    if (cr.status !== 'match') out.push(`请核实两份报价的「${CONDITION_LABELS[cr.key]}」及来源；取得并确认同条件报价后再比较。`);
  }
  for (const item of cmp.missing) out.push(`请补充报价 ${item.sides.join('、')} 的「${FEE_LABELS[item.key]}」明确金额与来源；若为零请明确说明。`);
  for (const item of cmp.unconfirmed) out.push(`请核对报价 ${item.sides.join('、')} 的「${FEE_LABELS[item.key]}」金额、确认状态和补充来源。`);
  for (const item of cmp.ambiguous) out.push(`请核实报价 ${item.sides.join('、')} 的「${FEE_LABELS[item.key]}」实际采用哪一个候选，并记录补充说明。`);
  return out;
}

/**
 * 生成 Markdown/JSON。默认省略原文、摘录、条件自由文本与人工说明；
 * 该模式仍包含金额与状态，不是任意数据自动脱敏。
 * @param {Quote} qa
 * @param {Quote} qb
 * @param {Comparison} cmp 接受现有调用形状；导出前从当前快照复核以避免旧结果。
 * @param {{includeOriginal?:boolean, generatedAt?:string}} [opts]
 * @returns {{markdown:string, json:string}}
 */
export function makeReport(qa, qb, cmp, opts = {}) {
  cmp = compareQuotes(qa, qb);
  const includeOriginal = opts.includeOriginal === true;
  const generatedAt = typeof opts.generatedAt === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(opts.generatedAt)
    ? opts.generatedAt : new Date().toISOString();
  const blockers = reportBlockers(cmp);
  const questions = reportQuestions(cmp);
  const exportNotice = includeOriginal
    ? '完整导出：包含原文、摘录、自由文本条件及人工说明；分享前请自行核查范围。'
    : '省略原文模式：不包含原文、摘录、自由文本条件或人工说明；仍包含金额与状态，不承诺任意数据脱敏。';
  const L = ['# 报价核对报告（报价显微镜）', '', `- 生成时间：${generatedAt}`,
    `- 结论：**${cmp.statusLabel}**`, `- 导出范围：${exportNotice}`,
    '- 口径：仅比较七项录入费用；未报价 ≠ 0；不构成购买、贷款或车型建议。', '',
    '## 一、条件核对', '', '| 条件 | 报价 A | 报价 B | 结论 |', '| --- | --- | --- | --- |'];
  for (const cr of cmp.conditionResults) {
    const labels = ['a', 'b'].map((side) => {
      const item = cr[side];
      const state = item.status === 'confirmed' ? '已标记确认' : '未确认';
      return includeOriginal ? `${item.value ?? '未提及'}（${state}）` : state;
    });
    const verdict = cr.status === 'match' ? '一致' : cr.status === 'mismatch' ? '不一致' : '待核对';
    L.push(`| ${CONDITION_LABELS[cr.key]} | ${mdCell(labels[0])} | ${mdCell(labels[1])} | ${verdict} |`);
  }
  L.push('', '## 二、费用对照（单位：元）', '', '| 项目 | 报价 A | 报价 B | 差额(B−A) | A 状态 | B 状态 |', '| --- | --- | --- | --- | --- | --- |');
  for (const key of FEE_KEYS) {
    const fa = qa.fields[key], fb = qb.fields[key];
    const delta = cmp.diff?.items.find((item) => item.key === key);
    L.push(`| ${FEE_LABELS[key]} | ${fieldValueLabel(fa)} | ${fieldValueLabel(fb)} | ${delta ? formatCents(delta.deltaCents) : '—'} | ${fieldStatusLabel(fa)} | ${fieldStatusLabel(fb)} |`);
  }
  L.push(`| 已知小计（A ${cmp.totals.a.knownCount}/7、B ${cmp.totals.b.knownCount}/7） | ${formatCents(cmp.totals.a.knownSubtotalCents)} | ${formatCents(cmp.totals.b.knownSubtotalCents)} | — | | |`);
  L.push(`| 七项已确认合计 | ${cmp.totals.a.completeTotalCents === null ? '未完整' : formatCents(cmp.totals.a.completeTotalCents)} | ${cmp.totals.b.completeTotalCents === null ? '未完整' : formatCents(cmp.totals.b.completeTotalCents)} | — | | |`);
  L.push('', '已知小计可以包含待确认候选，不等于完整总额，不能据此判断谁更便宜。');
  for (const [side, total] of [['A', cmp.totals.a], ['B', cmp.totals.b]]) {
    L.push(`- ${side} 原文申报金额：${total.declaredTotalCents === null ? '无单一可用数值' : formatCents(total.declaredTotalCents)}（${total.declaredNote}）`);
  }
  L.push('', '## 三、差额说明', '');
  if (cmp.diff) {
    L.push(`- 在已确认录入范围内，B − A = ${formatCents(cmp.diff.totalCents)}。`);
    for (const item of cmp.diff.items) {
      L.push(`- ${FEE_LABELS[item.key]}：A ${formatCents(item.aCents)} → B ${formatCents(item.bCents)}（${item.deltaCents > 0 ? '+' : ''}${formatCents(item.deltaCents)}）`);
    }
  } else L.push('- 当前无法完整比较，不输出费用排名或差额。');
  L.push('', '## 四、未知与问题', '');
  if (!blockers.length) L.push('- 无：七项金额均已确认且三类条件一致。');
  else blockers.forEach((text) => L.push(`- ${text}`));
  for (const [side, quote] of [['A', qa], ['B', qb]]) {
    if (quote.issues.length) {
      L.push(`- ${side} 有 ${quote.issues.length} 条抽取提示，请核对本机原文。`);
      if (includeOriginal) quote.issues.forEach((text) => L.push(literalBlock(text)));
    }
  }
  L.push('', '## 五、建议追问', '');
  if (!questions.length) L.push('1. 无待追问项。');
  else questions.forEach((text, index) => L.push(`${index + 1}. ${text}`));
  L.push('', includeOriginal ? '## 六、来源证据（用户选择包含）' : '## 六、来源类型与行号（原文已省略）', '');
  for (const [side, quote] of [['A', qa], ['B', qb]]) {
    L.push(`### 报价 ${side}`, '');
    for (const [kind, keys, labels] of [['conditions', CONDITION_KEYS, CONDITION_LABELS], ['fields', FEE_KEYS, FEE_LABELS]]) {
      for (const key of keys) {
        const item = quote[kind][key];
        const source = sourceEnum(item.source);
        const name = source === 'manual' ? '人工补充' : source === 'extract' ? '原文' : '无来源';
        const validEvidence = item.evidence.filter((e) => Number.isInteger(e.lineIndex) && e.lineIndex >= 0);
        L.push(`- ${labels[key]}：${name}；${validEvidence.length ? validEvidence.map((e) => `第 ${e.lineIndex + 1} 行`).join('、') : '无原文行号'}。`);
        if (includeOriginal) {
          if (kind === 'conditions') L.push('条件值：', literalBlock(item.value ?? '（缺失）'));
          if (item.note) L.push('核对/补充说明：', literalBlock(item.note));
          validEvidence.forEach((e) => L.push(`第 ${e.lineIndex + 1} 行：`, literalBlock(e.line)));
        }
      }
    }
    L.push('');
  }
  if (includeOriginal) {
    L.push('## 附：报价原文（用户选择包含）', '', '### 报价 A 原文', '', literalBlock(qa.raw), '',
      '### 报价 B 原文', '', literalBlock(qb.raw), '');
  }
  const conditionResults = cmp.conditionResults.map((cr) => {
    const out = { key: cr.key, label: CONDITION_LABELS[cr.key], status: cr.status,
      a: { status: statusEnum(cr.a.status) }, b: { status: statusEnum(cr.b.status) } };
    if (includeOriginal) {
      out.detail = cr.detail;
      out.a.value = cr.a.value;
      out.b.value = cr.b.value;
    }
    return out;
  });
  const jsonObj = {
    tool: '报价显微镜', engineVersion: ENGINE_VERSION, generatedAt, includeOriginal, exportNotice,
    scope: '仅比较七项录入费用；未报价 ≠ 0；不构成购买、贷款或车型建议',
    status: cmp.status, statusLabel: cmp.statusLabel, blockers, conditionResults,
    missing: cmp.missing, unconfirmed: cmp.unconfirmed, ambiguous: cmp.ambiguous,
    totals: cmp.totals, diff: cmp.diff, questions,
    quotes: { a: quoteToJson(qa, includeOriginal), b: quoteToJson(qb, includeOriginal) },
  };
  return { markdown: L.join('\n'), json: JSON.stringify(jsonObj, null, 2) };
}

function quoteToJson(q, includeOriginal) {
  const lineNumber = (value) => Number.isInteger(value) && value >= 0 ? value : null;
  const evidence = (item) => item.evidence
    .filter((e) => Number.isInteger(e.lineIndex) && e.lineIndex >= 0)
    .map((e) => includeOriginal ? { line: e.line, lineIndex: e.lineIndex } : { lineIndex: e.lineIndex });
  const out = { conditions: {}, fields: {},
    declaredTotals: q.declaredTotals.filter((d) => validCents(d.cents))
      .map((d) => ({ cents: d.cents, yuan: d.cents / 100, lineIndex: lineNumber(d.lineIndex) })),
    issues: includeOriginal ? q.issues : q.issues.map(() => '存在抽取提示；本模式省略具体原文，请在本机核对。'),
  };
  for (const key of CONDITION_KEYS) {
    const c = q.conditions[key];
    out.conditions[key] = { status: statusEnum(c.status), source: sourceEnum(c.source), evidence: evidence(c) };
    if (includeOriginal) Object.assign(out.conditions[key], { value: c.value, note: c.note, candidates: c.candidates });
  }
  for (const key of FEE_KEYS) {
    const f = q.fields[key];
    out.fields[key] = { valueCents: validCents(f.value) ? f.value : null,
      valueYuan: validCents(f.value) ? f.value / 100 : null,
      status: statusEnum(f.status), source: sourceEnum(f.source),
      candidates: f.candidates.filter((c) => validCents(c.cents))
        .map((c) => ({ cents: c.cents, lineIndex: lineNumber(c.lineIndex) })), evidence: evidence(f) };
    if (includeOriginal) Object.assign(out.fields[key], { note: f.note, amounts: f.amounts });
  }
  if (includeOriginal) out.raw = q.raw;
  return out;
}
