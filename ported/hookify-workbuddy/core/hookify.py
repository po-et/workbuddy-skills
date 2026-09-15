#!/usr/bin/env python3
"""hookify-workbuddy 核心：规则加载 + 规则引擎。

修改自 Anthropic 官方插件 hookify（Apache-2.0）：
  https://github.com/anthropics/claude-plugins-official/tree/main/plugins/hookify
原作者 Anthropic。本文件为派生作品，改动见仓库 ATTRIBUTION.md。

主要改动（相对原版）：
  1. 合并 config_loader.py + rule_engine.py 为单文件，便于作为插件分发
  2. 规则目录：优先 <项目>/.codebuddy/，其次 .claude/（兼容），项目根取自 stdin 的 cwd
  3. 字段兼容：UserPromptSubmit 同时接受 prompt / user_prompt；
              PostToolUse 同时接受 tool_response / tool_result
  4. 工具名映射抽成表（TOOL_EVENTS），可扩展
  5. 输出统一带顶层 continue，PreToolUse 拒绝时补 permissionDecisionReason，
     Stop 拒绝时同时给 decision/reason 与 continue/stopReason 两种形态
  6. 全部中文错误信息
"""
from __future__ import annotations

import glob
import os
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

# 事件别名 -> 工具名集合。IDE 模式工具名（execute_command 等）来自第三方移植报告，
# 未在官方文档中确认，标为兼容项；官方文档记载的工具名为 Bash / Edit / Write。
TOOL_EVENTS: Dict[str, set] = {
    "bash": {"Bash", "execute_command"},
    "file": {"Edit", "Write", "MultiEdit", "write_to_file", "replace_in_file"},
}

RULE_GLOB = "hookify.*.local.md"
RULE_DIRS = (".codebuddy", ".claude")   # 优先级从高到低


# ---------------------------------------------------------------- 数据结构

@dataclass
class Condition:
    field: str
    operator: str = "regex_match"
    pattern: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Condition":
        return cls(field=str(d.get("field", "")),
                   operator=str(d.get("operator", "regex_match")),
                   pattern=str(d.get("pattern", "")))


@dataclass
class Rule:
    name: str
    enabled: bool
    event: str                      # bash | file | stop | prompt | all
    conditions: List[Condition] = field(default_factory=list)
    action: str = "warn"            # warn | block
    tool_matcher: Optional[str] = None
    message: str = ""
    source: str = ""                # 规则文件路径，便于报错定位

    @classmethod
    def from_frontmatter(cls, fm: Dict[str, Any], message: str, source: str = "") -> "Rule":
        conds: List[Condition] = []
        raw = fm.get("conditions")
        if isinstance(raw, list):
            conds = [Condition.from_dict(c) for c in raw if isinstance(c, dict)]

        simple = fm.get("pattern")
        if simple and not conds:
            event = str(fm.get("event", "all"))
            fld = "command" if event == "bash" else "new_text" if event == "file" \
                else "user_prompt" if event == "prompt" else "content"
            conds = [Condition(field=fld, operator="regex_match", pattern=str(simple))]

        enabled = fm.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() not in ("false", "0", "no", "off")

        return cls(name=str(fm.get("name", "unnamed")), enabled=bool(enabled),
                   event=str(fm.get("event", "all")), conditions=conds,
                   action=str(fm.get("action", "warn")).lower(),
                   tool_matcher=fm.get("tool_matcher"),
                   message=message.strip(), source=source)


# ---------------------------------------------------------------- 规则文件解析

