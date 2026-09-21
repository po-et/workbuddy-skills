"""skillkit 的端到端测试：每个子命令的正常路径与异常路径。

原则：
  * 只用标准库 unittest；
  * 每个用例自己造临时目录 fixture，不依赖仓库里的真实技能（那部分由实跑验证覆盖）；
  * 涉及网络的 stats 用假 http_get_json，并额外断言 urlopen 没被调用过 —— 测试绝不打真实接口。
"""

import io
import json
import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from skillkit import cli, frontmatter, rules
from skillkit.commands import stats as stats_cmd

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- 工具

def run_cli(argv):
    """跑一次 CLI，返回 (退出码, stdout, stderr)。argparse 的 SystemExit 也会被捕获。"""
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


GOOD_FM = {
    "name": "demo-skill",
    "description": ('日志排查、报错定位、异常分析、崩溃排查、error 排查。当用户说「帮我看看这段日志」'
                    '「这个报错什么意思」「服务为什么挂了」时使用。附纯标准库脚本 '
                    'scripts/demo_skill.py：按时间聚类、分级输出、--json 机器可读。'),
    "author": "Tester",
    "version": "0.1.0",
    "display_name": "日志排查助手",
    "display_name_en": "Log Triage",
    "description_zh": "一条命令把日志里的异常聚成几类并给出定位建议。",
    "description_en": "Cluster log anomalies and suggest where to look.",
}
GOOD_EXAMPLES_ZH = ["帮我看看这段日志", "这个报错什么意思", "服务为什么挂了"]
GOOD_EXAMPLES_EN = ["Triage this log", "What does this error mean", "Why did the service die"]
GOOD_TAGS = ["日志", "排查", "log", "triage", "SRE", "可观测性"]

BODY = """
# 日志排查助手

## 何时用

- 当用户贴出一段日志问「这是什么问题」
- 当服务挂了要快速定位第一现场
- **不用于**：实时监控告警配置，那是另一个技能的事

## 流程

1. 跑脚本，先看 high 级别的聚类
2. 按输出里的时间线回看上下游
3. 复验

```bash
python3 scripts/demo_skill.py app.log --json
```

## 输出契约

| 字段 | 含义 |
|---|---|
| cluster | 日志模板 |

退出码：0 通过；1 有 high 级别问题。

## 常见问题

- **时区不一致** —— 用 --tz 归一
- **日志被截断** —— 先确认 logrotate
""" + ("补充说明。" * 400)


