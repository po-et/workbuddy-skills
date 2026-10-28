"""Behavioral checks using synthetic slide XML, not GUI rendering claims."""
from collections import Counter
from html import escape
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "skills/pptx-making/scripts/pptx_check.py"
SPEC = importlib.util.spec_from_file_location("pptx_check_regression", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
TITLE = "本季度注册转化率提升了九个百分点"
NS = ('xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')


def run(text="合成正文", size=None, field=False):
    tag = "a:fld" if field else "a:r"
    props = "" if size is None else f'<a:rPr sz="{size}"/>'
    return f'<{tag}>{props}<a:t>{escape(text)}</a:t></{tag}>'


def paragraph(content=None, size=None, level=None):
    attrs = "" if level is None else f' lvl="{level}"'
    default = "" if size is None else f'<a:defRPr sz="{size}"/>'
    return f'<a:p><a:pPr{attrs}>{default}</a:pPr>{run() if content is None else content}</a:p>'


def shape(content, title=False, list_style="", body_pr="<a:bodyPr/>"):
    placeholder = '<p:ph type="title"/>' if title else ""
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{1 if title else 2}" name="合成文本"/>'
            f'<p:nvPr>{placeholder}</p:nvPr></p:nvSpPr><p:txBody>{body_pr}'
            f'<a:lstStyle>{list_style}</a:lstStyle>{content}</p:txBody></p:sp>')


def slide(content, list_style="", title=TITLE, body_pr="<a:bodyPr/>"):
    heading = "" if title is None else shape(paragraph(run(title, 3200)), title=True)
    return (f'<p:sld {NS}><p:cSld><p:spTree>{heading}'
            f'{shape(content, list_style=list_style, body_pr=body_pr)}'
            '</p:spTree></p:cSld></p:sld>')


class PptxCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "合成汇报.pptx"

    def deck(self, *slides, order=None, extras=None):
        with zipfile.ZipFile(self.source, "w") as archive:
            for number, xml in enumerate(slides, 1):
                archive.writestr(f"ppt/slides/slide{number}.xml", xml)
            if order is not None:
                archive.writestr("ppt/presentation.xml",
                                 '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                                 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                                 '<p:sldIdLst>' + ''.join(f'<p:sldId r:id="r{n}"/>' for n in order) +
                                 '</p:sldIdLst></p:presentation>')
                archive.writestr("ppt/_rels/presentation.xml.rels",
                                 '<Relationships>' + ''.join(f'<Relationship Id="r{n}" Target="slides/slide{n}.xml"/>'
                                                             for n in range(1, len(slides) + 1)) + '</Relationships>')
            for name, text in (extras or {}).items():
                archive.writestr(name, text)
        return self.source

    def inspect(self):
        return CHECKER.check_details(self.source, 18)

    def body_records(self, report=None):
        return [r for r in (report or self.inspect())["font_size_coverage"]["text_pieces"] if r["text"] != TITLE]

    def cli(self, *args):
        before = self.source.read_bytes() if self.source.exists() else None
        before_names = set(self.root.iterdir())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.source), *args],
                                capture_output=True, text=True)
        self.assertNotIn("Traceback", result.stderr)
        if before is not None:
            self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), before_names)
        return result

    def test_paragraph_default_small_font_is_not_missed(self):
        self.deck(slide(paragraph(size=800)))
        report = self.inspect()
        self.assertEqual(report["font_size_coverage"]["small_count"], 1)
        record, = self.body_records(report)
        self.assertEqual((record["font_size_pt"], record["font_source"]), (8, "paragraph"))
        self.assertEqual([i["code"] for i in report["issues"]], ["small_font"])
        self.assertEqual(self.cli().returncode, 3)

    def test_explicit_run_overrides_small_paragraph_and_list_defaults(self):
        self.deck(slide(paragraph(run(size=2400), size=800),
                        list_style='<a:lvl1pPr><a:defRPr sz="600"/></a:lvl1pPr>'))
        report = self.inspect()
        self.assertEqual(report["issues"], [])
        self.assertEqual(self.body_records(report)[0]["font_size_pt"], 24)
        self.assertEqual(self.body_records(report)[0]["font_source"], "run")

    def test_paragraph_default_overrides_list_default(self):
        self.deck(slide(paragraph(size=2400), list_style='<a:lvl1pPr><a:defRPr sz="800"/></a:lvl1pPr>'))
        self.assertEqual(self.body_records()[0]["font_size_pt"], 24)
        self.assertEqual(self.inspect()["font_size_coverage"]["small_count"], 0)

    def test_list_style_follows_paragraph_level_and_default_level_zero(self):
        levels = ('<a:lvl1pPr><a:defRPr sz="800"/></a:lvl1pPr>'
                  '<a:lvl3pPr><a:defRPr sz="2200"/></a:lvl3pPr>')
        self.deck(slide(paragraph(run("一级")) + paragraph(run("三级"), level=2), list_style=levels))
        records = self.body_records()
        self.assertEqual([(r["font_size_pt"], r["font_source"]) for r in records],
                         [(8, "list_style"), (22, "list_style")])

    def test_list_style_does_not_leak_between_text_bodies(self):
        xml = slide(paragraph(run("第一文本框")), list_style='<a:lvl1pPr><a:defRPr sz="800"/></a:lvl1pPr>')
        xml = xml.replace('</p:spTree>', shape(paragraph(run("第二文本框"))) + '</p:spTree>')
        self.deck(xml)
        records = self.body_records()
        self.assertEqual([r["font_size_pt"] for r in records], [8, None])

    def test_paragraph_default_does_not_leak_between_paragraphs(self):
        self.deck(slide(paragraph(run("第一段"), size=800) + paragraph(run("第二段"))))
        self.assertEqual([r["font_size_pt"] for r in self.body_records()], [8, None])

    def test_real_run_and_field_count_once_and_empty_text_does_not_count(self):
        content = run("正常字段", 2400, field=True) + run("小字段", field=True) + run("普通文字") + run("") + run("  ", 600)
        self.deck(slide(paragraph(content, size=800)))
        report = self.inspect()
        self.assertEqual(report["font_size_coverage"]["text_piece_count"], 4)  # 标题与三处正文
        self.assertEqual(report["font_size_coverage"]["small_count"], 2)
        self.assertEqual([r["kind"] for r in self.body_records(report)], ["field", "field", "run"])

    def test_table_cell_uses_its_own_text_body_defaults(self):
        cell = ('<p:graphicFrame><a:tbl><a:tr><a:tc><a:txBody><a:bodyPr/><a:lstStyle>'
                '<a:lvl1pPr><a:defRPr sz="800"/></a:lvl1pPr></a:lstStyle>' + paragraph(run("表格文字")) +
                '</a:txBody></a:tc></a:tr></a:tbl></p:graphicFrame>')
        xml = slide(paragraph(run("普通正文", 2400))).replace('</p:spTree>', cell + '</p:spTree>')
        self.deck(xml)
        records = self.body_records()
        self.assertEqual([(r["text"], r["font_size_pt"]) for r in records], [("普通正文", 24), ("表格文字", 8)])

    def test_unknown_master_size_is_counted_and_never_claimed_resolved(self):
        self.deck(slide(paragraph()), extras={"ppt/slideMasters/slideMaster1.xml": '<a:defRPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" sz="800"/>'})
        report = self.inspect()
        self.assertEqual(report["font_size_coverage"]["unresolved_count"], 1)
        self.assertEqual(report["font_size_coverage"]["small_count"], 0)
        self.assertEqual(report["status"], "no_issues_in_checked_scope")
        self.assertIsNone(self.body_records(report)[0]["font_size_pt"])
        human = self.cli()
        self.assertEqual(human.returncode, 0)
        self.assertIn("未确定 1 处", human.stdout)
        self.assertIn("检查范围内", human.stdout)

    def test_invalid_explicit_size_stays_unresolved_instead_of_inventing_a_size(self):
        self.deck(slide(paragraph(run(size="bad"), size=2400)))
        record, = self.body_records()
        self.assertIsNone(record["font_size_pt"])
        self.assertEqual(record["unresolved_reason"], "invalid_explicit_size")

    def test_invalid_list_level_stays_unresolved(self):
        self.deck(slide(paragraph(level="9"), list_style='<a:lvl1pPr><a:defRPr sz="800"/></a:lvl1pPr>'))
        self.assertIsNone(self.body_records()[0]["font_size_pt"])

    def test_threshold_is_strict_and_legacy_numeric_argument_remains_supported(self):
        self.deck(slide(paragraph(run(size=1800))))
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(self.cli("18.01").returncode, 3)
        self.assertEqual(self.cli("14").returncode, 0)

    def test_json_is_deterministic_and_source_hash_matches_unchanged_input(self):
        self.deck(slide(paragraph(size=800)))
        first, second = self.cli("--json"), self.cli("--json")
        self.assertEqual(first.returncode, 3)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["source"], {"name": self.source.name,
                                          "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()})
        self.assertEqual(report["titles"], [{"slide": 1, "part": "ppt/slides/slide1.xml", "text": TITLE}])
        self.assertEqual(report["font_size_coverage"]["source_counts"], {"run": 1, "paragraph": 1, "list_style": 0})
        self.assertEqual(first.stderr, "")

    def test_json_evidence_paths_resolve_to_actual_text_and_font_attribute(self):
        self.deck(slide(paragraph(size=800)))
        report = self.inspect()
        evidence, = report["issues"][0]["evidence"]
        with zipfile.ZipFile(self.source) as archive:
            root = ET.fromstring(archive.read(evidence["part"]))
        namespaces = {"a": CHECKER.A[1:-1], "p": CHECKER.P[1:-1]}
        text_path = evidence["text_path"].split("/", 1)[1]
        size_path = evidence["size_path"].split("/", 1)[1].rsplit("/@", 1)[0]
        self.assertEqual(root.find(text_path, namespaces).text, "合成正文")
        self.assertEqual(root.find(size_path, namespaces).get("sz"), "800")

    def test_legacy_check_api_keeps_four_item_tuple_and_counters(self):
        self.deck(slide(paragraph(size=800)))
        result = CHECKER.check(self.source, 18)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], [TITLE])
        self.assertEqual(len(result[1]), 1)
        self.assertIsInstance(result[2], Counter)
        self.assertIsInstance(result[3], Counter)

    def test_slide_presentation_order_is_preserved(self):
        self.deck(slide(paragraph(run(size=2400)), title="第一份材料的结论需要继续验证"),
                  slide(paragraph(run(size=2400)), title="第二份材料的结论需要继续验证"), order=[2, 1])
        self.assertEqual([t["part"] for t in self.inspect()["titles"]],
                         ["ppt/slides/slide2.xml", "ppt/slides/slide1.xml"])

    def test_existing_title_density_and_auto_shrink_checks_remain(self):
        paragraphs = ''.join(paragraph(run(f"合成要点{n}", 2400)) for n in range(7))
        self.deck(slide(paragraphs, title="市场分析",
                        body_pr='<a:bodyPr><a:normAutofit fontScale="62500"/></a:bodyPr>'))
        self.assertEqual([i["code"] for i in self.inspect()["issues"]],
                         ["topic_title", "dense_body", "auto_shrink"])
        self.deck(slide(paragraph(run(size=2400)), title=None))
        self.assertEqual([i["code"] for i in self.inspect()["issues"]], ["missing_title_placeholder"])

    def test_autofit_at_full_size_or_default_is_not_font_shrinkage(self):
        settings = ('<a:normAutofit fontScale="100000"/>',
                    '<a:normAutofit fontScale="100%"/>',
                    '<a:normAutofit fontScale="100.000%"/>',
                    '<a:normAutofit/>',
                    '<a:normAutofit lnSpcReduction="20000"/>',
                    '<a:normAutofit fontScale="100000" lnSpcReduction="20000"/>')
        for fit in settings:
            with self.subTest(fit=fit):
                self.deck(slide(paragraph(run(size=2400)), body_pr=f'<a:bodyPr>{fit}</a:bodyPr>'))
                result = self.cli("--json")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["issues"], [])

    def test_autofit_integer_and_percentage_forms_flag_only_actual_shrinkage(self):
        # Expectations derive from 1000 = 1%, 100000 = 100%, and the documented percent-string form.
        for raw, percentage in (("1000", "1"), ("1%", "1"), ("62500", "62.5"),
                                ("62.500%", "62.5"), ("92.000%", "92"),
                                ("99999", "99.999"), ("99.999%", "99.999")):
            with self.subTest(fontScale=raw):
                self.deck(slide(paragraph(run(size=2400)),
                                body_pr=f'<a:bodyPr><a:normAutofit fontScale="{raw}"/></a:bodyPr>'))
                result = self.cli("--json")
                self.assertEqual(result.returncode, 3)
                issues = json.loads(result.stdout)["issues"]
                self.assertEqual([i["code"] for i in issues], ["auto_shrink"])
                self.assertIn(percentage + "%", issues[0]["message"])

    def test_unsupported_or_invalid_font_scale_is_not_claimed_as_font_shrinkage(self):
        for raw in ("0", "999", "100001", "0%", "0.999%", "100.001%", "-62500", "-2%",
                    "NaN", "NaN%", "Infinity", "Infinity%", "6.25e4", "6.25e1%", "", "n/a",
                    "٦٢٥٠٠", "６２５００", "9" * 6000):
            with self.subTest(fontScale=raw):
                self.deck(slide(paragraph(run(size=2400)),
                                body_pr=f'<a:bodyPr><a:normAutofit fontScale="{raw}"/></a:bodyPr>'))
                result = self.cli("--json")
                self.assertEqual(result.returncode, 3)
                issues = json.loads(result.stdout)["issues"]
                self.assertEqual([i["code"] for i in issues], ["unresolved_font_scale"])

    def test_existing_manual_font_and_color_statistics_remain(self):
        text = '<a:r><a:rPr sz="2400"><a:latin typeface="Arial"/><a:ea typeface="微软雅黑"/><a:solidFill><a:srgbClr val="305496"/></a:solidFill></a:rPr><a:t>合成正文</a:t></a:r>'
        self.deck(slide(paragraph(text)))
        report = self.inspect()
        self.assertEqual(report["fonts"], {"Arial": 1, "微软雅黑": 1})
        self.assertEqual(report["colors"], {"305496": 1})

    def test_corrupt_slide_does_not_look_like_complete_coverage(self):
        self.deck("<broken")
        report = self.inspect()
        self.assertEqual(report["font_size_coverage"]["unreadable_slide_count"], 1)
        self.assertEqual(report["font_size_coverage"]["text_piece_count"], 0)
        self.assertEqual([i["code"] for i in report["issues"]], ["unreadable_slide"])
        self.assertEqual(self.cli("--json").returncode, 3)

    def test_nonfinite_zero_negative_and_nonnumeric_thresholds_are_argument_errors(self):
        self.deck(slide(paragraph(run(size=2400))))
        for value in ("nan", "NaN", "inf", "-inf", "1e999", "0", "-1", "wrong"):
            with self.subTest(value=value):
                self.assertEqual(self.cli(value).returncode, 1)

    def test_file_errors_remain_exit_two(self):
        self.assertEqual(self.cli("--json").returncode, 2)
        self.source.write_bytes(b"not a zip file")
        self.assertEqual(self.cli("--json").returncode, 2)
        self.deck()
        self.assertEqual(self.cli("--json").returncode, 2)


if __name__ == "__main__":
    unittest.main()