def extract_frontmatter(content: str):
    """解析 YAML frontmatter（子集）+ 消息体。与原版兼容：
    支持 key: value / conditions 列表（多行 dict 项与单行逗号 dict 项）。"""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm_text, message = parts[1], parts[2].strip()

    fm: Dict[str, Any] = {}
    cur_key: Optional[str] = None
    cur_list: List[Any] = []
    cur_dict: Dict[str, Any] = {}
    in_list = in_dict = False

    def flush():
        nonlocal cur_list, cur_dict, in_list, in_dict
        if in_list and cur_key:
            if in_dict and cur_dict:
                cur_list.append(cur_dict)
            fm[cur_key] = cur_list
        cur_list, cur_dict, in_list, in_dict = [], {}, False, False

    for line in fm_text.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        if indent == 0 and ":" in line and not s.startswith("-"):
            flush()
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if not v:
                cur_key, in_list = k, True
            else:
                v = v.strip("\"'")
                fm[k] = True if v.lower() == "true" else False if v.lower() == "false" else v

        elif s.startswith("-") and in_list:
            if in_dict and cur_dict:
                cur_list.append(cur_dict)
                cur_dict = {}
            item = s[1:].strip()
            if ":" in item and "," in item:
                d = {}
                for part in item.split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        d[k.strip()] = v.strip().strip("\"'")
                cur_list.append(d)
                in_dict = False
            elif ":" in item:
                in_dict = True
                k, v = item.split(":", 1)
                cur_dict = {k.strip(): v.strip().strip("\"'")}
            else:
                cur_list.append(item.strip("\"'"))
                in_dict = False

        elif indent > 2 and in_dict and ":" in line:
            k, v = s.split(":", 1)
            cur_dict[k.strip()] = v.strip().strip("\"'")

    flush()
    return fm, message