def write_skill(parent, name="demo-skill", fm_overrides=None, body=BODY,
                examples_zh=None, examples_en=None, tags=None, with_script=True):
    """造一个通过全部格式校验的技能目录，再按 fm_overrides 定点破坏它。"""
    directory = Path(parent) / name
    (directory / "scripts").mkdir(parents=True, exist_ok=True)
    fields = dict(GOOD_FM)
    fields["name"] = name
    fields.update(fm_overrides or {})
    lines = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, str) and (": " in value or value.startswith(" ")):
            lines.append('%s: "%s"' % (key, value.replace('"', '\\"')))
        else:
            lines.append("%s: %s" % (key, value))
    ez = GOOD_EXAMPLES_ZH if examples_zh is None else examples_zh
    en = GOOD_EXAMPLES_EN if examples_en is None else examples_en
    tg = GOOD_TAGS if tags is None else tags
    if ez:
        lines.append(frontmatter.fmt_list("examples_zh", ez))
    if en:
        lines.append(frontmatter.fmt_list("examples_en", en))
    if tg:
        lines.append(frontmatter.fmt_list("tags", tg))
    (directory / "SKILL.md").write_text(
        frontmatter.join("\n".join(lines), body), encoding="utf-8")
    if with_script:
        (directory / "scripts" / "demo_skill.py").write_text(
            "#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    return directory


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="skillkit-test-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)


# ---------------------------------------------------------------- frontmatter

class TestFrontmatter(unittest.TestCase):
    def test_split_and_join_roundtrip(self):
        text = "---\nname: a\n---\n正文\n"
        fm_text, body = frontmatter.split(text)
        self.assertEqual(fm_text, "name: a")
        self.assertEqual(body, "正文\n")
        self.assertEqual(frontmatter.join(fm_text, body), text)

    def test_split_without_frontmatter_raises(self):
        with self.assertRaises(frontmatter.FrontmatterError):
            frontmatter.split("# 只有正文\n")
        self.assertIsNone(frontmatter.try_split("# 只有正文\n"))

    def test_parse_block_list_inline_list_and_nested_map(self):
        data = frontmatter.parse(
            "name: a\n"
            "tags:\n  - x\n  - \"y z\"\n"
            "inline: [p, q]\n"
            "nested:\n  key: v\n  other: w\n"
            "flag: true\n"
        )
        self.assertEqual(data["name"], "a")
        self.assertEqual(data["tags"], ["x", "y z"])
        self.assertEqual(data["inline"], ["p", "q"])
        self.assertEqual(data["nested"], {"key": "v", "other": "w"})
        self.assertIs(data["flag"], True)

    def test_parse_multiline_json_block(self):
        data = frontmatter.parse(
            'name: a\n'
            'metadata:\n'
            '  {\n'
            '    "openclaw":\n'
            '      { "requires": { "bins": ["python3"] }, "emoji": "🧰" }\n'
            '  }\n'
            'after: yes\n'
        )
        self.assertEqual(data["metadata"]["openclaw"]["emoji"], "🧰")
        self.assertEqual(data["after"], "yes")

    def test_parse_ignores_comments(self):
        data = frontmatter.parse("# 注释: 带冒号也不该被当字段\nname: a\n")
        self.assertEqual(list(data), ["name"])

    def test_unquoted_colon_lines_flags_strict_yaml_trap(self):
        bad = frontmatter.unquoted_colon_lines('a: 没问题\nb: 有问题: 会炸\nc: "有引号: 没事"\n')
        self.assertEqual([n for n, _ in bad], [2])

    def test_drop_keys_removes_block_and_inline_forms(self):
        text = "name: a\nversion: 1.0.0\ntags:\n  - x\n  - y\nafter: z"
        self.assertEqual(frontmatter.drop_keys(text, ("version", "tags")), "name: a\nafter: z")
        self.assertEqual(frontmatter.drop_keys("tags: [a, b]\nx: 1", ("tags",)), "x: 1")

    def test_fmt_helpers(self):
        self.assertEqual(frontmatter.fmt_scalar("k", "v"), "k: v")
        self.assertEqual(frontmatter.fmt_scalar("k", 'a"b', quote=True), 'k: "a\\"b"')
        self.assertEqual(frontmatter.fmt_list("t", ["a", "b"]), "t:\n  - a\n  - b")
        self.assertEqual(frontmatter.fmt_list("t", []), "t: []")


# ---------------------------------------------------------------- new

class TestNew(TempCase):
    def test_creates_skeleton_that_passes_lint(self):
        code, out, _ = run_cli(["new", "my-skill", "--dir", str(self.tmp), "--author", "Tester"])
        self.assertEqual(code, 0)
        self.assertIn("创建", out)
        self.assertTrue((self.tmp / "my-skill" / "SKILL.md").is_file())
        self.assertTrue((self.tmp / "my-skill" / "scripts" / "my_skill.py").is_file())
        code, out, _ = run_cli(["lint", str(self.tmp / "my-skill"), "--json"])
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        fails = [f for f in payload["skills"][0]["findings"] if f["level"] == "FAIL"]
        self.assertEqual(fails, [], "骨架不该一生成就带 FAIL")

    def test_template_contains_required_fields_and_pit_comments(self):
        run_cli(["new", "my-skill", "--dir", str(self.tmp)])
        text = (self.tmp / "my-skill" / "SKILL.md").read_text(encoding="utf-8")
        for key, _ in rules.REQUIRED_FIELDS:
            self.assertRegex(text, r"(?m)^%s:" % key)
        self.assertIn("配额", text)

    def test_no_script_flag(self):
        run_cli(["new", "s-only", "--dir", str(self.tmp), "--no-script"])
        self.assertFalse((self.tmp / "s-only" / "scripts").exists())

    def test_rejects_non_kebab_name(self):
        code, _, err = run_cli(["new", "My_Skill", "--dir", str(self.tmp)])
        self.assertEqual(code, 2)
        self.assertIn("kebab-case", err)

    def test_refuses_overwrite_without_force(self):
        run_cli(["new", "dup", "--dir", str(self.tmp)])
        code, _, err = run_cli(["new", "dup", "--dir", str(self.tmp)])
        self.assertEqual(code, 1)
        self.assertIn("--force", err)
        code, _, _ = run_cli(["new", "dup", "--dir", str(self.tmp), "--force"])
        self.assertEqual(code, 0)


# ---------------------------------------------------------------- lint

class TestLint(TempCase):
    def _lint_json(self, *paths):
        code, out, err = run_cli(["lint", "--json"] + [str(p) for p in paths])
        self.assertTrue(out, err)
        return code, json.loads(out)["skills"][0]

    def test_good_skill_passes(self):
        d = write_skill(self.tmp)
        code, result = self._lint_json(d)
        self.assertEqual(code, 0)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["total"], 80)
        self.assertEqual(set(result["scores"]), set(rules.SCORE_DIMENSIONS))

    def test_missing_parser_required_field_fails(self):
        d = write_skill(self.tmp, fm_overrides={"display_name_en": None})
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("display_name_en" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_missing_author_is_only_a_warning(self):
        d = write_skill(self.tmp, fm_overrides={"author": None})
        code, result = self._lint_json(d)
        self.assertEqual(code, 0)
        self.assertTrue(any("author" in f["message"]
                            for f in result["findings"] if f["level"] == "WARN"))

    def test_bad_semver_fails(self):
        d = write_skill(self.tmp, fm_overrides={"version": "1.0"})
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("version" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_too_many_examples_fails(self):
        d = write_skill(self.tmp, examples_zh=["a", "b", "c", "d"])
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("examples_zh" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_unquoted_colon_in_frontmatter_fails(self):
        d = write_skill(self.tmp)
        md = d / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8").replace(
            "author: Tester", "author: Tester: 前端"), encoding="utf-8")
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("严格 YAML" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_secret_in_file_fails(self):
        d = write_skill(self.tmp)
        (d / "scripts" / "leak.py").write_text(
            'TOKEN = "ghp_' + "a" * 36 + '"\n', encoding="utf-8")
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("GitHub token" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_pycache_fails(self):
        d = write_skill(self.tmp)
        (d / "scripts" / "__pycache__").mkdir()
        (d / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("__pycache__" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_extensionless_license_is_warning_not_fail(self):
        d = write_skill(self.tmp)
        (d / "LICENSE").write_text("MIT", encoding="utf-8")
        code, result = self._lint_json(d)
        self.assertEqual(code, 0)
        self.assertTrue(any("LICENSE" in f["message"]
                            for f in result["findings"] if f["level"] == "WARN"))

    def test_missing_frontmatter_fails(self):
        d = write_skill(self.tmp)
        (d / "SKILL.md").write_text("# 没有 frontmatter\n", encoding="utf-8")
        code, result = self._lint_json(d)
        self.assertEqual(code, 1)
        self.assertTrue(any("frontmatter" in f["message"]
                            for f in result["findings"] if f["level"] == "FAIL"))

    def test_min_threshold_gates_exit_code(self):
        d = write_skill(self.tmp)
        self.assertEqual(run_cli(["lint", str(d), "--min", "1"])[0], 0)
        code, out, _ = run_cli(["lint", str(d), "--min", "101"])
        self.assertEqual(code, 1)
        self.assertIn("低于", out)

    def test_recurses_into_parent_directory(self):
        write_skill(self.tmp, name="one")
        write_skill(self.tmp, name="two")
        code, out, _ = run_cli(["lint", str(self.tmp), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["skills"]), 2)

    def test_quiet_hides_clean_skills(self):
        d = write_skill(self.tmp)
        code, out, _ = run_cli(["lint", str(d), "--quiet"])
        self.assertEqual(code, 0)
        self.assertIn("都没有 FAIL", out)

    def test_missing_path_is_usage_error(self):
        code, _, err = run_cli(["lint", str(self.tmp / "nope")])
        self.assertEqual(code, 2)
        self.assertIn("路径不存在", err)

    def test_directory_without_skill_md_is_usage_error(self):
        (self.tmp / "empty").mkdir()
        code, _, err = run_cli(["lint", str(self.tmp / "empty")])
        self.assertEqual(code, 2)
        self.assertIn("SKILL.md", err)


# ---------------------------------------------------------------- build

class TestBuild(TempCase):
    def setUp(self):
        super(TestBuild, self).setUp()
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()

    def _head(self, slug):
        text = (self.out / slug / "SKILL.md").read_text(encoding="utf-8")
        return frontmatter.split(text)[0]

    def test_writes_publish_copy_with_skillhub_head(self):
        d = write_skill(self.src)
        code, out, err = run_cli(["build", str(d), "--out", str(self.out),
                                  "--homepage", "https://example.invalid/repo"])
        self.assertEqual(code, 0, out + err)
        head = self._head("demo-skill")
        self.assertTrue(head.startswith("slug: demo-skill\n"))
        for key in rules.SKILLHUB_REQUIRED + rules.SKILLHUB_RECOMMENDED:
            self.assertRegex(head, r"(?m)^%s:" % key)
        # 源目录未被改动
        self.assertNotIn("slug:", (d / "SKILL.md").read_text(encoding="utf-8"))

    def test_does_not_duplicate_version_or_tags(self):
        write_skill(self.src)
        run_cli(["build", str(self.src / "demo-skill"), "--out", str(self.out)])
        head = self._head("demo-skill")
        self.assertEqual(len([l for l in head.splitlines() if l.startswith("version:")]), 1)
        self.assertEqual(len([l for l in head.splitlines() if l.startswith("tags:")]), 1)

    def test_drops_extensionless_license(self):
        d = write_skill(self.src)
        (d / "LICENSE").write_text("MIT", encoding="utf-8")
        code, out, _ = run_cli(["build", str(d), "--out", str(self.out)])
        self.assertEqual(code, 0)
        self.assertIn("已删除", out)
        self.assertFalse((self.out / "demo-skill" / "LICENSE").exists())

    def test_drops_bytecode_and_pycache(self):
        d = write_skill(self.src)
        (d / "scripts" / "__pycache__").mkdir()
        (d / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
        run_cli(["build", str(d), "--out", str(self.out)])
        self.assertFalse((self.out / "demo-skill" / "scripts" / "__pycache__").exists())

    def test_slug_and_tags_overrides(self):
        d = write_skill(self.src)
        run_cli(["build", str(d), "--out", str(self.out),
                 "--slug", "demo-skill-triage", "--tags", "a,b"])
        head = self._head("demo-skill-triage")
        self.assertIn("slug: demo-skill-triage", head)
        self.assertIn("tags:\n  - a\n  - b", head)

    def test_map_file_renames_slug(self):
        write_skill(self.src, name="alpha")
        write_skill(self.src, name="beta")
        mapping = self.tmp / "map.json"
        mapping.write_text(json.dumps({"alpha": {"slug": "alpha-x", "tags": ["t1"]},
                                       "beta": "beta-y"}), encoding="utf-8")
        code, _, _ = run_cli(["build", str(self.src), "--out", str(self.out),
                              "--map", str(mapping)])
        self.assertEqual(code, 0)
        self.assertTrue((self.out / "alpha-x" / "SKILL.md").is_file())
        self.assertTrue((self.out / "beta-y" / "SKILL.md").is_file())

    def test_dry_run_writes_nothing(self):
        d = write_skill(self.src)
        code, out, _ = run_cli(["build", str(d), "--out", str(self.out), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("未落盘", out)
        self.assertFalse(self.out.exists())

    def test_duplicate_slug_in_one_run_fails(self):
        write_skill(self.src, name="alpha")
        write_skill(self.src, name="beta")
        mapping = self.tmp / "map.json"
        mapping.write_text(json.dumps({"alpha": "same", "beta": "same"}), encoding="utf-8")
        code, out, _ = run_cli(["build", str(self.src), "--out", str(self.out),
                                "--map", str(mapping)])
        self.assertEqual(code, 1)
        self.assertIn("撞车", out)

    def test_slug_with_multiple_targets_is_usage_error(self):
        write_skill(self.src, name="alpha")
        write_skill(self.src, name="beta")
        code, _, err = run_cli(["build", str(self.src), "--out", str(self.out), "--slug", "x"])
        self.assertEqual(code, 2)
        self.assertIn("--slug", err)

    def test_bad_map_file_is_usage_error(self):
        d = write_skill(self.src)
        bad = self.tmp / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code, _, err = run_cli(["build", str(d), "--out", str(self.out), "--map", str(bad)])
        self.assertEqual(code, 2)
        self.assertIn("--map", err)

    def test_missing_out_is_argparse_error(self):
        d = write_skill(self.src)
        code, _, _ = run_cli(["build", str(d)])
        self.assertEqual(code, 2)

    def test_long_summary_is_truncated(self):
        d = write_skill(self.src, fm_overrides={"description_zh": "长" * 300})
        run_cli(["build", str(d), "--out", str(self.out)])
        summary = frontmatter.get_raw(self._head("demo-skill"), "summary")
        self.assertLessEqual(len(summary), rules.SUMMARY_MAX)
        self.assertGreater(len(summary), rules.SUMMARY_MAX - 5)
        self.assertTrue(summary.endswith("…"))


# ---------------------------------------------------------------- budget

class TestBudget(TempCase):
    def test_plan_splits_into_batches(self):
        code, out, _ = run_cli(["budget", "--count", "40", "--used", "12",
                                "--start", "2026-09-21T20:00:00", "--json", "--no-bash"])
        self.assertEqual(code, 0)
        plan = json.loads(out)
        self.assertEqual(plan["usable_now"], 78)
        self.assertEqual(plan["publish_this_round"], 40)
        self.assertEqual(plan["batch_count"], 2)
        self.assertEqual([b["count"] for b in plan["batches"]], [25, 15])
        self.assertIsNone(plan["resume_after"])

    def test_quota_exhausted_defers_everything(self):
        code, out, _ = run_cli(["budget", "--count", "5", "--used", "95",
                                "--start", "2026-09-21T20:00:00", "--json", "--no-bash"])
        self.assertEqual(code, 0)
        plan = json.loads(out)
        self.assertEqual(plan["publish_this_round"], 0)
        self.assertEqual(plan["deferred"], 5)
        self.assertEqual(plan["resume_after"], "2026-09-22T20:00:00")

    def test_text_output_marks_speculative_defaults(self):
        code, out, _ = run_cli(["budget", "--count", "3", "--no-bash"])
        self.assertEqual(code, 0)
        self.assertIn("推测", out)

    def test_bash_template_written_to_file(self):
        path = self.tmp / "publish.sh"
        code, out, _ = run_cli(["budget", "--count", "3", "--out", str(path)])
        self.assertEqual(code, 0)
        script = path.read_text(encoding="utf-8")
        self.assertIn("skillhub publish", script)
        self.assertIn("发布频率过高", script)
        self.assertIn("已写入", out)

    def test_zero_count_is_usage_error(self):
        code, _, err = run_cli(["budget", "--count", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--count", err)

    def test_negative_used_is_usage_error(self):
        code, _, err = run_cli(["budget", "--count", "1", "--used", "-1"])
        self.assertEqual(code, 2)
        self.assertIn("--used", err)

    def test_bad_start_is_usage_error(self):
        code, _, err = run_cli(["budget", "--count", "1", "--start", "昨天"])
        self.assertEqual(code, 2)
        self.assertIn("--start", err)


# ---------------------------------------------------------------- stats（离线）

DETAIL = {
    "skill": {"displayName": "演示技能", "category": "dev-programming",
              "createdAt": 1758326400000, "updatedAt": 1758412800000,
              "stats": {"downloads": 1234, "installs": 2, "stars": 7,
                        "comments": 1, "versions": 3}},
    "latestVersion": {"version": "0.1.2"},
    "namespace": {"handle": "someone"},
}
SEARCH = {"results": [{"slug": "demo-skill", "namespace": {"handle": "someone"}}]}
EVALUATION = {
    "skillId": 123456,
    "dimensions": dict((d, {"items": {"a": {"score": 4}, "b": {"score": 5}}})
                       for d in rules.STATS_EVAL_DIMENSIONS),
}


class TestStats(TempCase):
    def setUp(self):
        super(TestStats, self).setUp()
        self.calls = []
        self.real_get = stats_cmd.http_get_json
        self.addCleanup(setattr, stats_cmd, "http_get_json", self.real_get)
        stats_cmd.http_get_json = self._fake_get
        # 兜底：真实网络层一旦被调用就直接炸，保证测试绝不打真实接口
        self.real_urlopen = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", self.real_urlopen)
        urllib.request.urlopen = self._boom

    def _boom(self, *args, **kwargs):
        raise AssertionError("测试里不允许发真实 HTTP 请求")

    def _fake_get(self, url, timeout=10.0):
        self.calls.append(url)
        if "missing-skill" in url:
            return 404, {"error": "not found"}, None
        if "/evaluation" in url:
            return 200, EVALUATION, None
        if "/api/v1/search" in url:
            return 200, SEARCH, None
        return 200, DETAIL, None

    def test_reports_metrics_from_detail_endpoint(self):
        code, out, _ = run_cli(["stats", "demo-skill", "--namespace", "someone",
                                "--sleep", "0", "--json"])
        self.assertEqual(code, 0)
        row = json.loads(out)["skills"][0]
        self.assertTrue(row["found"])
        self.assertEqual(row["downloads"], 1234)
        self.assertEqual(row["stars"], 7)
        self.assertIs(row["in_search_index"], True)
        self.assertEqual(row["eval_overall"], 4.5)

    def test_missing_slug_sets_exit_code_1(self):
        code, out, _ = run_cli(["stats", "missing-skill", "--sleep", "0", "--json"])
        self.assertEqual(code, 1)
        row = json.loads(out)["skills"][0]
        self.assertFalse(row["found"])
        self.assertEqual(row["http_status"], 404)
        # 详情 404 之后不该再去查搜索与评测
        self.assertEqual(len(self.calls), 1)

    def test_comma_separated_slugs_and_text_output(self):
        code, out, _ = run_cli(["stats", "demo-skill,missing-skill", "--sleep", "0"])
        self.assertEqual(code, 1)
        self.assertIn("demo-skill", out)
        self.assertIn("查不到", out)
        self.assertIn("浏览量平台不提供", out)

    def test_skip_flags_reduce_requests(self):
        run_cli(["stats", "demo-skill", "--sleep", "0", "--no-search", "--no-eval", "--json"])
        self.assertEqual(len(self.calls), 1)

    def test_csv_output_appends_header_once(self):
        path = self.tmp / "m.csv"
        run_cli(["stats", "demo-skill", "--sleep", "0", "--csv", str(path), "--json"])
        run_cli(["stats", "demo-skill", "--sleep", "0", "--csv", str(path), "--json"])
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("queried_at,slug"))

    def test_no_auth_header_is_sent(self):
        """回归保护：这几个接口对 CLI 本来就是匿名可读的，不要偷偷加鉴权头。"""
        captured = {}

        def capture(req, timeout=None):
            captured["headers"] = dict(req.headers)
            captured["method"] = req.get_method()
            raise RuntimeError("stop here")

        urllib.request.urlopen = capture
        status, _, err = self.real_get("https://example.invalid/api/v1/skills/x")
        self.assertEqual(status, 0)
        self.assertIn("stop here", err)
        self.assertEqual(captured["method"], "GET")
        self.assertEqual(sorted(k.lower() for k in captured["headers"]),
                         ["accept", "user-agent"])


# ---------------------------------------------------------------- doctor

class TestDoctor(TempCase):
    def test_clean_skill_can_publish(self):
        d = write_skill(self.tmp)
        code, out, _ = run_cli(["doctor", str(d), "--json"])
        self.assertEqual(code, 0)
        result = json.loads(out)["skills"][0]
        self.assertTrue(result["can_publish"])
        self.assertEqual(result["slug"], "demo-skill")

    def test_broken_skill_is_blocked(self):
        d = write_skill(self.tmp, fm_overrides={"version": "nope"})
        code, out, _ = run_cli(["doctor", str(d), "--json"])
        self.assertEqual(code, 1)
        result = json.loads(out)["skills"][0]
        self.assertFalse(result["can_publish"])
        self.assertTrue(any("version" in b for b in result["blockers"]))

    def test_same_rule_is_not_reported_twice(self):
        """lint 与 build 会从两个角度撞上同一条规则，结论里只该出现一次。"""
        d = write_skill(self.tmp, fm_overrides={"version": "nope"})
        code, out, _ = run_cli(["doctor", str(d), "--json"])
        self.assertEqual(code, 1)
        blockers = json.loads(out)["skills"][0]["blockers"]
        self.assertEqual(sum(1 for b in blockers if "version" in b.lower()), 1, blockers)

    def test_score_threshold_blocks(self):
        d = write_skill(self.tmp)
        code, out, _ = run_cli(["doctor", str(d), "--min", "101", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("低于门槛", json.loads(out)["skills"][0]["blockers"][0])

    def test_text_output_lists_reminders(self):
        d = write_skill(self.tmp)
        code, out, _ = run_cli(["doctor", str(d)])
        self.assertEqual(code, 0)
        self.assertIn("失败的发布请求一样消耗配额", out)

    def test_reports_files_build_would_remove(self):
        d = write_skill(self.tmp)
        (d / "NOTICE").write_text("x", encoding="utf-8")
        code, out, _ = run_cli(["doctor", str(d)])
        self.assertEqual(code, 0)
        self.assertIn("NOTICE", out)

    def test_slug_with_multiple_targets_is_usage_error(self):
        write_skill(self.tmp, name="alpha")
        write_skill(self.tmp, name="beta")
        code, _, err = run_cli(["doctor", str(self.tmp), "--slug", "x"])
        self.assertEqual(code, 2)


# ---------------------------------------------------------------- pitfalls / 入口

class TestPitfallsAndEntry(unittest.TestCase):
    def test_lists_all_rules(self):
        code, out, _ = run_cli(["pitfalls", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), len(rules.PITFALLS))

    def test_filter_by_confidence(self):
        code, out, _ = run_cli(["pitfalls", "--confidence", "推测"])
        self.assertEqual(code, 0)
        self.assertIn("需确认", out)

    def test_unknown_id_returns_1(self):
        code, out, _ = run_cli(["pitfalls", "--id", "no-such-rule"])
        self.assertEqual(code, 1)
        self.assertIn("没有匹配", out)

    def test_every_pitfall_has_required_columns(self):
        for pit in rules.PITFALLS:
            for key in ("id", "现象", "规则", "证据", "置信度", "skillkit"):
                self.assertIn(key, pit, pit.get("id"))
            self.assertTrue(pit["置信度"].startswith(("实测", "文档", "推测", "自设")), pit["id"])

    def test_no_subcommand_prints_help(self):
        code, out, _ = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("典型流程", out)

    def test_version_flag(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("skillkit", out)

    def test_every_subcommand_has_chinese_help(self):
        parser = cli.build_parser()
        actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
        names = sorted(actions[0].choices)
        self.assertEqual(names, sorted(["new", "lint", "build", "doctor",
                                        "budget", "stats", "pitfalls"]))
        for name, sub in actions[0].choices.items():
            text = sub.format_help()
            self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in text), name)

    def test_runs_as_module(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, "-m", "skillkit", "--help"],
                              cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skillkit", proc.stdout)


if __name__ == "__main__":
    unittest.main()
