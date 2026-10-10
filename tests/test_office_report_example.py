"""Synthetic office workflow regressions; requires existing openpyxl only."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    import openpyxl
except ImportError:
    openpyxl = None

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "examples/office-report/run_demo.py"


class ReportDerivationTest(unittest.TestCase):
    def demo(self):
        spec = importlib.util.spec_from_file_location("office_demo", RUNNER)
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        return demo

    def test_report_conclusion_and_period_are_derived_from_actual_summary(self):
        demo = self.demo()
        rows = [dict(zip(demo.FIELDS, (month, "华东", "线上", "A", 10, 1, amount)))
                for month, amount in (("2027-06", "1000.01"), ("2027-07", "700.01"))]
        summary = demo.aggregate_rows(rows)
        checks = {"source_rows": 2, "merged_rows": 2, "provenance_rows_verified": 2,
                  "known_sales_source": "1700.02", "sources": []}
        flagged = [{"维度": "华东/线上", "期": "2027-07", "销售额": "700.01", "环比": "-30.0%", "标记": "▼"}]
        text = demo.report(summary, checks, flagged, [])
        self.assertIn("2027 年 7 月", text)
        self.assertIn("1,000.01", text)
        self.assertIn("700.01", text)
        self.assertNotIn("2,000.02", text)
        self.assertNotIn("72 行", text)
        self.assertNotIn("华西/线上存在", text)

    def test_missing_sales_does_not_claim_missing_refunds_or_unknown_rate(self):
        demo = self.demo()
        rows = [dict(zip(demo.FIELDS, (month, "华西", "线上", "A", 10, 1, amount)))
                for month, amount in (("2027-06", "1000.01"), ("2027-07", None))]
        rows[-1].update({"来源文件": "/tmp/west.xlsx", "来源工作表": "明细", "来源行": 2})
        summary = demo.aggregate_rows(rows)
        checks = {"source_rows": 2, "merged_rows": 2, "provenance_rows_verified": 2,
                  "known_sales_source": "1000.01", "sources": []}
        text = demo.report(summary, checks, [], [rows[-1]])
        self.assertIn("缺失销售额", text)
        self.assertNotIn("缺失销售额及退款数", text)
        self.assertNotIn("销售额与退款率暂不能下结论", text)
        self.assertIn("| 退款率（总退款数/总订单数） | 10.00% | 10.00% |", text)


@unittest.skipUnless(openpyxl is not None, "requires existing openpyxl")
class OfficeWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-office-test-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "new-run"

    def run_demo(self):
        proc = subprocess.run([sys.executable, str(RUNNER), "--out-dir", str(self.output)],
                              text=True, capture_output=True, timeout=45,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        return proc

    def assert_success(self):
        proc = self.run_demo()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        return json.loads((self.output / "verification.json").read_text())

    def test_real_chain_preserves_sources_and_reordered_headers(self):
        check = self.assert_success()
        self.assertTrue(check["synthetic_demo"])
        self.assertEqual(check["source_rows"], 72)
        self.assertEqual(check["merged_rows"], 72)
        self.assertEqual(check["provenance_rows_verified"], 72)
        self.assertTrue(check["source_hashes_unchanged"])
        self.assertTrue(all(row["sha256_before"] == row["sha256_after"] for row in check["sources"]))
        self.assertEqual([step["exit_code"] for step in check["steps"]], [0, 0, 0])
        self.assertIn("合成演示", (self.output / "report.md").read_text())
        with (self.output / "details.csv").open(encoding="utf-8-sig", newline="") as f:
            details = list(csv.DictReader(f))
        self.assertEqual(len(details), 72)
        self.assertTrue(all(row["来源工作表"] == "明细" for row in details))

    def test_refund_rate_is_weighted_and_missing_is_not_zero(self):
        self.assert_success()
        data = json.loads((self.output / "summary.json").read_text())
        months = {row["month"]: row for row in data["monthly"]}
        self.assertEqual(months["2026-08"]["orders"], 400)
        self.assertEqual(months["2026-08"]["refunds"], 12)
        self.assertEqual(months["2026-08"]["refund_rate"], "0.03")
        self.assertNotEqual(months["2026-08"]["refund_rate"], "0.05875")
        self.assertEqual(months["2026-09"]["orders"], 390)
        self.assertIsNone(months["2026-09"]["refunds"])
        self.assertIsNone(months["2026-09"]["refund_rate"])
        self.assertIsNone(months["2026-09"]["sales"])
        self.assertEqual(months["2026-09"]["known_sales"], "32050.09")
        profile = (self.output / "profile.txt").read_text()
        self.assertIn("缺失不等于 0", profile)
        self.assertNotIn("需要处理：没有发现常见问题", profile)

    def test_decimal_money_reconciles_to_independent_source_total(self):
        check = self.assert_success()
        self.assertEqual(check["known_sales_source"], "312050.89")
        self.assertEqual(check["known_sales_merged"], "312050.89")
        self.assertEqual(check["known_sales_grouped"], "312050.89")
        data = json.loads((self.output / "summary.json").read_text())
        groups = {(r["month"], r["region"], r["channel"]): r for r in data["groups"]}
        self.assertEqual(groups[("2026-09", "华东", "线上")]["sales"], "800.02")
        west = groups[("2026-09", "华西", "线上")]
        self.assertIsNone(west["sales"])
        self.assertEqual(west["known_sales"], "5250.03")

    def test_fixed_rules_flag_drop_without_treating_missing_as_drop(self):
        check = self.assert_success()
        self.assertEqual(check["anomaly_count"], 1)
        self.assertEqual(check["missing_sales_rows"], 1)
        with (self.output / "anomalies.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([(r["维度"], r["期"], r["标记"]) for r in rows if r["标记"]],
                         [("华东/线上", "2026-09", "▼")])
        missing = next(r for r in rows if r["维度"] == "华西/线上" and r["期"] == "2026-09")
        self.assertEqual(missing["销售额"], "—")
        self.assertEqual(missing["标记"], "")
        self.assertIn("值无效", missing["触发规则"])

    def test_existing_directory_is_refused_without_changing_artifacts(self):
        self.assert_success()
        before = {str(p.relative_to(self.output)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.output.rglob("*") if p.is_file()}
        proc = self.run_demo()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("拒绝覆盖", proc.stderr)
        after = {str(p.relative_to(self.output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
