#!/usr/bin/env python3
"""Compare exactly two user supplied synthetic or real quotes offline; no policy lookup.

SPDX-License-Identifier: MIT
Only computes recorded amounts; missing amounts remain null. See references/quote-contract.md.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys

MONEY = ('price', 'tax', 'insurance', 'plate', 'addons')
FINANCE = ('principal', 'total_repay', 'fees_outside_total')
ENERGY = ('annual_km', 'consumption_per_100', 'unit_price', 'home_price', 'fast_price', 'home_share')


class InputProblem(ValueError):
    pass


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputProblem('JSON 字段重复：%s' % key)
        result[key] = value
    return result


def fields(value, allowed, required, where):
    if not isinstance(value, dict):
        raise InputProblem('%s 必须是对象' % where)
    extra, missing = set(value) - set(allowed), set(required) - set(value)
    if extra or missing:
        raise InputProblem('%s 字段不符合契约（未知 %s；缺少 %s）' % (where, sorted(extra), sorted(missing)))


def amount(value, where):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise InputProblem('%s 必须是十进制数字或 null，不能是布尔值/数组' % where)
    text = str(value)
    if len(text) > 80:
        raise InputProblem('%s 数字过长' % where)
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise InputProblem('%s 不是十进制数字' % where)
    if not number.is_finite() or number < 0 or number > Decimal('1e15'):
        raise InputProblem('%s 须为 0 到 1e15 的有限非负数' % where)
    if number.as_tuple().exponent < -12:
        raise InputProblem('%s 最多支持 12 位小数' % where)
    return number


def dec(value):
    if value is None:
        return None
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def label(value, where):
    if not isinstance(value, str) or not value.strip() or len(value) > 300 or any(ord(c) < 32 for c in value):
        raise InputProblem('%s 须为 1–300 字符的单行非空说明' % where)
    return value


def metric(known, missing, formula, pointers):
    return {'complete': not missing, 'value': dec(known) if not missing else None,
            'known_subtotal': dec(known), 'missing_fields': missing,
            'formula': formula, 'input_pointers': pointers}


def quote_report(quote, index):
    prefix = '/quotes/%s' % index
    allowed = ('id', 'source', 'method', 'amounts', 'finance', 'energy')
    fields(quote, allowed, ('id', 'source', 'method', 'amounts'), prefix)
    ident = label(quote['id'], prefix + '/id')
    source = label(quote['source'], prefix + '/source')
    method = quote['method']
    if method not in ('cash', 'finance'):
        raise InputProblem('%s/method 只能是 cash 或 finance' % prefix)
    fields(quote['amounts'], MONEY, (), prefix + '/amounts')
    values, provenance = {}, {}
    for key in MONEY:
        pointer = prefix + '/amounts/' + key
        values[key] = amount(quote['amounts'].get(key), pointer)
        provenance[pointer] = {'source': source, 'recorded': key in quote['amounts'], 'value': dec(values[key])}
    missing = [prefix + '/amounts/' + key for key, value in values.items() if value is None]
    purchase = metric(sum((v for v in values.values() if v is not None), Decimal(0)), missing,
                      'price + tax + insurance + plate + addons', [prefix + '/amounts/' + k for k in MONEY])
    finance = None
    financing_amounts = None
    if method == 'cash':
        if quote.get('finance') is not None:
            raise InputProblem('%s 为 cash，不能同时录入 finance' % prefix)
    else:
        data = quote.get('finance')
        if data is None:
            data = {}
        fields(data, FINANCE, (), prefix + '/finance')
        financing_amounts = {}
        for key in FINANCE:
            pointer = prefix + '/finance/' + key
            financing_amounts[key] = amount(data.get(key), pointer)
            provenance[pointer] = {'source': source, 'recorded': key in data, 'value': dec(financing_amounts[key])}
        principal, total, fees = (financing_amounts[k] for k in FINANCE)
        if principal is not None and total is not None and total < principal:
            raise InputProblem('%s 总还款额不能小于本金' % prefix)
        missing_finance = [prefix + '/finance/' + k for k, v in financing_amounts.items() if v is None]
        difference = total - principal if principal is not None and total is not None else None
        # If either repayment component is unknown, no subtraction is possible.
        known = (difference if difference is not None else Decimal(0)) + (fees if fees is not None else Decimal(0))
        finance = metric(known, missing_finance, 'total_repay - principal + fees_outside_total',
                         [prefix + '/finance/' + k for k in FINANCE])
        finance['repayment_difference'] = dec(difference)
        finance['known_subtotal_scope'] = '已知还款差额（能算时）与已知另收费用之和；不是完整贷款成本'
    combined = metric(Decimal(purchase['known_subtotal']) + (Decimal(finance['known_subtotal']) if finance else 0),
                      purchase['missing_fields'] + (finance['missing_fields'] if finance else []),
                      'purchase + finance_fee (cash: purchase only)', purchase['input_pointers'] + (finance['input_pointers'] if finance else []))
    energy = None
    if 'energy' in quote:
        fields(quote['energy'], ENERGY, (), prefix + '/energy')
        energy_values = {key: amount(quote['energy'].get(key), prefix + '/energy/' + key) for key in ENERGY}
        for key, value in energy_values.items():
            provenance[prefix + '/energy/' + key] = {'source': source, 'recorded': key in quote['energy'], 'value': dec(value)}
        km, consumption, unit, home, fast, share = (energy_values[k] for k in ENERGY)
        if consumption is not None and consumption <= 0:
            raise InputProblem('%s 百公里能耗须大于 0（里程可为 0）' % prefix)
        if share is not None and share > 1:
            raise InputProblem('%s 家充占比须在 0 到 1 之间' % prefix)
        mixed = any(v is not None for v in (home, fast, share))
        if unit is not None and mixed:
            raise InputProblem('%s 统一单价与家充/快充假设冲突' % prefix)
        required = ('annual_km', 'consumption_per_100', 'home_price', 'fast_price', 'home_share') if mixed else ('annual_km', 'consumption_per_100', 'unit_price')
        missing_energy = [prefix + '/energy/' + k for k in required if energy_values[k] is None]
        energy_value = Decimal(0)
        if not missing_energy:
            effective = home * share + fast * (1 - share) if mixed else unit
            energy_value = km / 100 * consumption * effective
        energy = metric(energy_value, missing_energy,
                        'annual_km / 100 * consumption_per_100 * (home_price * home_share + fast_price * (1 - home_share))' if mixed else 'annual_km / 100 * consumption_per_100 * unit_price',
                        [prefix + '/energy/' + k for k in required])
        # No partial annual cost is inferred when assumptions are incomplete.
        if missing_energy:
            energy['known_subtotal'] = None
        energy['assumptions'] = {k: dec(v) for k, v in energy_values.items()}
    return {'id': ident, 'source': source, 'method': method, 'amounts': {k: dec(v) for k, v in values.items()},
            'finance_inputs': {k: dec(v) for k, v in financing_amounts.items()} if financing_amounts else None,
            'purchase': purchase, 'finance_fee': finance, 'recorded_total': combined,
            'annual_energy': energy, 'provenance': provenance}


def compare_metric(quotes, name, equal_principal=False):
    a, b = (q[name] for q in quotes)
    result = {'scope': name, 'left_id': quotes[0]['id'], 'right_id': quotes[1]['id'],
              'comparable': False, 'right_minus_left': None, 'reason': None}
    if a is None or b is None or not a['complete'] or not b['complete']:
        result['reason'] = '缺项或未提供该范围，不能列示完整差额'
    elif equal_principal and quotes[0]['method'] == quotes[1]['method'] == 'finance' and quotes[0]['finance_inputs']['principal'] != quotes[1]['finance_inputs']['principal']:
        result['reason'] = '贷款本金不同，未作同口径比较'
    elif name == 'annual_energy' and a['assumptions']['annual_km'] != b['assumptions']['annual_km']:
        result['reason'] = '年里程不同，未作同口径比较'
    else:
        result.update(comparable=True, right_minus_left=dec(Decimal(b['value']) - Decimal(a['value'])))
    return result


def build_report(data, sha):
    fields(data, ('schema_version', 'notice', 'quotes'), ('schema_version', 'quotes'), '/')
    if isinstance(data['schema_version'], bool) or data['schema_version'] != 1:
        raise InputProblem('schema_version 必须为 1')
    if 'notice' in data:
        label(data['notice'], '/notice')
    if not isinstance(data['quotes'], list) or len(data['quotes']) != 2:
        raise InputProblem('quotes 必须恰好包含两份报价')
    with localcontext() as context:
        context.prec = 64
        quotes = [quote_report(q, i) for i, q in enumerate(data['quotes'])]
        if quotes[0]['id'] == quotes[1]['id']:
            raise InputProblem('两份报价 id 不能相同')
        comparisons = [compare_metric(quotes, n, equal_principal=n in ('finance_fee', 'recorded_total'))
                       for n in ('purchase', 'finance_fee', 'recorded_total', 'annual_energy')]
    return {'schema_version': 1, 'input_sha256': sha, 'currency': 'CNY',
            'scope': '仅列示用户录入范围的金额；不验证报价真实性，不计算税率/APR，不排序、不推荐车型或融资',
            'quotes': quotes, 'comparisons': comparisons}


def safe_cell(value):
    text = str(value)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('`', '&#96;')


def value_cell(metric_value):
    if metric_value is None:
        return '未提供'
    if metric_value['complete']:
        return metric_value['value']
    known = metric_value['known_subtotal']
    return '待补' + ('；已知小计 ' + known if known is not None else '')


def render_markdown(report):
    labels = {'purchase': '购车款项', 'finance_fee': '录入贷款费用', 'recorded_total': '购车款项加贷款费用', 'annual_energy': '年度能耗假设'}
    a, b = report['quotes']
    lines = ['# 两份报价核对', '', report['scope'], '', '输入 SHA256：`%s`' % report['input_sha256'], '',
             '| 范围（元） | %s | %s | B − A |' % (safe_cell(a['id']), safe_cell(b['id'])), '|---|---|---|---|']
    for comp in report['comparisons']:
        name = comp['scope']
        lines.append('| %s | %s | %s | %s |' % (labels[name], value_cell(a[name]), value_cell(b[name]), comp['right_minus_left'] if comp['comparable'] else comp['reason']))
    for quote in report['quotes']:
        lines += ['', '## ' + safe_cell(quote['id']), '', '用户来源说明：' + safe_cell(quote['source']), '', '| 输入字段（JSON Pointer） | 录入值 | 状态 |', '|---|---|---|']
        for pointer, info in quote['provenance'].items():
            lines.append('| %s | %s | %s |' % (pointer, info['value'] if info['value'] is not None else 'null', '已录入' if info['value'] is not None else '待补'))
        for name in labels:
            item = quote[name]
            if item:
                lines += ['', labels[name] + '算式：`' + item['formula'] + '`']
                lines += ['- 待补：`' + pointer + '`' for pointer in item['missing_fields']]
    return '\n'.join(lines) + '\n'


def render_csv(report):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['left_id', 'right_id', 'scope', 'left_complete', 'left_value', 'left_known_subtotal', 'right_complete', 'right_value', 'right_known_subtotal', 'comparable', 'right_minus_left', 'reason'])
    # Neutralise spreadsheet formula prefixes in user supplied labels.
    def cell(value):
        if value is None:
            return ''
        text = str(value)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    a, b = report['quotes']
    for comp in report['comparisons']:
        left, right = a[comp['scope']], b[comp['scope']]
        writer.writerow([cell(a['id']), cell(b['id']), comp['scope'], left['complete'] if left else '', left['value'] if left else '', left['known_subtotal'] if left else '', right['complete'] if right else '', right['value'] if right else '', right['known_subtotal'] if right else '', comp['comparable'], comp['right_minus_left'], comp['reason'] or ''])
    return output.getvalue()


def load_input(path):
    if path.is_symlink() or not path.is_file():
        raise InputProblem('输入须为普通 JSON 文件，不能是符号链接')
    raw = path.read_bytes()
    if len(raw) > 1024 * 1024:
        raise InputProblem('输入超过 1 MiB')
    try:
        data = json.loads(raw.decode('utf-8'), parse_float=Decimal, parse_int=Decimal,
                          parse_constant=lambda value: (_ for _ in ()).throw(InputProblem('JSON 不允许 %s' % value)),
                          object_pairs_hook=strict_object)
    except (ValueError, UnicodeDecodeError, RecursionError) as error:
        raise InputProblem('无效 JSON：%s' % error)
    return data, hashlib.sha256(raw).hexdigest()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--out-dir', required=True, type=Path, help='必须是不存在的新目录；从不覆盖输入或已有报告')
    seen = set()
    for arg in argv:
        if arg.startswith('--'):
            key = arg.split('=', 1)[0]
            if key in seen:
                parser.error('参数重复：' + key)
            seen.add(key)
    args = parser.parse_args(argv)
    created = False
    try:
        data, sha = load_input(args.input)
        report = build_report(data, sha)
        outputs = {'comparison.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                   'comparison.md': render_markdown(report), 'comparison.csv': render_csv(report)}
        if os.path.lexists(args.out_dir):
            raise InputProblem('输出目录已存在；请换新目录，不覆盖任何输入或已有报告')
        args.out_dir.mkdir(mode=0o700)
        created = True
        for filename, text in outputs.items():
            with (args.out_dir / filename).open('x', encoding='utf-8', newline='') as target:
                target.write(text)
        print('已生成 comparison.json / comparison.md / comparison.csv：' + str(args.out_dir.resolve()))
        return 0
    except (InputProblem, OSError, RecursionError) as error:
        if created:
            shutil.rmtree(args.out_dir)
        sys.stderr.write('未生成报告：%s\n' % error)
        return 1


if __name__ == '__main__':
    sys.exit(main())
