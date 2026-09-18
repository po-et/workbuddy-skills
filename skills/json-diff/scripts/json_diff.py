#!/usr/bin/env python3
"""语义化 JSON / 配置对比：按扁平路径列出仅左有、仅右有、值不同、类型不同、数组长度变化。纯标准库。

用法：
  python3 json_diff.py old.json new.json
  python3 json_diff.py prod.json staging.json --ignore '*.updatedAt' --ignore 'meta.*'
  python3 json_diff.py a.json b.json --array-key id            # 数组按对象的 id 字段配对，而不是按下标
  python3 json_diff.py a.json b.json --summary-only
  python3 json_diff.py a.json b.json --json
退出码：0 无差异；1 有差异（便于 CI 比对配置漂移）；2 读取或解析失败。
"""
import argparse
import json
import re
import sys
from fnmatch import fnmatchcase

SECRET_PAT = re.compile(r"(password|passwd|secret|token|apikey|api_key|accesskey|access_key|"
                        r"privatekey|private_key|credential|\bkey\b|_key$|\.key$)", re.I)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
TYPE_ZH = {dict: "对象", list: "数组", str: "字符串", bool: "布尔", int: "整数", float: "浮点", type(None): "空值"}


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def type_name(v):
    return TYPE_ZH.get(type(v), type(v).__name__)


def join(path, key):
    if isinstance(key, int):
        return f"{path}[{key}]"
    if IDENT.match(str(key)):
        return f"{path}.{key}" if path else str(key)
    return f'{path}["{key}"]' if path else f'["{key}"]'


def brief(v, mask=False, limit=70):
    if mask:
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        return f"***（{len(s)} 字符）"
    if isinstance(v, dict):
        return "{…}" if not v else "{" + f"…{len(v)} 个键" + "}"
    if isinstance(v, list):
        return "[]" if not v else "[" + f"…{len(v)} 项" + "]"
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def load(path):
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8-sig", errors="replace").read()
    except OSError as e:
        die(f"读不到文件：{e}")
    if not text.strip():
        die(f"{path} 是空文件")
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():                     # JSONL：取第一条记录
        if line.strip():
            try:
                return json.loads(line), True
            except json.JSONDecodeError as e:
                die(f"{path} 既不是合法 JSON，第一行也不是合法 JSONL 记录：{e}")
    die(f"{path} 里没有内容")


class Differ:
    def __init__(self, ignores, array_keys, default_key, mask):
        self.ignores, self.array_keys, self.default_key, self.mask = ignores, array_keys, default_key, mask
        self.left_only, self.right_only, self.changed, self.retyped, self.len_changed = [], [], [], [], []
        self.notes, self.ignored = [], 0

    def skip(self, path):
        for pat in self.ignores:
            if fnmatchcase(path, pat):
                return True
            if not any(c in pat for c in "*?[") and (path.startswith(pat + ".") or path.startswith(pat + "[")):
                return True
        return False

    def key_field(self, path):
        for pat, field in self.array_keys:
            if fnmatchcase(path, pat) or fnmatchcase(path + "[]", pat):
                return field
        return self.default_key

    def secret(self, path):
        return bool(SECRET_PAT.search(path)) if self.mask else False

    def walk(self, a, b, path=""):
        if self.skip(path):
            self.ignored += 1
            return
        if type(a) is not type(b) and not (isinstance(a, bool) == isinstance(b, bool)
                                           and isinstance(a, (int, float)) and isinstance(b, (int, float))):
            m = self.secret(path)
            self.retyped.append({"path": path, "old_type": type_name(a), "new_type": type_name(b),
                                 "old": brief(a, m), "new": brief(b, m)})
            return
        if isinstance(a, dict):
            for k in a:
                p = join(path, k)
                if k not in b:
                    if self.skip(p):
                        self.ignored += 1; continue
                    self.left_only.append({"path": p, "value": brief(a[k], self.secret(p)), "type": type_name(a[k])})
                else:
                    self.walk(a[k], b[k], p)
            for k in b:
                if k not in a:
                    p = join(path, k)
                    if self.skip(p):
                        self.ignored += 1; continue
                    self.right_only.append({"path": p, "value": brief(b[k], self.secret(p)), "type": type_name(b[k])})
            return
        if isinstance(a, list):
            if len(a) != len(b):
                self.len_changed.append({"path": path or "(根)", "old": len(a), "new": len(b)})
            field = self.key_field(path)
            objs = all(isinstance(x, dict) for x in a + b) and bool(a + b)
            if field and objs and all(field in x for x in a + b):
                self.walk_keyed(a, b, path, field)
            else:
                if field and objs:
                    self.notes.append(f"{path or '(根)'}：数组元素缺少键字段 {field!r}，退回按下标对比")
                for i in range(min(len(a), len(b))):
                    self.walk(a[i], b[i], join(path, i))
                for i in range(len(b), len(a)):
                    p = join(path, i)
                    if not self.skip(p):
                        self.left_only.append({"path": p, "value": brief(a[i], self.secret(p)), "type": type_name(a[i])})
                for i in range(len(a), len(b)):
                    p = join(path, i)
                    if not self.skip(p):
                        self.right_only.append({"path": p, "value": brief(b[i], self.secret(p)), "type": type_name(b[i])})
            return
        if a != b:
            m = self.secret(path)
            self.changed.append({"path": path or "(根)", "old": brief(a, m), "new": brief(b, m)})

    def walk_keyed(self, a, b, path, field):
        def index(items):
            out, dup = {}, []
            for x in items:
                k = json.dumps(x[field], ensure_ascii=False, sort_keys=True)
                if k in out:
                    dup.append(k)
                out.setdefault(k, x)
            return out, dup

        ia, dup_a = index(a)
        ib, dup_b = index(b)
        for k in dup_a + dup_b:
            self.notes.append(f"{path or '(根)'}：键 {field}={k} 重复，只对比第一个")
        for k, x in ia.items():
            p = f"{path}[{field}={k.strip(chr(34))}]"
            if k not in ib:
                if not self.skip(p):
                    self.left_only.append({"path": p, "value": brief(x, self.secret(p)), "type": "数组元素"})
            else:
                self.walk(x, ib[k], p)
        for k, x in ib.items():
            if k not in ia:
                p = f"{path}[{field}={k.strip(chr(34))}]"
                if not self.skip(p):
                    self.right_only.append({"path": p, "value": brief(x, self.secret(p)), "type": "数组元素"})

    def total(self):
        return len(self.left_only) + len(self.right_only) + len(self.changed) + len(self.retyped) + len(self.len_changed)


