#!/usr/bin/env python3
"""hookify-workbuddy 端到端测试：通过 subprocess 以 stdin JSON 驱动真实入口脚本。

运行:  python3 -m unittest tests.test_hooks -v   （在插件根目录）
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")


def run_hook(script, payload, project):
    env = {**os.environ, "CODEBUDDY_PLUGIN_ROOT": ROOT}
    p = subprocess.run([sys.executable, os.path.join(HOOKS, script)],
                       input=json.dumps({**payload, "cwd": project}),
                       capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, f"hook 必须 exit 0，实际 {p.returncode}: {p.stderr}"
    return json.loads(p.stdout)


def write_rule(project, subdir, name, body):
    d = os.path.join(project, subdir)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"hookify.{name}.local.md"), "w", encoding="utf-8") as f:
        f.write(body)


BLOCK_RM = """---
name: block-dangerous-rm
enabled: true
event: bash
pattern: rm\\s+-rf
action: block
---

⚠️ 检测到危险的 rm 命令。
"""

WARN_ENV = """---
name: warn-sensitive-files
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \\.env$|credentials|secrets
---

🔐 你正在编辑可能含凭证的文件。
"""

STOP_TESTS = """---
name: require-tests
enabled: true
event: stop
action: block
conditions:
  - field: transcript
    operator: not_contains
    pattern: pytest|npm test
---

未检测到测试命令，先跑测试再结束。
"""

PROMPT_DEPLOY = """---
name: deploy-checklist
enabled: true
event: prompt
conditions:
  - field: user_prompt
    operator: contains
    pattern: 上线
---

上线前检查清单：测试、评审、回滚方案。
"""


class HookifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- PreToolUse ----------
    def test_pretooluse_blocks_rm_rf(self):
        write_rule(self.project, ".codebuddy", "rm", BLOCK_RM)
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "rm -rf /tmp/x"}}, self.project)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("危险", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertTrue(out["continue"])

    def test_pretooluse_allows_safe_command(self):
        write_rule(self.project, ".codebuddy", "rm", BLOCK_RM)
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "ls -la"}}, self.project)
        self.assertEqual(out, {"continue": True})

    def test_pretooluse_ide_tool_alias(self):
        """IDE 模式工具名 execute_command 也应命中 bash 规则（兼容项）。"""
        write_rule(self.project, ".codebuddy", "rm", BLOCK_RM)
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "execute_command",
                                         "tool_input": {"command": "rm -rf build"}}, self.project)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_pretooluse_warns_on_env_file(self):
        write_rule(self.project, ".codebuddy", "env", WARN_ENV)
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                                         "tool_input": {"file_path": "/p/.env", "content": "X=1"}},
                       self.project)
        self.assertNotIn("hookSpecificOutput", out)
        self.assertIn("凭证", out["systemMessage"])
        self.assertTrue(out["continue"])

    # ---------- Stop ----------
    def test_stop_blocks_when_no_tests_in_transcript(self):
        write_rule(self.project, ".codebuddy", "tests", STOP_TESTS)
        tp = os.path.join(self.project, "t.txt")
        with open(tp, "w") as f:
            f.write("edited files, no tests")
        out = run_hook("stop.py", {"hook_event_name": "Stop", "transcript_path": tp}, self.project)
        self.assertEqual(out["decision"], "block")
        self.assertFalse(out["continue"])
        self.assertIn("测试", out["stopReason"])

    def test_stop_allows_when_tests_ran(self):
        write_rule(self.project, ".codebuddy", "tests", STOP_TESTS)
        tp = os.path.join(self.project, "t.txt")
        with open(tp, "w") as f:
            f.write("ran pytest, all green")
        out = run_hook("stop.py", {"hook_event_name": "Stop", "transcript_path": tp}, self.project)
        self.assertEqual(out, {"continue": True})

    # ---------- UserPromptSubmit：字段兼容 ----------
    def test_prompt_field_codebuddy_style(self):
        write_rule(self.project, ".codebuddy", "deploy", PROMPT_DEPLOY)
        out = run_hook("userpromptsubmit.py", {"hook_event_name": "UserPromptSubmit",
                                               "prompt": "帮我上线这个版本"}, self.project)
        self.assertIn("回滚", out["hookSpecificOutput"]["additionalContext"])

    def test_prompt_field_claude_code_style(self):
        write_rule(self.project, ".codebuddy", "deploy", PROMPT_DEPLOY)
        out = run_hook("userpromptsubmit.py", {"hook_event_name": "UserPromptSubmit",
                                               "user_prompt": "准备上线"}, self.project)
        self.assertIn("回滚", out["systemMessage"])

    # ---------- 目录优先级与禁用 ----------
    def test_codebuddy_dir_overrides_claude_dir(self):
        write_rule(self.project, ".claude", "rm", BLOCK_RM.replace("action: block", "action: warn"))
        write_rule(self.project, ".codebuddy", "rm", BLOCK_RM)
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "rm -rf x"}}, self.project)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_claude_dir_still_works_alone(self):
        write_rule(self.project, ".claude", "rm", BLOCK_RM)
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "rm -rf x"}}, self.project)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_disabled_rule_is_ignored(self):
        write_rule(self.project, ".codebuddy", "rm", BLOCK_RM.replace("enabled: true", "enabled: false"))
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "rm -rf x"}}, self.project)
        self.assertEqual(out, {"continue": True})

    # ---------- 健壮性：坏规则文件绝不卡死 Agent ----------
    def test_malformed_rule_never_breaks_hook(self):
        write_rule(self.project, ".codebuddy", "bad", "no frontmatter here")
        write_rule(self.project, ".codebuddy", "badre", BLOCK_RM.replace("rm\\s+-rf", "([unclosed"))
        out = run_hook("pretooluse.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "rm -rf x"}}, self.project)
        self.assertTrue(out["continue"])

    def test_no_rules_dir_at_all(self):
        out = run_hook("posttooluse.py", {"hook_event_name": "PostToolUse", "tool_name": "Edit",
                                          "tool_input": {"file_path": "a.py"}, "tool_response": "ok"},
                       self.project)
        self.assertEqual(out, {"continue": True})


if __name__ == "__main__":
    unittest.main()