def project_root(input_data: Optional[Dict[str, Any]] = None) -> str:
    """项目根：stdin 的 cwd > CODEBUDDY_PROJECT_DIR > CLAUDE_PROJECT_DIR > 进程 cwd。"""
    if input_data and input_data.get("cwd"):
        return str(input_data["cwd"])
    for var in ("CODEBUDDY_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        if os.environ.get(var):
            return os.environ[var]
    return os.getcwd()


def load_rules(event: Optional[str] = None,
               input_data: Optional[Dict[str, Any]] = None) -> List[Rule]:
    root = project_root(input_data)
    seen_names: set = set()
    rules: List[Rule] = []
    for d in RULE_DIRS:
        for path in sorted(glob.glob(os.path.join(root, d, RULE_GLOB))):
            try:
                with open(path, encoding="utf-8") as f:
                    fm, msg = extract_frontmatter(f.read())
            except (OSError, UnicodeDecodeError) as e:
                print(f"hookify: 读取失败 {path}: {e}", file=sys.stderr)
                continue
            if not fm:
                print(f"hookify: {path} 缺少 YAML frontmatter（须以 --- 开头）", file=sys.stderr)
                continue
            rule = Rule.from_frontmatter(fm, msg, source=path)
            if not rule.enabled:
                continue
            if event and rule.event not in ("all", event):
                continue
            # 同名规则：高优先级目录（.codebuddy）胜出
            if rule.name in seen_names:
                continue
            seen_names.add(rule.name)
            rules.append(rule)
    return rules


# ---------------------------------------------------------------- 规则引擎

@lru_cache(maxsize=128)
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


class RuleEngine:
    def evaluate(self, rules: List[Rule], input_data: Dict[str, Any]) -> Dict[str, Any]:
        event = input_data.get("hook_event_name", "")
        blocking = [r for r in rules if self._matches(r, input_data) and r.action == "block"]
        warning = [r for r in rules if self._matches(r, input_data) and r.action != "block"]

        if blocking:
            msg = "\n\n".join(f"**[{r.name}]**\n{r.message}" for r in blocking)
            if event == "Stop":
                # 两种形态同时给：Claude Code 读 decision/reason，CodeBuddy/WorkBuddy 读 continue/stopReason
                return {"decision": "block", "reason": msg,
                        "continue": False, "stopReason": msg, "systemMessage": msg}
            if event in ("PreToolUse", "PostToolUse"):
                return {"continue": True,
                        "hookSpecificOutput": {"hookEventName": event,
                                               "permissionDecision": "deny",
                                               "permissionDecisionReason": msg},
                        "systemMessage": msg}
            return {"continue": True, "systemMessage": msg}

        if warning:
            msg = "\n\n".join(f"**[{r.name}]**\n{r.message}" for r in warning)
            out: Dict[str, Any] = {"continue": True, "systemMessage": msg}
            if event in ("UserPromptSubmit", "SessionStart"):
                out["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": msg}
            return out

        return {"continue": True}

    # ---- 匹配 ----
    def _matches(self, rule: Rule, data: Dict[str, Any]) -> bool:
        tool = data.get("tool_name", "")
        tin = data.get("tool_input", {}) or {}
        if rule.tool_matcher and not self._tool_ok(rule.tool_matcher, tool):
            return False
        if not rule.conditions:
            return False
        return all(self._cond(c, tool, tin, data) for c in rule.conditions)

    @staticmethod
    def _tool_ok(matcher: str, tool: str) -> bool:
        return matcher == "*" or tool in matcher.split("|")

    def _cond(self, c: Condition, tool: str, tin: Dict[str, Any], data: Dict[str, Any]) -> bool:
        val = self._field(c.field, tool, tin, data)
        if val is None:
            return False
        op, p = c.operator, c.pattern
        if op == "regex_match":
            try:
                return bool(_compile(p).search(val))
            except re.error as e:
                print(f"hookify: 规则正则无效 {p!r}: {e}", file=sys.stderr)
                return False
        # contains / not_contains 支持 "a|b|c" 任一匹配语义（上游原版按字面串处理，
        # 导致其自带的 require-tests 示例 `not_contains: npm test|pytest` 永远为真）。
        alts = [a for a in p.split("|") if a != ""] if "|" in p else [p]
        return {"contains": lambda: any(a in val for a in alts),
                "not_contains": lambda: not any(a in val for a in alts),
                "equals": lambda: p == val,
                "starts_with": lambda: val.startswith(p),
                "ends_with": lambda: val.endswith(p)}.get(op, lambda: False)()

    @staticmethod
    def _field(fld: str, tool: str, tin: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
        if fld in tin:
            v = tin[fld]
            return v if isinstance(v, str) else str(v)

        if fld == "reason":
            return str(data.get("reason", ""))
        if fld in ("user_prompt", "prompt"):
            return str(data.get("prompt") or data.get("user_prompt") or "")
        if fld in ("tool_response", "tool_result"):
            v = data.get("tool_response", data.get("tool_result", ""))
            return v if isinstance(v, str) else str(v)
        if fld == "transcript":
            path = data.get("transcript_path")
            if not path:
                return ""
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError as e:
                print(f"hookify: 无法读取 transcript {path}: {e}", file=sys.stderr)
                return ""

        if tool in TOOL_EVENTS["bash"] and fld == "command":
            return str(tin.get("command", ""))

        if tool in TOOL_EVENTS["file"]:
            if fld == "content":
                return str(tin.get("content") or tin.get("new_string") or "")
            if fld in ("new_text", "new_string"):
                if "edits" in tin:   # MultiEdit
                    return " ".join(str(e.get("new_string", "")) for e in tin.get("edits", []))
                return str(tin.get("new_string") or tin.get("content") or "")
            if fld in ("old_text", "old_string"):
                return str(tin.get("old_string", ""))
            if fld == "file_path":
                return str(tin.get("file_path", ""))
        return None


OTHER_EVENT = "other"   # Read / Glob / Grep / WebFetch / mcp__* 等非 bash、非 file 工具


def event_for_tool(tool: str) -> str:
    """工具名 -> 事件别名。未知工具返回 OTHER_EVENT，而不是 None。

    上游 hookify 在这里返回 None，而 load_rules(event=None) 等于不过滤，
    导致 event:file 的 block 规则会误拦 Read（issue #4787），
    event:stop 的规则在每次 PreToolUse 都触发（issue #3712）。
    返回 OTHER_EVENT 后，只有 event: all 的规则会对这类工具生效。"""
    for ev, names in TOOL_EVENTS.items():
        if tool in names:
            return ev
    return OTHER_EVENT
