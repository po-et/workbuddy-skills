#!/usr/bin/env python3
"""从样例 JSON 推断 JSON Schema（draft 2020-12）：合并多条样例，识别可空、可选字段、枚举候选、格式（date-time / email / uuid / uri）。纯标准库。

用法：
  python3 schema_infer.py sample.json                # 单个对象或数组
  python3 schema_infer.py events.jsonl --jsonl        # 每行一条
  cat resp.json | python3 schema_infer.py - --title Order --enum-max 8 --required-threshold 1.0
"""
import argparse, collections, json, re, sys

FORMATS = [
    ("date-time", re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")),
    ("date", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("uuid", re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)),
    ("email", re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")),
    ("uri", re.compile(r"^https?://\S+$")),
    ("ipv4", re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")),
]


class Node:
    def __init__(self):
        self.types = collections.Counter()
        self.count = 0
        self.props = collections.defaultdict(Node)
        self.prop_seen = collections.Counter()
        self.items = None
        self.strings = collections.Counter()
        self.nums = []
        self.fmt = collections.Counter()
        self.max_len = 0

    def add(self, v):
        self.count += 1
        if v is None:
            self.types["null"] += 1
        elif isinstance(v, bool):
            self.types["boolean"] += 1
        elif isinstance(v, int):
            self.types["integer"] += 1; self.nums.append(v)
        elif isinstance(v, float):
            self.types["number"] += 1; self.nums.append(v)
        elif isinstance(v, str):
            self.types["string"] += 1; self.strings[v] += 1; self.max_len = max(self.max_len, len(v))
            for name, pat in FORMATS:
                if pat.match(v):
                    self.fmt[name] += 1; break
        elif isinstance(v, list):
            self.types["array"] += 1
            if self.items is None:
                self.items = Node()
            for x in v:
                self.items.add(x)
        elif isinstance(v, dict):
            self.types["object"] += 1
            for k, x in v.items():
                self.prop_seen[k] += 1; self.props[k].add(x)

    def schema(self, a):
        types = [t for t in self.types if t != "null"]
        nullable = self.types.get("null", 0) > 0
        if "integer" in types and "number" in types:
            types.remove("integer")
        out = {}
        if len(types) == 1:
            t = types[0]; out["type"] = [t, "null"] if nullable else t
        elif types:
            out["type"] = sorted(types) + (["null"] if nullable else [])
        else:
            out["type"] = "null"
        if "object" in types:
            n_obj = self.types["object"]
            out["properties"] = {k: self.props[k].schema(a) for k in self.props}
            req = [k for k, c in self.prop_seen.items() if c / n_obj >= a.required_threshold]
            if req:
                out["required"] = sorted(req)
            out["additionalProperties"] = False if a.strict else True
        if "array" in types and self.items is not None and self.items.count:
            out["items"] = self.items.schema(a)
        if "string" in types:
            if self.fmt and self.fmt.most_common(1)[0][1] == self.types["string"]:
                out["format"] = self.fmt.most_common(1)[0][0]
            elif len(self.strings) <= a.enum_max and self.types["string"] >= a.enum_min and self.max_len <= 40:
                out["enum"] = sorted(self.strings)
            if a.lengths and self.max_len:
                out["maxLength"] = self.max_len
        if self.nums and ("integer" in types or "number" in types) and a.ranges:
            out["minimum"], out["maximum"] = min(self.nums), max(self.nums)
        if a.examples and "string" in types and "enum" not in out and "format" not in out:
            out["examples"] = [self.strings.most_common(1)[0][0]]
        return out


def main():
    ap = argparse.ArgumentParser(description="JSON Schema 推断")
    ap.add_argument("file")
    ap.add_argument("--jsonl", action="store_true")
    ap.add_argument("--title")
    ap.add_argument("--required-threshold", type=float, default=1.0, help="字段出现比例 ≥ 此值视为 required（默认 1.0 = 每条样例都有）")
    ap.add_argument("--enum-max", type=int, default=6, help="不同取值 ≤ 此数视为枚举候选")
    ap.add_argument("--enum-min", type=int, default=3, help="至少这么多样例才推枚举")
    ap.add_argument("--strict", action="store_true", help="additionalProperties: false")
    ap.add_argument("--ranges", action="store_true", help="输出数值 minimum/maximum")
    ap.add_argument("--lengths", action="store_true", help="输出字符串 maxLength")
    ap.add_argument("--examples", action="store_true")
    a = ap.parse_args()
    raw = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    if a.jsonl:
        samples = [json.loads(l) for l in raw.splitlines() if l.strip()]
    else:
        data = json.loads(raw)
        samples = data if isinstance(data, list) else [data]
    root = Node()
    for s in samples:
        root.add(s)
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
    if a.title:
        schema["title"] = a.title
    schema.update(root.schema(a))
    schema["x-inferred-from"] = f"{len(samples)} 条样例；required 阈值 {a.required_threshold}；枚举 ≤ {a.enum_max} 个取值"
    print(json.dumps(schema, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
