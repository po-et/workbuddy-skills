"""Conservative coverage and test-path evidence using synthetic files only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/test-coverage-gap/scripts/test_coverage_gap.py'
spec = importlib.util.spec_from_file_location('coverage_mapping_under_test', SCRIPT)
coverage_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage_module)


def stats(rate):
    return {'lines': 1, 'covered': int(rate > 0), 'rate': rate}


class PathEvidenceTests(unittest.TestCase):
    def test_longest_suffix_tie_does_not_pick_first(self):
        cov = {'left/x.py': stats(1), 'right/x.py': stats(0)}
        evidence = coverage_module.match_coverage('src/x.py', cov)
        self.assertEqual(evidence['confidence'], 'ambiguous')
        self.assertIsNone(evidence['matched_path'])
        self.assertEqual(evidence['candidates'], ['left/x.py', 'right/x.py'])

    def test_tie_evidence_independent_of_input_order(self):
        first = {'left/x.py': stats(1), 'right/x.py': stats(0)}
        second = dict(reversed(list(first.items())))
        self.assertEqual(coverage_module.match_coverage('src/x.py', first),
                         coverage_module.match_coverage('src/x.py', second))

    def test_unique_longest_suffix_retains_confidence(self):
        cov = {'other/x.py': stats(0), '/workspace/src/x.py': stats(1)}
        evidence = coverage_module.match_coverage('src/x.py', cov)
        self.assertEqual(evidence['confidence'], 'suffix_unique')
        self.assertEqual(evidence['matched_path'], '/workspace/src/x.py')
        self.assertEqual(evidence['suffix_components'], 2)

    def test_exact_match_wins_and_preserves_zero(self):
        cov = {'src/x.py': stats(0), 'elsewhere/x.py': stats(1)}
        evidence = coverage_module.match_coverage('./src/x.py', cov)
        self.assertEqual(evidence['confidence'], 'exact')
        self.assertEqual(cov[evidence['matched_path']]['rate'], 0)

    def test_windows_separators_normalized_without_case_folding(self):
        evidence = coverage_module.match_coverage('src/x.py', {'src\\x.py': stats(1)})
        self.assertEqual(evidence['confidence'], 'exact')
        self.assertEqual(coverage_module.match_coverage('src/X.py', {'src/x.py': stats(1)})['confidence'], 'unmatched')

    def test_one_report_entry_cannot_cover_two_module_sources(self):
        result = coverage_module.coverage_matches(['moduleA/src/user.py', 'moduleB/src/user.py'],
                                                  {'user.py': stats(1)})
        self.assertEqual([result[p]['confidence'] for p in sorted(result)], ['ambiguous', 'ambiguous'])
        self.assertTrue(all(result[p]['matched_path'] is None for p in result))

    def test_exact_source_keeps_ownership_of_shared_report_candidate(self):
        result = coverage_module.coverage_matches(['src/user.py', 'moduleB/src/user.py'],
                                                  {'src/user.py': stats(1)})
        self.assertEqual(result['src/user.py']['confidence'], 'exact')
        self.assertEqual(result['moduleB/src/user.py']['confidence'], 'ambiguous')

    def test_twin_module_test_name_does_not_hide_other_module(self):
        result = coverage_module.test_matches(['moduleA/src/user.py', 'moduleB/src/user.py'],
                                               [('moduleA/tests/test_user.py', 'test_user.py')])
        self.assertEqual(result['moduleA/src/user.py']['confidence'], 'convention_unique')
        self.assertEqual(result['moduleB/src/user.py']['confidence'], 'unmatched')
        self.assertFalse(result['moduleA/src/user.py']['execution_proven'])

    def test_root_test_is_ambiguous_for_two_collapsed_source_paths(self):
        result = coverage_module.test_matches(['src/user.py', 'lib/user.py'],
                                               [('tests/test_user.py', 'test_user.py')])
        self.assertEqual(result['src/user.py']['confidence'], 'ambiguous')
        self.assertEqual(result['lib/user.py']['confidence'], 'ambiguous')

    def test_explicit_prefix_mapping_clears_matching_uncertainty(self):
        mapped = coverage_module.map_prefixes({'/build/app/user.py': stats(0)}, ['/build/app=src'])
        self.assertEqual(coverage_module.match_coverage('src/user.py', mapped)['confidence'], 'exact')

    def test_dot_report_root_and_longest_mapping(self):
        mapped = coverage_module.map_prefixes({'app/user.py': stats(1)}, ['.=src', 'app=moduleA/src'])
        self.assertIn('moduleA/src/user.py', mapped)
        self.assertEqual(coverage_module.map_prefixes({'user.py': stats(1)}, ['.=src']), {'src/user.py': stats(1)})

    def test_conflicting_prefix_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, '映射冲突'):
            coverage_module.map_prefixes({'/build/x.py': stats(1)}, ['/build=src', '/build=other'])
        with self.assertRaisesRegex(ValueError, '覆盖率冲突'):
            coverage_module.map_prefixes({'left/x.py': stats(1), 'right/x.py': stats(0)}, ['left=src', 'right=src'])


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='coverage-parser-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def write(self, filename, text):
        target = self.base / filename
        target.write_text(text, encoding='utf-8')
        return str(target)

    def xml(self, content):
        return self.write('coverage.xml', '<coverage><packages><package><classes>' + content + '</classes></package></packages></coverage>')

    def test_lcov_valid_hundred_and_zero_percent(self):
        path = self.write('lcov.info', 'SF:src/paid.py\nDA:1,3\nLF:1\nLH:1\nend_of_record\nSF:src/refund.py\nDA:2,0\nLF:1\nLH:0\nend_of_record\n')
        cov, kind = coverage_module.load_coverage(path)
        self.assertEqual(kind, 'lcov')
        self.assertEqual(cov['src/paid.py']['rate'], 1)
        self.assertEqual(cov['src/refund.py']['rate'], 0)

    def test_lcov_identical_duplicate_line_deduplicated(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:1,1\nDA:1,1\nLF:1\nLH:1\nend_of_record\n')
        self.assertEqual(coverage_module.parse_lcov(path)['x.py']['lines'], 1)

    def test_lcov_duplicate_conflicting_line_rejected(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:1,1\nDA:1,0\nend_of_record\n')
        with self.assertRaisesRegex(ValueError, '冲突'):
            coverage_module.load_coverage(path)

    def test_lcov_duplicate_conflicting_records_rejected(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:1,1\nend_of_record\nSF:./x.py\nDA:1,0\nend_of_record\n')
        with self.assertRaisesRegex(ValueError, '冲突'):
            coverage_module.load_coverage(path)

    def test_lcov_invalid_hits_rejected(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:1,-1\nend_of_record\n')
        with self.assertRaisesRegex(ValueError, '非负整数'):
            coverage_module.load_coverage(path)

    def test_lcov_summary_conflict_rejected(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:1,0\nLF:1\nLH:1\nend_of_record\n')
        with self.assertRaisesRegex(ValueError, '冲突'):
            coverage_module.load_coverage(path)

    def test_lcov_missing_end_rejected(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:1,1\n')
        with self.assertRaisesRegex(ValueError, 'end_of_record'):
            coverage_module.load_coverage(path)

    def test_lcov_empty_population_is_unknown(self):
        path = self.write('lcov.info', 'SF:x.py\nLF:0\nLH:0\nend_of_record\n')
        self.assertIsNone(coverage_module.load_coverage(path)[0]['x.py']['rate'])

    def test_lcov_invalid_record_rejected(self):
        path = self.write('lcov.info', 'SF:x.py\nDA:bad\nend_of_record\n')
        with self.assertRaisesRegex(ValueError, 'DA 格式'):
            coverage_module.load_coverage(path)

    def test_cobertura_line_details_computed(self):
        path = self.xml('<class filename="src/x.py" line-rate="0.5"><lines><line number="1" hits="1"/><line number="2" hits="0"/></lines></class>')
        self.assertEqual(coverage_module.parse_cobertura(path)['src/x.py'], {'lines': 2, 'covered': 1, 'rate': .5})

    def test_cobertura_summary_fraction_not_promoted_to_hundred(self):
        path = self.xml('<class filename="src/x.py" line-rate="0.5"/>')
        self.assertEqual(coverage_module.parse_cobertura(path)['src/x.py'], {'lines': None, 'covered': None, 'rate': .5})

    def test_cobertura_missing_rate_is_unknown(self):
        path = self.xml('<class filename="src/x.py"><lines/></class>')
        self.assertIsNone(coverage_module.parse_cobertura(path)['src/x.py']['rate'])

    def test_cobertura_duplicate_identical_details_deduplicated(self):
        item = '<class filename="src/x.py"><lines><line number="1" hits="1"/></lines></class>'
        self.assertEqual(coverage_module.parse_cobertura(self.xml(item + item))['src/x.py']['lines'], 1)

    def test_cobertura_duplicate_conflicting_entries_rejected(self):
        path = self.xml('<class filename="x.py"><line number="1" hits="1"/></class><class filename="./x.py"><line number="1" hits="0"/></class>')
        with self.assertRaisesRegex(ValueError, '冲突'):
            coverage_module.load_coverage(path)

    def test_cobertura_missing_filename_rejected(self):
        with self.assertRaisesRegex(ValueError, 'filename'):
            coverage_module.load_coverage(self.xml('<class line-rate="1"/>'))

    def test_cobertura_invalid_rate_rejected(self):
        with self.assertRaisesRegex(ValueError, '0 到 1'):
            coverage_module.load_coverage(self.xml('<class filename="x.py" line-rate="NaN"/>'))

    def test_xml_invalid_structure_rejected(self):
        with self.assertRaisesRegex(ValueError, '解析失败'):
            coverage_module.load_coverage(self.write('coverage.xml', '<coverage>'))
        with self.assertRaisesRegex(ValueError, '没有文件'):
            coverage_module.load_coverage(self.write('coverage.xml', '<coverage/>'))

    def test_xml_dtd_entity_declarations_rejected(self):
        path = self.write('coverage.xml', '<!DOCTYPE coverage [<!ENTITY secret SYSTEM "file:///not-read">]><coverage/>')
        with self.assertRaisesRegex(ValueError, 'DTD'):
            coverage_module.load_coverage(path)

    def test_external_cobertura_doctype_does_not_load_external_file(self):
        declaration = '<!DOCTYPE coverage SYSTEM "file:///nonexistent-synthetic-dtd-not-loaded">'
        body = '<coverage><class filename="x.py"><line number="1" hits="1"/></class></coverage>'
        path = self.write('coverage.xml', declaration + body)
        self.assertEqual(coverage_module.load_coverage(path)[0]['x.py']['rate'], 1)

    def test_xml_utf16_entity_declarations_rejected_before_parse(self):
        path = self.base / 'coverage.xml'
        path.write_bytes('<!DOCTYPE coverage [<!ENTITY secret "expanded">]><coverage/>'.encode('utf-16'))
        with self.assertRaisesRegex(ValueError, '空字节'):
            coverage_module.load_coverage(str(path))


class CoverageCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='coverage-cli-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def write(self, name, text='value = 1\n'):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def report(self, records):
        body = ''.join(f'SF:{path}\nDA:1,{hit}\nend_of_record\n' for path, hit in records)
        return self.write('lcov.info', body)

    def cli(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), '.', '--days', '0', '--min-lines', '1', '--json', *args],
                                cwd=self.base, capture_output=True, text=True, timeout=15)
        self.assertNotIn('Traceback', result.stderr)
        data = json.loads(result.stdout) if result.stdout.strip() else None
        return result, data

    def test_twin_module_one_test_leaves_other_gap(self):
        self.write('moduleA/src/user.py')
        self.write('moduleB/src/user.py')
        self.write('moduleA/tests/test_user.py', '# Synthetic naming signal, not executed.\n')
        result, data = self.cli()
        self.assertEqual(result.returncode, 0)
        self.assertEqual([gap['file'] for gap in data['gaps']], ['moduleB/src/user.py'])
        self.assertFalse(data['source_findings'][0]['test_mapping']['execution_proven'])

    def test_strict_longest_suffix_tie_cannot_pass(self):
        self.write('src/x.py')
        self.report([('left/x.py', 1), ('right/x.py', 0)])
        result, data = self.cli('--coverage', 'lcov.info', '--strict')
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(data['gaps'][0]['coverage'])
        self.assertEqual(data['coverage_unknown'][0]['confidence'], 'ambiguous')
        self.assertEqual(data['zero_coverage'], [])

    def test_missing_coverage_is_unknown_even_with_named_test(self):
        self.write('src/user.py')
        self.write('tests/test_user.py')
        self.report([('src/other.py', 1)])
        result, data = self.cli('--coverage', 'lcov.info', '--strict')
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(data['source_findings'][0]['coverage'])
        self.assertEqual(data['zero_coverage'], [])
        self.assertEqual(data['summary']['unknown'], 1)

    def test_exact_hundred_passes_strict(self):
        self.write('src/user.py')
        self.report([('src/user.py', 1)])
        result, data = self.cli('--coverage', 'lcov.info', '--strict')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data['total_coverage'], 100)
        self.assertEqual(data['source_findings'][0]['coverage_mapping']['confidence'], 'exact')

    def test_exact_zero_blocks_despite_named_test(self):
        self.write('src/user.py')
        self.write('tests/test_user.py')
        self.report([('src/user.py', 0)])
        result, data = self.cli('--coverage', 'lcov.info', '--strict')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data['gaps'], [])
        self.assertEqual(data['zero_coverage'][0]['coverage'], 0)

    def test_malformed_lcov_errors_nonzero_without_json_success(self):
        self.write('src/user.py')
        self.write('lcov.info', 'SF:src/user.py\nDA:1,nonsense\nend_of_record\n')
        result, data = self.cli('--coverage', 'lcov.info')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(data)

    def test_malformed_xml_errors_nonzero(self):
        self.write('coverage.xml', '<coverage>')
        result, data = self.cli('--coverage', 'coverage.xml')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(data)

    def test_explicit_mapping_generates_exact_readonly_evidence_and_markdown(self):
        source = self.write('src/user.py')
        test = self.write('tests/test_user.py', '# Never execute tests or alter inputs.\n')
        report = self.report([('/worker/app/user.py', 1)])
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, test, report)}
        result, data = self.cli('--coverage', 'lcov.info', '--coverage-map', '/worker/app=src', '--strict', '--output', 'report.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['source_findings'][0]['coverage_mapping']['confidence'], 'exact')
        self.assertIn('测试文件名匹配是线索', (self.base / 'report.md').read_text())
        self.assertEqual(before, {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, test, report)})

    def test_output_cannot_overwrite_source_or_coverage(self):
        self.write('src/user.py')
        self.report([('src/user.py', 1)])
        for target in ('src/user.py', 'lcov.info'):
            with self.subTest(target=target):
                before = (self.base / target).read_bytes()
                result, data = self.cli('--coverage', 'lcov.info', '--output', target)
                self.assertEqual(result.returncode, 2)
                self.assertIsNone(data)
                self.assertEqual(before, (self.base / target).read_bytes())

    def test_deterministic_json_after_report_record_reordering(self):
        self.write('src/x.py')
        self.report([('right/x.py', 0), ('left/x.py', 1)])
        first, _ = self.cli('--coverage', 'lcov.info')
        self.report([('left/x.py', 1), ('right/x.py', 0)])
        second, _ = self.cli('--coverage', 'lcov.info')
        self.assertEqual(first.stdout, second.stdout)

    def test_no_report_does_not_invent_zero_coverage(self):
        self.write('src/user.py')
        result, data = self.cli('--strict')
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(data['total_coverage'])
        self.assertIsNone(data['source_findings'][0]['coverage'])
        self.assertEqual(data['zero_coverage'], [])
        self.assertEqual(data['coverage_unknown'], [])

    def test_invalid_cli_threshold_is_input_error(self):
        result, data = self.cli('--min-cov', 'nan')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(data)


if __name__ == '__main__':
    unittest.main()