def main():
    ap = argparse.ArgumentParser(description="语义化 JSON / 配置对比")
    ap.add_argument("left", help="左侧（旧）文件，写 - 从标准输入读")
    ap.add_argument("right", help="右侧（新）文件")
    ap.add_argument("--array-key", action="append", default=[], metavar="字段 或 路径=字段",
                    help="数组按对象某字段配对，如 id 或 spec.containers=name；可重复")
    ap.add_argument("--ignore", action="append", default=[], metavar="路径通配",
                    help="忽略路径，支持通配，如 '*.updatedAt'、'meta.*'；可重复")
    ap.add_argument("--summary-only", action="store_true", help="只输出统计")
    ap.add_argument("--no-mask", action="store_true", help="不脱敏密钥类路径的值（默认脱敏）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    array_keys, default_key = [], None
    for spec in a.array_key:
        if "=" in spec:
            pat, field = spec.split("=", 1)
            array_keys.append((pat, field))
        else:
            default_key = spec

    left, jsonl_l = load(a.left)
    right, jsonl_r = load(a.right)
    d = Differ(a.ignore, array_keys, default_key, not a.no_mask)
    d.walk(left, right)

    counts = {"仅左有": len(d.left_only), "仅右有": len(d.right_only), "值不同": len(d.changed),
              "类型不同": len(d.retyped), "数组长度变化": len(d.len_changed)}
    if a.json:
        print(json.dumps({"left": a.left, "right": a.right, "total": d.total(), "counts": counts,
                          "ignored": d.ignored, "notes": d.notes, "left_only": d.left_only,
                          "right_only": d.right_only, "changed": d.changed, "retyped": d.retyped,
                          "array_length_changed": d.len_changed}, ensure_ascii=False, indent=2))
        sys.exit(1 if d.total() else 0)

    print(f"{a.left} → {a.right}")
    for f, is_l in ((a.left, jsonl_l), (a.right, jsonl_r)):
        if is_l:
            print(f"· {f} 按 JSONL 处理，只对比第一条记录")
    if d.total() == 0:
        print("两边语义一致" + (f"（忽略 {d.ignored} 处）" if d.ignored else "") + "。")
    else:
        print(f"差异 {d.total()} 处：" + "，".join(f"{k} {v}" for k, v in counts.items() if v)
              + (f"（忽略 {d.ignored} 处）" if d.ignored else ""))
    for n in d.notes:
        print(f"· {n}")

    if not a.summary_only:
        blocks = [("仅左侧有", "-", d.left_only, lambda x: f"{x['path']} = {x['value']}"),
                  ("仅右侧有", "+", d.right_only, lambda x: f"{x['path']} = {x['value']}"),
                  ("值不同", "~", d.changed, lambda x: f"{x['path']}\n      {x['old']}  →  {x['new']}"),
                  ("类型不同", "!", d.retyped,
                   lambda x: f"{x['path']}\n      {x['old_type']} {x['old']}  →  {x['new_type']} {x['new']}"),
                  ("数组长度变化", "#", d.len_changed, lambda x: f"{x['path']}  {x['old']} 项  →  {x['new']} 项")]
        for title, sign, items, fmt in blocks:
            if not items:
                continue
            print(f"\n## {title}（{len(items)}）")
            for x in sorted(items, key=lambda x: x["path"]):
                print(f"  {sign} {fmt(x)}")

    sys.exit(1 if d.total() else 0)


if __name__ == "__main__":
    main()
