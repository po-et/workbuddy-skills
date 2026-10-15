"""Car quote arithmetic and file preservation, using synthetic amounts only."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1] / 'skills/car-buying-checklist'
SINGLE = BASE / 'scripts/car_cost.py'
COMPARE = BASE / 'scripts/compare_quotes.py'


def load_script(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_script(COMPARE, 'car_compare_test')


class SingleCarTest(unittest.TestCase):
    def cli(self, *args):
        result = subprocess.run([sys.executable, '-B', str(SINGLE), *args], capture_output=True, text=True)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def test_duplicate_price_rejected_even_same_value(self):
        for args in (('--price', '150000', '--price', '150000'), ('--price=150000', '--price=160000')):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 1)

    def test_duplicate_alias_and_flags_rejected(self):
        for args in (('--unit-price', '1', '--electric-price', '2'), ('--ev', '--ev'), ('--price', '15万', '--pr', '15万')):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args).returncode, 1)

    def test_legacy_duplicate_input_rejected(self):
        self.assertEqual(self.cli('150000', '15000', '7', '8', '--price', '150000').returncode, 1)

    def test_conflicting_energy_modes_rejected(self):
        result = self.cli('--km', '15000', '--consumption', '15', '--electric-price', '0.8', '--home-price', '0.6', '--fast-price', '1.5', '--home-share', '0.8')
        self.assertEqual(result.returncode, 1)

    def test_partial_mixed_energy_rejected(self):
        self.assertEqual(self.cli('--km', '1', '--consumption', '1', '--home-share', '0.8').returncode, 1)

    def test_missing_fee_stays_unknown(self):
        result = self.cli('--loan-principal', '100000', '--loan-total', '112000')
        self.assertEqual(result.returncode, 0)
        self.assertIn('已知小计 12,000', result.stdout)
        self.assertIn('[待补：另收费用]', result.stdout)
        self.assertIn('| 另收的手续费、服务费 | [待补]', result.stdout)

    def test_explicit_zero_fee_is_complete(self):
        result = self.cli('--loan-principal', '100000', '--loan-total', '112000', '--loan-fees', '0')
        self.assertEqual(result.returncode, 0)
        self.assertIn('| **录入范围费用合计** | 12,000 |', result.stdout)

    def test_no_implicit_tax_or_insurance(self):
        result = self.cli('--price', '150000')
        self.assertEqual(result.returncode, 0)
        self.assertIn('[待确认：请提供当地正式税费金额]', result.stdout)
        self.assertNotIn('13,274', result.stdout)
        self.assertIn('| 首年保险 | [待补]', result.stdout)

    def test_explicit_tax_used(self):
        result = self.cli('--price', '150000', '--tax', '1000', '--insurance', '0', '--plate', '0', '--addons', '0')
        self.assertEqual(result.returncode, 0)
        self.assertIn('| **落地价合计** | 151,000 |', result.stdout)

    def test_nonfinite_negative_excess_precision_and_bounds_rejected(self):
        for value in ('NaN', 'sNaN', 'Infinity', '-1', '1e9999999', '0e-9999999', '0.0000000000001'):
            with self.subTest(value=value):
                self.assertEqual(self.cli('--price', value).returncode, 1)

    def test_bad_share_rejected(self):
        for value in ('NaN', 'sNaN', 'Infinity', '-0.1', '101%', '1e9999999'):
            with self.subTest(value=value):
                self.assertEqual(self.cli('--km', '1', '--consumption', '1', '--home-price', '1', '--fast-price', '2', '--home-share', value).returncode, 1)

    def test_positive_consumption_required_for_driving(self):
        self.assertEqual(self.cli('--km', '100', '--consumption', '0', '--unit-price', '1').returncode, 1)

    def test_synthetic_mixed_energy(self):
        result = self.cli('--km', '15000', '--consumption', '15', '--home-price', '0.6', '--fast-price', '1.5', '--home-share', '80%')
        self.assertEqual(result.returncode, 0)
        self.assertIn('| 能耗 | 1,755 |', result.stdout)

    def test_zero_mileage_and_explicit_free_energy(self):
        for km, unit in (('0', '8'), ('15000', '0')):
            result = self.cli('--km', km, '--consumption', '7', '--unit-price', unit)
            self.assertEqual(result.returncode, 0)
            self.assertIn('| 能耗 | 0 |', result.stdout)

    def test_existing_out_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'original.md'
            out.write_text('preserve me')
            result = self.cli('--price', '150000', '--out', str(out))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(out.read_text(), 'preserve me')

    def test_output_symlink_does_not_change_target(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'original.txt'
            original.write_text('preserve')
            link = Path(folder) / 'report.md'
            link.symlink_to(original)
            self.assertEqual(self.cli('--price', '150000', '--out', str(link)).returncode, 2)
            self.assertEqual(original.read_text(), 'preserve')
            self.assertTrue(link.is_symlink())


class QuoteComparisonTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((BASE / 'examples/two-quotes-missing-fee.json').read_text())

    def report(self, data=None):
        return MODULE.build_report(copy.deepcopy(self.data if data is None else data), 'synthetic-sha')

    def comparison(self, report, scope):
        return next(c for c in report['comparisons'] if c['scope'] == scope)

    def test_missing_fees_are_null_and_no_cost_ranking(self):
        report = self.report()
        a, b = report['quotes']
        self.assertEqual(a['finance_fee']['value'], '15000')
        self.assertEqual(b['finance_fee']['repayment_difference'], '10500')
        self.assertEqual(b['finance_fee']['known_subtotal'], '10500')
        self.assertIsNone(b['finance_fee']['value'])
        self.assertFalse(b['finance_fee']['complete'])
        self.assertFalse(self.comparison(report, 'finance_fee')['comparable'])
        self.assertIsNone(self.comparison(report, 'recorded_total')['right_minus_left'])
        self.assertNotIn('winner', report)

    def test_complete_fees_difference_exact(self):
        self.data['quotes'][1]['finance']['fees_outside_total'] = '6000'
        report = self.report()
        self.assertEqual(report['quotes'][1]['finance_fee']['value'], '16500')
        self.assertEqual(self.comparison(report, 'finance_fee')['right_minus_left'], '1500')
        self.assertEqual(report['quotes'][0]['recorded_total']['value'], '165000')
        self.assertEqual(self.comparison(report, 'recorded_total')['right_minus_left'], '1500')

    def test_omitted_and_null_both_unknown_but_provenance_distinguishes(self):
        report_null = self.report()
        del self.data['quotes'][1]['finance']['fees_outside_total']
        report_missing = self.report()
        pointer = '/quotes/1/finance/fees_outside_total'
        self.assertTrue(report_null['quotes'][1]['provenance'][pointer]['recorded'])
        self.assertFalse(report_missing['quotes'][1]['provenance'][pointer]['recorded'])
        self.assertIsNone(report_missing['quotes'][1]['finance_inputs']['fees_outside_total'])

    def test_zero_fees_not_unknown(self):
        self.data['quotes'][1]['finance']['fees_outside_total'] = 0
        result = self.report()['quotes'][1]['finance_fee']
        self.assertTrue(result['complete'])
        self.assertEqual(result['value'], '10500')

    def test_all_finance_fields_missing_does_not_invent_total(self):
        self.data['quotes'][1]['finance'] = {}
        result = self.report()['quotes'][1]['finance_fee']
        self.assertFalse(result['complete'])
        self.assertIsNone(result['value'])
        self.assertIsNone(result['repayment_difference'])

    def test_decimal_arithmetic_retains_cents(self):
        self.data['quotes'][0]['finance'] = {'principal': '0.1', 'total_repay': '0.3', 'fees_outside_total': '0.2'}
        self.assertEqual(self.report()['quotes'][0]['finance_fee']['value'], '0.4')

    def test_missing_tax_insurance_and_price_remain_null(self):
        self.data['quotes'][0]['amounts'] = {'price': None, 'plate': '0', 'addons': '0'}
        quote = self.report()['quotes'][0]
        self.assertIsNone(quote['purchase']['value'])
        self.assertEqual(quote['purchase']['known_subtotal'], '0')
        self.assertIsNone(quote['amounts']['tax'])
        self.assertIsNone(quote['amounts']['insurance'])

    def test_different_principal_not_same_scope_comparison(self):
        self.data['quotes'][1]['finance'].update(principal='90000', fees_outside_total='6000')
        report = self.report()
        for name in ('finance_fee', 'recorded_total'):
            comparison = self.comparison(report, name)
            self.assertFalse(comparison['comparable'])
            self.assertIn('本金不同', comparison['reason'])

    def test_cash_and_finance_complete_recorded_amounts(self):
        self.data['quotes'][0]['method'] = 'cash'
        del self.data['quotes'][0]['finance']
        self.data['quotes'][1]['finance']['fees_outside_total'] = '6000'
        report = self.report()
        self.assertIsNone(report['quotes'][0]['finance_fee'])
        self.assertEqual(report['quotes'][0]['recorded_total']['value'], '150000')
        self.assertEqual(self.comparison(report, 'recorded_total')['right_minus_left'], '16500')

    def test_cash_must_not_carry_finance(self):
        self.data['quotes'][0]['method'] = 'cash'
        with self.assertRaises(MODULE.InputProblem):
            self.report()

    def test_total_below_principal_rejected(self):
        self.data['quotes'][0]['finance']['total_repay'] = '99999'
        with self.assertRaises(MODULE.InputProblem):
            self.report()

    def test_negative_boolean_nan_infinite_bad_units_rejected(self):
        for value in ('-1', 'NaN', 'sNaN', 'Infinity', '1e9999999', '0e-999999', '1e-13', True, ['1'], {}, '15万'):
            with self.subTest(value=value):
                self.data['quotes'][0]['amounts']['price'] = value
                with self.assertRaises(MODULE.InputProblem):
                    self.report()

    def test_duplicate_quote_id_and_unknown_schema_fields_rejected(self):
        self.data['quotes'][1]['id'] = 'A'
        with self.assertRaises(MODULE.InputProblem):
            self.report()
        self.data['quotes'][1]['id'] = 'B'
        self.data['quotes'][0]['finance']['fee_outside_total'] = '0'
        with self.assertRaises(MODULE.InputProblem):
            self.report()

    def test_schema_boolean_rejected(self):
        self.data['schema_version'] = True
        with self.assertRaises(MODULE.InputProblem):
            self.report()

    def test_exactly_two_quotes_required(self):
        for count in (0, 1, 3):
            data = copy.deepcopy(self.data)
            data['quotes'] = [copy.deepcopy(data['quotes'][0]) for _ in range(count)]
            with self.assertRaises(MODULE.InputProblem):
                self.report(data)

    def test_energy_mixed_and_uniform_exact(self):
        report = self.report()
        self.assertEqual(report['quotes'][0]['annual_energy']['value'], '1755')
        self.assertEqual(report['quotes'][1]['annual_energy']['value'], '1755')
        self.assertEqual(self.comparison(report, 'annual_energy')['right_minus_left'], '0')

    def test_energy_mode_conflict_rejected(self):
        self.data['quotes'][0]['energy']['unit_price'] = '0.8'
        with self.assertRaises(MODULE.InputProblem):
            self.report()

    def test_energy_unknown_share_stays_null(self):
        del self.data['quotes'][0]['energy']['home_share']
        energy = self.report()['quotes'][0]['annual_energy']
        self.assertIsNone(energy['value'])
        self.assertIsNone(energy['known_subtotal'])
        self.assertFalse(energy['complete'])

    def test_energy_positive_consumption_and_bounded_share(self):
        for key, value in (('consumption_per_100', '0'), ('home_share', '1.1')):
            with self.subTest(key=key):
                data = copy.deepcopy(self.data)
                data['quotes'][0]['energy'][key] = value
                with self.assertRaises(MODULE.InputProblem):
                    self.report(data)

    def test_zero_annual_mileage_is_zero_cost(self):
        self.data['quotes'][0]['energy']['annual_km'] = 0
        self.assertEqual(self.report()['quotes'][0]['annual_energy']['value'], '0')

    def test_unequal_annual_mileage_no_energy_comparison(self):
        self.data['quotes'][0]['energy']['annual_km'] = 1
        comparison = self.comparison(self.report(), 'annual_energy')
        self.assertFalse(comparison['comparable'])
        self.assertIn('年里程不同', comparison['reason'])

    def test_csv_makes_missing_value_explicit_and_escapes_label(self):
        self.data['quotes'][0]['id'] = '=FORMULA()'
        rows = list(csv.DictReader(io.StringIO(MODULE.render_csv(self.report()))))
        finance = next(r for r in rows if r['scope'] == 'finance_fee')
        self.assertEqual(finance['left_id'], "'=FORMULA()")
        self.assertEqual(finance['right_value'], '')
        self.assertEqual(finance['right_complete'], 'False')
        self.assertEqual(finance['right_known_subtotal'], '10500')

    def test_markdown_escapes_untrusted_source_markup(self):
        self.data['quotes'][0]['source'] = '<script>alert(1)</script>|bad'
        text = MODULE.render_markdown(self.report())
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)
        self.assertIn('&#124;', text)


class QuoteFileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'quotes.json'
        self.input.write_bytes((BASE / 'examples/two-quotes-missing-fee.json').read_bytes())
        self.out = self.root / 'report'

    def cli(self, *extra, input=None, out=None):
        before = hashlib.sha256(self.input.read_bytes()).hexdigest()
        result = subprocess.run([sys.executable, '-B', str(COMPARE), '--input', str(input or self.input), '--out-dir', str(out or self.out), *extra], text=True, capture_output=True)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(), before)
        return result

    def test_outputs_and_input_hash_match(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ['comparison.csv', 'comparison.json', 'comparison.md'])
        report = json.loads((self.out / 'comparison.json').read_text())
        self.assertEqual(report['input_sha256'], hashlib.sha256(self.input.read_bytes()).hexdigest())
        self.assertEqual(report['quotes'][0]['provenance']['/quotes/0/finance/principal']['source'], '合成报价 A：无真实商家、车型或个人数据')

    def test_input_as_output_directory_preserved(self):
        self.assertEqual(self.cli(out=self.input).returncode, 1)

    def test_existing_report_directory_preserved(self):
        self.out.mkdir()
        old = self.out / 'comparison.json'
        old.write_text('old report')
        self.assertEqual(self.cli().returncode, 1)
        self.assertEqual(old.read_text(), 'old report')
        self.assertEqual(list(self.out.iterdir()), [old])

    def test_symlink_output_not_followed(self):
        self.out.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.cli().returncode, 1)
        self.assertFalse((self.root / 'comparison.json').exists())
        self.assertTrue(self.out.is_symlink())

    def test_symlink_input_rejected(self):
        link = self.root / 'link.json'
        link.symlink_to(self.input)
        self.assertEqual(self.cli(input=link).returncode, 1)
        self.assertFalse(self.out.exists())

    def test_duplicate_json_key_fails_without_reports(self):
        self.input.write_text('{"schema_version":1,"schema_version":1,"quotes":[]}')
        self.assertEqual(self.cli().returncode, 1)
        self.assertFalse(self.out.exists())

    def test_raw_nonfinite_json_fails_without_reports(self):
        self.input.write_text('{"schema_version":1,"quotes":[NaN,Infinity]}')
        self.assertEqual(self.cli().returncode, 1)
        self.assertFalse(self.out.exists())

    def test_bad_json_type_and_encoding_fail_cleanly(self):
        for value in (b'[]', b'{', b'\xff'):
            self.input.write_bytes(value)
            self.assertEqual(self.cli().returncode, 1)
            self.assertFalse(self.out.exists())

    def test_duplicate_cli_parameter_rejected(self):
        self.assertNotEqual(self.cli('--input', str(self.input)).returncode, 0)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
