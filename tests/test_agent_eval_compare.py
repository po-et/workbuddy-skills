"""Meaningful offline regression tests for recorded agent-eval comparisons."""

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/agent-engineering-expert"
SCRIPT = SKILL / "scripts/agent_eval_compare.py"


class AgentEvalCompareTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-eval-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.sequence = 0

    @staticmethod
    def record(case_id="a", passed=True, **extra):
        return {"case_id": case_id, "passed": passed, "evidence": "synthetic: recorded assertion", **extra}

    def run_text(self, before, after, out_exists=False):
        self.sequence += 1
        run = self.directory / str(self.sequence)
        run.mkdir()
        before_file, after_file = run / "before.jsonl", run / "after.jsonl"
        before_file.write_text(before, encoding="utf-8")
        after_file.write_text(after, encoding="utf-8")
        original = {path: path.read_bytes() for path in (before_file, after_file)}
        out_dir = run / "out"
        if out_exists:
            out_dir.mkdir()
            (out_dir / "comparison.json").write_text("existing report", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--before", str(before_file),
             "--after", str(after_file), "--out-dir", str(out_dir)],
            text=True, capture_output=True, timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content, "input files must stay unchanged")
        self.assertNotIn("Traceback", proc.stderr)
        report = None
        if proc.returncode in (0, 1):
            report = json.loads((out_dir / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(report["exit_code"], proc.returncode)
            self.assertTrue((out_dir / "comparison.md").is_file())
        return proc, report, out_dir

    def run_rows(self, before, after, **kwargs):
        lines = lambda rows: "\n".join(json.dumps(row) for row in rows) + "\n"
        return self.run_text(lines(before), lines(after), **kwargs)

    def assert_invalid(self, before, after, error):
        proc, report, out_dir = self.run_text(before, after)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn(error, proc.stderr)
        self.assertIsNone(report)
        self.assertFalse(out_dir.exists(), "invalid input must not create reports")

    def test_complete_comparison_pairs_by_id_not_order(self):
        before = [self.record("a", False), self.record("b", True)]
        after = [self.record("b", True), self.record("a", True)]
        proc, report, _ = self.run_rows(before, after)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(report["comparison_complete"])
        self.assertEqual(report["paired"]["recorded_pass_count_delta"], 1)
        self.assertEqual(report["paired"]["newly_passed_with_both_evidence"], ["a"])
        self.assertTrue(report["pass_gain_supported_for_recorded_case_set"])

    def test_complete_unchanged_failures_are_not_an_improvement(self):
        proc, report, _ = self.run_rows([self.record(passed=False)], [self.record(passed=False)])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(report["paired"]["unchanged_failed"], ["a"])
        self.assertFalse(report["pass_gain_supported_for_recorded_case_set"])

    def test_any_regression_gates_even_when_overall_pass_count_increases(self):
        before = [self.record("a", True), self.record("b", False), self.record("c", False)]
        after = [self.record("a", False), self.record("b", True), self.record("c", True)]
        proc, report, _ = self.run_rows(before, after)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["paired"]["recorded_pass_count_delta"], 1)
        self.assertEqual(report["paired"]["regressions_true_to_false"], ["a"])
        self.assertFalse(report["pass_gain_supported_for_recorded_case_set"])

    def test_missing_cases_are_unpaired_not_newly_passed(self):
        before = [self.record("a", False), self.record("removed", False)]
        after = [self.record("a", True), self.record("added", True)]
        proc, report, _ = self.run_rows(before, after)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(report["comparison_complete"])
        self.assertEqual(report["missing"]["missing_after_case_ids"], ["removed"])
        self.assertEqual(report["missing"]["missing_before_case_ids"], ["added"])
        self.assertEqual(report["paired"]["recorded_false_to_true"], ["a"])
        self.assertFalse(report["pass_gain_supported_for_recorded_case_set"])

    def test_no_shared_cases_has_unknown_rates(self):
        proc, report, _ = self.run_rows([self.record("a")], [self.record("b")])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["paired"]["case_count"], 0)
        self.assertIsNone(report["paired"]["recorded_before_pass_rate"])
        self.assertIsNone(report["metrics"]["cost"]["before_mean_on_metric_pairs"])

    def test_missing_or_blank_evidence_blocks_gain_claim(self):
        for evidence in (None, "", " \t "):
            with self.subTest(evidence=evidence):
                before = self.record(passed=False)
                if evidence is None:
                    before.pop("evidence")
                else:
                    before["evidence"] = evidence
                proc, report, _ = self.run_rows([before], [self.record(passed=True)])
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(report["paired"]["recorded_false_to_true"], ["a"])
                self.assertEqual(report["paired"]["newly_passed_with_both_evidence"], [])
                self.assertFalse(report["pass_gain_supported_for_recorded_case_set"])

    def test_regression_is_recorded_even_without_evidence(self):
        before = self.record(evidence="")
        proc, report, _ = self.run_rows([before], [self.record(passed=False)])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["paired"]["regressions_true_to_false"], ["a"])
        self.assertFalse(report["comparison_complete"])

    def test_missing_metrics_are_unknown_and_means_use_only_metric_pairs(self):
        before = [self.record("a", latency_ms=100, cost=0.1), self.record("b", latency_ms=900)]
        after = [self.record("a", latency_ms=50), self.record("b", cost=0.2)]
        proc, report, _ = self.run_rows(before, after)
        self.assertEqual(proc.returncode, 0)
        latency = report["metrics"]["latency_ms"]
        self.assertEqual(latency["recorded_before_count"], 2)
        self.assertEqual(latency["recorded_after_count"], 1)
        self.assertEqual(latency["paired_metric_case_ids"], ["a"])
        self.assertEqual(Decimal(latency["before_mean_on_metric_pairs"]), Decimal(100))
        self.assertEqual(Decimal(latency["after_mean_on_metric_pairs"]), Decimal(50))
        self.assertFalse(latency["whole_comparison_metric_coverage_complete"])
        cost = report["metrics"]["cost"]
        self.assertEqual(cost["paired_with_metric_count"], 0)
        self.assertIsNone(cost["mean_delta_after_minus_before"])

    def test_actual_zero_metrics_are_preserved(self):
        proc, report, _ = self.run_rows([self.record(latency_ms=0, cost=0)],
                                        [self.record(latency_ms=0, cost=0)])
        self.assertEqual(proc.returncode, 0)
        for metric in report["metrics"].values():
            self.assertEqual(metric["before_mean_on_metric_pairs"], "0")
            self.assertEqual(metric["mean_delta_after_minus_before"], "0")
            self.assertTrue(metric["whole_comparison_metric_coverage_complete"])

    def test_decimal_cost_difference_keeps_recorded_decimal_values(self):
        proc, report, _ = self.run_rows([self.record(cost=0.1), self.record("b", cost=0.2)],
                                        [self.record(cost=0.2), self.record("b", cost=0.3)])
        self.assertEqual(proc.returncode, 0)
        cost = report["metrics"]["cost"]
        self.assertEqual(Decimal(cost["before_mean_on_metric_pairs"]), Decimal("0.15"))
        self.assertEqual(Decimal(cost["after_mean_on_metric_pairs"]), Decimal("0.25"))
        self.assertEqual(Decimal(cost["mean_delta_after_minus_before"]), Decimal("0.10"))

    def test_unpaired_metrics_do_not_enter_paired_average(self):
        proc, report, _ = self.run_rows([self.record(latency_ms=100), self.record("b", latency_ms=9999)],
                                        [self.record(latency_ms=50)])
        self.assertEqual(proc.returncode, 1)
        metric = report["metrics"]["latency_ms"]
        self.assertEqual(metric["recorded_before_count"], 2)
        self.assertEqual(Decimal(metric["before_mean_on_metric_pairs"]), Decimal(100))
        self.assertFalse(metric["whole_comparison_metric_coverage_complete"])

    def test_duplicate_case_ids_are_rejected_with_line_number(self):
        line = json.dumps(self.record())
        self.assert_invalid(line + "\n" + line, line, "before.jsonl:2: duplicate case_id")

    def test_duplicate_json_keys_are_rejected(self):
        self.assert_invalid('{"case_id":"a","passed":false,"passed":true}',
                            json.dumps(self.record()), "duplicate JSON key: passed")

    def test_integer_one_is_not_boolean_passed(self):
        for value in (0, 1, "true", None, [], {}):
            with self.subTest(value=value):
                self.assert_invalid(json.dumps(self.record(passed=value)),
                                    json.dumps(self.record()), "passed must be JSON true or false")

    def test_nan_infinity_and_numeric_overflow_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(value=value):
                text = '{"case_id":"a","passed":true,"latency_ms":' + value + '}'
                self.assert_invalid(text, json.dumps(self.record()), "finite")

    def test_negative_or_wrong_type_metrics_are_rejected(self):
        for metric in ("latency_ms", "cost"):
            for value in (-0.01, -1, True, False, "1", None):
                with self.subTest(metric=metric, value=value):
                    text = json.dumps(self.record(**{metric: value}))
                    self.assert_invalid(text, json.dumps(self.record()), metric)

    def test_malformed_json_or_nonobject_lines_are_rejected(self):
        for text in ('{"case_id":"a",', '[]', 'null', '"record"', 'true'):
            with self.subTest(text=text):
                self.assert_invalid(text, json.dumps(self.record()), "before.jsonl:1")

    def test_excessively_nested_json_is_reported_without_traceback(self):
        text = '{"case_id":"a","passed":true,"extra":' + '[' * 1500 + '0' + ']' * 1500 + '}'
        self.assert_invalid(text, json.dumps(self.record()), "before.jsonl:1")

    def test_unpaired_unicode_surrogates_are_rejected_before_output_creation(self):
        for row in (self.record("a\ud800"), self.record(evidence="\ud800")):
            with self.subTest(row=row):
                self.assert_invalid(json.dumps(row), json.dumps(self.record()), "before.jsonl:1")

    def test_missing_required_fields_and_invalid_id_are_rejected(self):
        rows = [{"passed": True}, {"case_id": "a"}, self.record(""), self.record(" a"),
                self.record("a\n"), self.record(1), self.record("a\x00b")]
        for row in rows:
            with self.subTest(row=row):
                self.assert_invalid(json.dumps(row), json.dumps(self.record()), "before.jsonl:1")

    def test_wrong_type_evidence_and_typo_fields_are_rejected(self):
        for row in (self.record(evidence=None), self.record(evidence=1), self.record(latency=100)):
            with self.subTest(row=row):
                self.assert_invalid(json.dumps(row), json.dumps(self.record()), "before.jsonl:1")

    def test_empty_inputs_are_invalid(self):
        self.assert_invalid("\n  \n", json.dumps(self.record()), "no case records")

    def test_bom_and_blank_lines_do_not_change_pairing(self):
        row = json.dumps(self.record())
        proc, report, _ = self.run_text("\ufeff\n" + row + "\n\n", row)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["paired"]["case_ids"], ["a"])

    def test_existing_output_is_refused_and_preserved(self):
        proc, _, out = self.run_rows([self.record()], [self.record()], out_exists=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("refusing overwrite", proc.stderr)
        self.assertEqual((out / "comparison.json").read_text(), "existing report")
        self.assertFalse((out / "comparison.md").exists())

    def test_hashes_identify_actual_unchanged_input_bytes(self):
        proc, report, _ = self.run_rows([self.record()], [self.record(passed=False)])
        self.assertEqual(proc.returncode, 1)
        for source in report["inputs"].values():
            actual = hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest()
            self.assertEqual(source["sha256"], actual)

    def test_markdown_escapes_untrusted_record_text(self):
        evidence = '<script>alert(1)</script> | [fake](https://example.test)\nnext'
        proc, _, out = self.run_rows([self.record(evidence=evidence)], [self.record(evidence=evidence)])
        self.assertEqual(proc.returncode, 0)
        markdown = (out / "comparison.md").read_text()
        self.assertNotIn("<script>", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertNotIn("[fake](https://example.test)", markdown)

    def test_bundled_synthetic_fixtures_have_three_cases_and_partial_metrics(self):
        before = (SKILL / "assets/before.jsonl").read_text()
        after = (SKILL / "assets/after.jsonl").read_text()
        proc, report, out = self.run_text(before, after)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["paired"]["case_count"], 3)
        self.assertEqual(report["paired"]["recorded_before_pass_count"], 2)
        self.assertEqual(report["paired"]["recorded_after_pass_count"], 3)
        for metric in report["metrics"].values():
            self.assertEqual(metric["paired_with_metric_count"], 2)
            self.assertFalse(metric["whole_comparison_metric_coverage_complete"])
        rows = (out / "comparison.md").read_text().splitlines()
        index = rows.index("|---|---:|---:|---:|---:|---:|---:|")
        self.assertTrue(rows[index + 1].startswith("| latency_ms |"))
        self.assertTrue(rows[index + 2].startswith("| cost |"))


if __name__ == "__main__":
    unittest.main()
