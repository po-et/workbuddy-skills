#!/usr/bin/env python3
"""Stop 入口。修改自 Anthropic hookify（Apache-2.0），见 ATTRIBUTION.md。

设计原则：**永远 exit 0**。hookify 自身出错绝不能把 Agent 卡死；错误通过 systemMessage 报告。
"""
import json
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.environ.get("CODEBUDDY_PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT") \
    or os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from core.hookify import RuleEngine, event_for_tool, load_rules  # noqa: E402
except ImportError as e:  # pragma: no cover
    print(json.dumps({"continue": True, "systemMessage": f"hookify 导入失败: {e}"}))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
        rules = load_rules(event="stop", input_data=data)
        print(json.dumps(RuleEngine().evaluate(rules, data), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"continue": True, "systemMessage": f"hookify 错误: {e}"}, ensure_ascii=False))
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
