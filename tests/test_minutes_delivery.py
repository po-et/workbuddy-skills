"""Behavior tests for source-linked minutes delivery, using synthetic text only."""

import copy
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/meeting-transcript-cleanup"
SCRIPT = SKILL / "scripts/compile_minutes.py"
SPEC = importlib.util.spec_from_file_location("compile_minutes_delivery", SCRIPT)
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)


class MinutesDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.source = self.directory / "transcript.txt"
        self.notes_path = self.directory / "notes.json"
        self.out = self.directory / "delivery"
        self.source.write_bytes((SKILL / "assets/sample-transcript.txt").read_bytes())
        self.notes = json.loads((SKILL / "assets/sample-notes.json").read_text(encoding="utf-8"))
        self.lines, _ = compiler.decode_transcript(self.source.read_bytes())

    def save_notes(self):
        self.notes_path.write_text(json.dumps(self.notes, ensure_ascii=False), encoding="utf-8")

    def run_delivery(self):
        self.save_notes()
        return compiler.run(self.source, self.notes_path, self.out)

    def assert_rejected(self):
        self.save_notes()
        with self.assertRaises(compiler.InputError):
            compiler.run(self.source, self.notes_path, self.out)
        self.assertFalse(self.out.exists())

    def test_ready_deliverables_and_source_hashes(self):
        source_bytes = self.source.read_bytes()
        self.save_notes()
        notes_bytes = self.notes_path.read_bytes()
        report = compiler.run(self.source, self.notes_path, self.out)
        self.assertEqual({p.name for p in self.out.iterdir()}, {"minutes.md", "minutes.json", "actions.csv"})
        self.assertEqual(report["source"]["sha256"], hashlib.sha256(source_bytes).hexdigest())
        self.assertEqual(report["annotations"]["sha256"], hashlib.sha256(notes_bytes).hexdigest())
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertEqual(self.notes_path.read_bytes(), notes_bytes)
        self.assertFalse(report["checks"]["semantic_decision_verification"])
        self.assertFalse(report["checks"]["message_sent"])
        self.assertEqual(len(report["actions"]), 2)
        self.assertEqual(len(report["open_questions"]), 2)

    def test_unambiguous_confirmation_enters_decisions(self):
        report = self.run_delivery()
        self.assertTrue(report["decisions"][0]["included_as_confirmed_decision"])
        self.assertEqual(report["decisions"][0]["review_status"], "anchors_validated")

    def test_conditional_and_cancelled_stay_out_of_confirmed_decisions(self):
        report = self.run_delivery()
        self.assertFalse(report["decisions"][1]["included_as_confirmed_decision"])
        self.assertFalse(report["decisions"][2]["included_as_confirmed_decision"])
        text = (self.out / "minutes.md").read_text(encoding="utf-8")
        decision_section = text.split("## 一、决议", 1)[1].split("## 二、", 1)[0]
        self.assertNotIn("D2", decision_section)
        self.assertNotIn("D3", decision_section)
        self.assertIn("已取消", text)

    def test_literal_condition_in_mislabelled_confirmed_needs_review(self):
        self.notes["decisions"][1]["state"] = "confirmed"
        report = self.run_delivery()
        record = report["decisions"][1]
        self.assertEqual(record["state"], "confirmed")  # Preserve supplied label, do not infer semantics.
        self.assertFalse(record["included_as_confirmed_decision"])
        self.assertEqual(record["review_status"], "needs_review")
        self.assertTrue(any("字面" in flag for flag in record["review_flags"]))

    def test_literal_cancellation_in_confirmed_is_held_for_review(self):
        self.notes["decisions"][2]["state"] = "confirmed"
        record = self.run_delivery()["decisions"][2]
        self.assertFalse(record["included_as_confirmed_decision"])
        self.assertEqual(record["review_status"], "needs_review")

    def test_proposal_not_promoted_to_decision(self):
        self.notes["decisions"][0]["state"] = "proposed"
        self.assertFalse(self.run_delivery()["decisions"][0]["included_as_confirmed_decision"])

    def test_missing_owner_and_relative_deadline_stay_unknown(self):
        report = self.run_delivery()
        action = report["actions"][0]
        self.assertIsNone(report["meeting"]["date"])
        self.assertIsNone(action["owner"])
        self.assertIsNone(action["due_date"])
        self.assertEqual(action["due_text"], "明天")
        text = (self.out / "minutes.md").read_text(encoding="utf-8")
        self.assertIn("待认领", text)
        self.assertIn("明天（具体日期待确认）", text)

    def test_meeting_date_does_not_trigger_invented_deadline_conversion(self):
        self.notes["meeting"]["date"] = "2026-10-13"
        action = self.run_delivery()["actions"][0]
        self.assertIsNone(action["due_date"])
        self.assertEqual(action["due_text"], "明天")

    def test_unanchored_owner_is_rejected(self):
        self.notes["actions"][0]["owner"] = "猜出来的姓名"
        self.notes["actions"][0]["owner_source"] = copy.deepcopy(self.notes["actions"][0]["sources"][0])
        self.assert_rejected()

    def test_anonymous_owner_is_preserved_without_identity_inference(self):
        self.notes["actions"][0]["owner"] = "发言人1"
        self.notes["actions"][0]["owner_source"] = copy.deepcopy(self.notes["actions"][0]["sources"][0])
        record = self.run_delivery()["actions"][0]
        self.assertEqual(record["owner"], "发言人1")
        self.assertTrue(any("身份待确认" in flag for flag in record["review_flags"]))

    def test_owner_anchor_must_be_within_item_sources(self):
        self.notes["actions"][0]["owner"] = "赵敏"
        self.notes["actions"][0]["owner_source"] = copy.deepcopy(self.notes["actions"][1]["owner_source"])
        self.assert_rejected()

    def test_inferred_absolute_deadline_is_rejected(self):
        self.notes["actions"][0]["due_date"] = "2026-10-14"
        self.assert_rejected()

    def test_conflicting_date_quotes_flag_due_date(self):
        action = self.run_delivery()["actions"][1]
        self.assertEqual(action["due_date"], "2026-10-16")  # Annotation retained, not endorsed.
        self.assertEqual(action["review_status"], "needs_review")
        self.assertTrue(any("多个日期" in flag for flag in action["review_flags"]))

    def test_truncated_or_rewritten_quote_is_rejected(self):
        self.notes["decisions"][1]["sources"][0]["quote"] = "才安排导入"
        self.assert_rejected()

    def test_line_range_out_of_bounds_is_rejected(self):
        self.notes["decisions"][0]["sources"][0]["end_line"] = 999
        self.assert_rejected()

    def test_boolean_line_number_is_rejected(self):
        self.notes["decisions"][0]["sources"][0]["start_line"] = True
        self.assert_rejected()

    def test_duplicate_ids_across_categories_are_rejected(self):
        self.notes["actions"][0]["id"] = "D1"
        self.assert_rejected()

    def test_unknown_state_or_wrong_state_type_is_rejected(self):
        for state in ("approved", ["confirmed"], None):
            self.notes["decisions"][0]["state"] = state
            with self.subTest(state=state):
                self.assert_rejected()

    def test_schema_typos_and_missing_sources_are_rejected(self):
        self.notes["actions"][0]["owenr"] = "赵敏"
        self.assert_rejected()
        del self.notes["actions"][0]["owenr"]
        self.notes["actions"][0]["sources"] = []
        self.assert_rejected()

    def test_nonexistent_calendar_date_is_rejected(self):
        self.notes["meeting"]["date"] = "2026-02-30"
        self.assert_rejected()

    def test_existing_directory_is_never_overwritten(self):
        self.out.mkdir()
        sentinel = self.out / "minutes.md"
        sentinel.write_text("keep me", encoding="utf-8")
        self.assert_rejected_existing()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me")

    def assert_rejected_existing(self):
        self.save_notes()
        with self.assertRaises(compiler.InputError):
            compiler.run(self.source, self.notes_path, self.out)

    def test_symlink_output_is_never_followed(self):
        target = self.directory / "original"
        target.mkdir()
        self.out.symlink_to(target, target_is_directory=True)
        self.assert_rejected_existing()
        self.assertEqual(list(target.iterdir()), [])

    def test_csv_formula_escape_applies_to_every_user_cell(self):
        line = "=evil：+事项 @owner 明天"
        self.source.write_text(line + "\n", encoding="utf-8")
        anchor = {"start_line": 1, "end_line": 1, "quote": line}
        self.notes = {"schema_version": "1", "meeting": {"title": "  =title", "date": None},
                      "decisions": [], "open_questions": [], "actions": [
                          {"id": "-A", "text": "+事项", "state": "confirmed", "sources": [anchor],
                           "owner": "@owner", "owner_source": anchor, "due_text": "明天",
                           "due_date": None, "due_source": anchor}]}
        self.run_delivery()
        with (self.out / "actions.csv").open(encoding="utf-8", newline="") as handle:
            row = list(csv.DictReader(handle))[0]
        for column in ("meeting_title", "id", "action", "owner", "source_quote"):
            self.assertTrue(row[column].startswith("'"), column)
        for value in ("\tplain", "\nplain", "\ufeff =x", "  @x", "\r=1", "-123"):
            self.assertTrue(compiler.csv_cell(value).startswith("'"))

    def test_markdown_html_and_table_injection_is_escaped(self):
        self.notes["meeting"]["title"] = '<script>alert(1)</script> [x](https://evil.invalid)'
        self.notes["actions"][0]["text"] = "task | forged column\n# injected heading"
        self.run_delivery()
        text = (self.out / "minutes.md").read_text(encoding="utf-8")
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("task \\| forged column / \\# injected heading", text)
        self.assertIn("\\[x\\]", text)

    def test_original_crlf_hash_and_normalized_quote_lines(self):
        raw = self.source.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8")
        self.source.write_bytes(raw)
        report = self.run_delivery()
        self.assertEqual(report["source"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(report["source"]["line_count"], 16)

    def test_legacy_and_bom_text_encodings_preserve_original_hash(self):
        text = self.source.read_text(encoding="utf-8")
        for encoding in ("gb18030", "utf-16", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                raw = text.encode(encoding)
                self.source.write_bytes(raw)
                self.save_notes()
                report = compiler.run(self.source, self.notes_path, self.directory / encoding)
                self.assertEqual(report["source"]["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(report["source"]["line_count"], 16)

    def test_duplicate_json_fields_are_rejected_without_output(self):
        self.notes_path.write_text('{"schema_version":"1","schema_version":"2"}', encoding="utf-8")
        with self.assertRaises(compiler.InputError):
            compiler.run(self.source, self.notes_path, self.out)
        self.assertFalse(self.out.exists())

    def test_cli_generates_flagged_draft_successfully(self):
        self.save_notes()
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.source), "--notes", str(self.notes_path),
                                 "--out-dir", str(self.out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("needs_review", result.stdout)
        self.assertTrue((self.out / "minutes.md").is_file())

    def test_cli_validation_error_returns_two_and_preserves_inputs(self):
        self.notes["decisions"][0]["sources"][0]["quote"] = "fabricated"
        self.save_notes()
        before = self.source.read_bytes(), self.notes_path.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.source), "--notes", str(self.notes_path),
                                 "--out-dir", str(self.out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("原文不一致", result.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(before, (self.source.read_bytes(), self.notes_path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
