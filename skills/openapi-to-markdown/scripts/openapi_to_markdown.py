#!/usr/bin/env python3
"""OpenAPI 3.x 生成中文 Markdown 接口文档：目录、按 tag 分组、参数表、请求体与响应字段表、示例。纯标准库。

用法：
  python3 openapi_to_markdown.py openapi.json -o docs/api.md
  python3 openapi_to_markdown.py openapi.json --tag 用户 --tag 订单
  python3 openapi_to_markdown.py openapi.json --json          # 输出中间结构，便于二次加工
  python3 openapi_to_markdown.py openapi.json --strict         # 文档完整性门禁，有缺失退出码 1
"""
import argparse
import json
import re
import sys

METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")
FMT_SAMPLE = {"date-time": "2026-01-01T00:00:00Z", "date": "2026-01-01", "email": "dev@example.com",
              "uuid": "3f0c1a2e-1b2c-4d5e-8f90-1a2b3c4d5e6f", "uri": "https://example.com/x",
              "binary": "<binary>", "password": "******"}
IN_ZH = {"path": "路径", "query": "查询", "header": "请求头", "cookie": "Cookie"}


def load(path):
    text = open(path, encoding="utf-8").read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml  # noqa: PLC0415
        except ImportError:
            sys.exit("读取 YAML 需要 PyYAML，装一下 pip install pyyaml；"
                     "不方便装依赖时，用编辑器或在线工具把 YAML 转成 JSON 再传进来，字段完全一致")
        return yaml.safe_load(text)
    return json.loads(text)


class Spec:
    """本地 $ref 解析与 schema 展开（$ref/allOf/oneOf 的处理沿用 openapi-breaking-diff 的思路）。"""

    def __init__(self, doc):
        self.doc = doc
        self.unresolved = set()

    def resolve(self, obj, depth=0):
        if depth > 20 or not isinstance(obj, dict):
            return obj
        ref = obj.get("$ref")
        if isinstance(ref, str):
            if not ref.startswith("#/"):
                self.unresolved.add(ref); return {k: v for k, v in obj.items() if k != "$ref"}
            node = self.doc
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    self.unresolved.add(ref); return {}
            merged = dict(self.resolve(node, depth + 1))
            merged.update({k: v for k, v in obj.items() if k != "$ref"})
            merged.setdefault("_ref", ref.rsplit("/", 1)[-1])
            return merged
        return obj

    def flat(self, schema, depth=0):
        """合并 allOf、展开 oneOf/anyOf 的第一个分支，返回单层 schema。"""
        s = self.resolve(schema, depth)
        if not isinstance(s, dict) or depth > 10:
            return s if isinstance(s, dict) else {}
        if s.get("allOf"):
            merged = {"type": "object", "properties": {}, "required": []}
            for sub in s["allOf"]:
                m = self.flat(sub, depth + 1)
                merged["properties"].update(m.get("properties") or {})
                merged["required"] += list(m.get("required") or [])
                for k, v in m.items():
                    if k not in ("properties", "required", "allOf"):
                        merged.setdefault(k, v)
            for k, v in s.items():
                if k == "allOf":
                    continue
                if k == "properties":
                    merged["properties"].update(v)
                elif k == "required":
                    merged["required"] += list(v)
                else:
                    merged.setdefault(k, v)
            return merged
        alts = s.get("oneOf") or s.get("anyOf")
        if alts:
            m = dict(self.flat(alts[0], depth + 1))
            m["_alt"] = len(alts)
            for k, v in s.items():
                if k not in ("oneOf", "anyOf"):
                    m.setdefault(k, v)
            return m
        return s

    def type_str(self, s):
        t = s.get("type")
        if isinstance(t, list):
            t = "|".join(map(str, t))
        if not t:
            t = "object" if s.get("properties") else (s.get("_ref") or "any")
        if t == "array":
            item = self.flat(s.get("items") or {})
            inner = self.type_str(item) if item else "any"
            return f"array<{inner}>"
        fmt = s.get("format")
        if t == "object" and s.get("_ref"):
            return f"object({s['_ref']})"
        return f"{t}({fmt})" if fmt else t

    def desc_str(self, s):
        bits = []
        d = (s.get("description") or s.get("title") or "").strip().replace("\n", " ")
        if d:
            bits.append(d)
        if s.get("enum"):
            bits.append("可选值 " + " / ".join(f"`{v}`" for v in s["enum"][:8]))
        if s.get("default") is not None:
            bits.append(f"默认 `{s['default']}`")
        rng = [f"{k} {s[k]}" for k in ("minimum", "maximum", "minLength", "maxLength", "pattern") if k in s]
        if rng:
            bits.append("约束 " + "，".join(rng))
        if s.get("deprecated"):
            bits.append("**已废弃**")
        if s.get("_alt"):
            bits.append(f"（oneOf/anyOf 共 {s['_alt']} 种，此处展开第 1 种）")
        return "；".join(bits).replace("|", "\\|")

    def rows(self, schema, prefix="", depth=0, max_depth=4):
        out, s = [], self.flat(schema)
        if not isinstance(s, dict):
            return out
        if s.get("type") == "array" and not s.get("properties"):
            item = self.flat(s.get("items") or {})
            if item.get("properties"):
                return self.rows(item, prefix + "[].", depth, max_depth)
            return out
        req = set(s.get("required") or [])
        for name, sub in (s.get("properties") or {}).items():
            m = self.flat(sub)
            out.append({"name": prefix + name, "type": self.type_str(m), "required": name in req,
                        "desc": self.desc_str(m), "example": brief(self.sample(m))})
            if depth >= max_depth:
                continue
            if m.get("properties"):
                out += self.rows(m, f"{prefix}{name}.", depth + 1, max_depth)
            elif m.get("type") == "array":
                item = self.flat(m.get("items") or {})
                if item.get("properties"):
                    out += self.rows(item, f"{prefix}{name}[].", depth + 1, max_depth)
        return out

    def sample(self, schema, depth=0):
        s = self.flat(schema, depth)
        if not isinstance(s, dict) or depth > 8:
            return None
        if "example" in s:
            return s["example"]
        if s.get("examples"):
            first = list(s["examples"].values())[0] if isinstance(s["examples"], dict) else s["examples"][0]
            return first.get("value") if isinstance(first, dict) and "value" in first else first
        if s.get("default") is not None:
            return s["default"]
        if s.get("enum"):
            return s["enum"][0]
        if s.get("properties"):
            return {k: self.sample(v, depth + 1) for k, v in s["properties"].items()}
        t = s.get("type")
        if t == "array":
            return [self.sample(s.get("items") or {}, depth + 1)]
        if t == "object":
            return {}
        if t == "string":
            return FMT_SAMPLE.get(s.get("format"), "string")
        return {"integer": 0, "number": 0.0, "boolean": True, "null": None}.get(t)


def brief(v):
    if v is None:
        return ""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = s.replace("|", "\\|").replace("\n", " ")
    return f"`{s[:40]}`" if len(s) <= 40 else f"`{s[:37]}...`"


def slug(text):
    s = re.sub(r"[^\w\u4e00-\u9fff \-]", "", text.strip().lower())
    return re.sub(r"\s+", "-", s)


# ---------------------------------------------------------------- 结构化

def build(spec, only_tags, max_depth):
    doc, issues = spec.doc, []
    info = doc.get("info") or {}
    groups, order = {}, []
    for tag in doc.get("tags") or []:
        if isinstance(tag, dict) and tag.get("name"):
            order.append(tag["name"]); groups[tag["name"]] = {"name": tag["name"], "desc": tag.get("description", ""), "ops": []}
    for path, item in (doc.get("paths") or {}).items():
        item = spec.resolve(item) or {}
        common = [spec.resolve(p) for p in (item.get("parameters") or [])]
        for method in METHODS:
            if method not in item:
                continue
            op = spec.resolve(item[method]) or {}
            tags = op.get("tags") or ["未分类"]
            if only_tags and not any(t in only_tags for t in tags):
                continue
            where = f"{method.upper()} {path}"
            if not op.get("summary"):
                issues.append(f"{where} 缺少 summary")
            params = []
            for p in common + [spec.resolve(x) for x in (op.get("parameters") or [])]:
                if not isinstance(p, dict) or not p.get("name"):
                    continue
                sch = spec.flat(p.get("schema") or {})
                if not p.get("description"):
                    issues.append(f"{where} 参数 {p['name']} 缺少说明")
                params.append({"name": p["name"], "in": p.get("in", "query"), "required": bool(p.get("required")) or p.get("in") == "path",
                               "type": spec.type_str(sch), "desc": spec.desc_str({**sch, "description": p.get("description") or sch.get("description")}),
                               "example": brief(p.get("example") if "example" in p else spec.sample(sch))})
            body = None
            rb = spec.resolve(op.get("requestBody") or {}) or {}
            for ct, media in (rb.get("content") or {}).items():
                sch = media.get("schema") or {}
                body = {"content_type": ct, "required": bool(rb.get("required")), "desc": rb.get("description", ""),
                        "fields": spec.rows(sch, max_depth=max_depth),
                        "example": media.get("example") if "example" in media else spec.sample(sch)}
                break
            responses = []
            codes = list((op.get("responses") or {}).keys())
            if not any(str(c).startswith("2") for c in codes):
                issues.append(f"{where} 没有 2xx 响应定义")
            for code in codes:
                r = spec.resolve((op.get("responses") or {})[code]) or {}
                if not r.get("description"):
                    issues.append(f"{where} 响应 {code} 缺少说明")
                entry = {"code": str(code), "desc": r.get("description", ""), "content_type": None, "fields": [], "example": None}
                for ct, media in (r.get("content") or {}).items():
                    sch = media.get("schema") or {}
                    entry.update({"content_type": ct, "fields": spec.rows(sch, max_depth=max_depth),
                                  "example": media.get("example") if "example" in media else spec.sample(sch)})
                    break
                responses.append(entry)
            sec = op.get("security") if "security" in op else doc.get("security")
            entry = {"method": method.upper(), "path": path, "summary": op.get("summary", ""),
                     "description": (op.get("description") or "").strip(), "operation_id": op.get("operationId", ""),
                     "deprecated": bool(op.get("deprecated")), "tags": tags,
                     "security": [k for s in (sec or []) for k in s.keys()], "params": params,
                     "body": body, "responses": responses}
            tag = tags[0]
            if tag not in groups:
                groups[tag] = {"name": tag, "desc": "", "ops": []}; order.append(tag)
            groups[tag]["ops"].append(entry)
    schemes = {k: spec.resolve(v) for k, v in ((doc.get("components") or {}).get("securitySchemes") or {}).items()}
    if spec.unresolved:
        issues += [f"无法解析的 $ref {r}" for r in sorted(spec.unresolved)]
    return {"title": info.get("title", "API 文档"), "version": info.get("version", ""),
            "description": (info.get("description") or "").strip(),
            "servers": [{"url": s.get("url", ""), "desc": s.get("description", "")}
                        for s in (doc.get("servers") or []) if isinstance(s, dict)],
            "security_schemes": {k: {"type": v.get("type"), "scheme": v.get("scheme"), "name": v.get("name"),
                                     "in": v.get("in"), "desc": v.get("description", "")} for k, v in schemes.items()},
            "groups": [groups[t] for t in order if groups.get(t) and groups[t]["ops"]], "issues": issues}


# ---------------------------------------------------------------- 渲染

def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join([" --- "] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def fence(obj):
    return ["```json", json.dumps(obj, ensure_ascii=False, indent=2), "```"]


def render(d, toc=True):
    L = [f"# {d['title']}", ""]
    meta = [x for x in (f"版本 {d['version']}" if d["version"] else "", "本文件由 openapi_to_markdown.py 自动生成，请改 OpenAPI 源文件后重新生成") if x]
    L += ["> " + " · ".join(meta), ""]
    if d["description"]:
        L += [d["description"], ""]
    if d["servers"]:
        L += ["**服务地址**", ""] + [f"- `{s['url']}`" + (f" {s['desc']}" if s.get("desc") else "")
                                     for s in d["servers"]] + [""]
    if d["security_schemes"]:
        L += ["**认证方式**", ""]
        for k, v in d["security_schemes"].items():
            bits = [f"`{k}`", v.get("type") or ""]
            if v.get("scheme"):
                bits.append(f"scheme {v['scheme']}")
            if v.get("name"):
                bits.append(f"{IN_ZH.get(v.get('in'), v.get('in') or '')} 参数 {v['name']}")
            if v.get("desc"):
                bits.append(v["desc"])
            L.append("- " + " · ".join(b for b in bits if b))
        L.append("")
    if toc:
        L += ["## 目录", ""]
        for g in d["groups"]:
            L.append(f"- [{g['name']}](#{slug(g['name'])})")
            for op in g["ops"]:
                title = f"{op['method']} {op['path']}" + (f" {op['summary']}" if op["summary"] else "")
                L.append(f"  - [{title}](#{slug(title)})")
        L.append("")
    for g in d["groups"]:
        L += [f"## {g['name']}", ""]
        if g["desc"]:
            L += [g["desc"], ""]
        for op in g["ops"]:
            title = f"{op['method']} {op['path']}" + (f" {op['summary']}" if op["summary"] else "")
            L += [f"### {title}", ""]
            tags = []
            if op["deprecated"]:
                tags.append("**已废弃，请勿在新代码中使用**")
            if op["security"]:
                tags.append("需要认证 " + "、".join(f"`{s}`" for s in op["security"]))
            if op["operation_id"]:
                tags.append(f"operationId `{op['operation_id']}`")
            if tags:
                L += ["> " + " · ".join(tags), ""]
            if op["description"]:
                L += [op["description"], ""]
            if op["params"]:
                L += ["**请求参数**", ""]
                L += table(["名称", "位置", "必填", "类型", "说明", "示例"],
                           [[f"`{p['name']}`", IN_ZH.get(p["in"], p["in"]), "是" if p["required"] else "否",
                             f"`{p['type']}`", p["desc"] or "-", p["example"] or "-"] for p in op["params"]])
                L.append("")
            if op["body"]:
                b = op["body"]
                L += [f"**请求体** `{b['content_type']}`" + ("（必填）" if b["required"] else "（可选）"), ""]
                if b["desc"]:
                    L += [b["desc"], ""]
                if b["fields"]:
                    L += table(["字段", "类型", "必填", "说明", "示例"],
                               [[f"`{f['name']}`", f"`{f['type']}`", "是" if f["required"] else "否",
                                 f["desc"] or "-", f["example"] or "-"] for f in b["fields"]])
                    L.append("")
                if b["example"] is not None:
                    L += ["请求示例", ""] + fence(b["example"]) + [""]
            if op["responses"]:
                L += ["**响应**", ""]
                for r in op["responses"]:
                    head = f"`{r['code']}`" + (f" {r['desc']}" if r["desc"] else "")
                    L += [head + (f"（{r['content_type']}）" if r["content_type"] else ""), ""]
                    if r["fields"]:
                        L += table(["字段", "类型", "必返回", "说明"],
                                   [[f"`{f['name']}`", f"`{f['type']}`", "是" if f["required"] else "否", f["desc"] or "-"]
                                    for f in r["fields"]])
                        L.append("")
                    if r["example"] is not None and str(r["code"]).startswith("2"):
                        L += ["响应示例", ""] + fence(r["example"]) + [""]
            L.append("---")
            L.append("")
    return "\n".join(L).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="OpenAPI 3.x 生成中文 Markdown 接口文档")
    ap.add_argument("spec", help="OpenAPI 文件（JSON；YAML 需 PyYAML）")
    ap.add_argument("-o", "--out", help="输出文件，默认打印到标准输出")
    ap.add_argument("--tag", action="append", default=[], help="只输出这些 tag，可重复或用逗号分隔")
    ap.add_argument("--max-depth", type=int, default=4, help="嵌套对象展开层数，默认 4")
    ap.add_argument("--no-toc", action="store_true", help="不生成目录")
    ap.add_argument("--json", action="store_true", help="输出中间结构而不是 Markdown")
    ap.add_argument("--strict", action="store_true", help="存在文档缺失则退出码 1（CI 门禁）")
    a = ap.parse_args()

    doc = load(a.spec)
    if not isinstance(doc, dict) or not doc.get("paths"):
        sys.exit("这不是有效的 OpenAPI 文档（缺少 paths）；本脚本只支持 OpenAPI 3.x，Swagger 2.0 请先用 swagger2openapi 转换")
    ver = str(doc.get("openapi") or "")
    if not ver.startswith("3"):
        print(f"提示：openapi 字段为 {ver or '空'}，本脚本按 3.x 解析，结果可能不完整", file=sys.stderr)
    only = {t.strip() for x in a.tag for t in x.split(",") if t.strip()}
    spec = Spec(doc)
    d = build(spec, only, a.max_depth)
    if only and not d["groups"]:
        sys.exit(f"没有匹配 tag {sorted(only)} 的接口；可用 tag 有 " +
                 "、".join(sorted({t for p in (doc.get('paths') or {}).values() if isinstance(p, dict)
                                   for m in METHODS if isinstance(p.get(m), dict) for t in (p[m].get('tags') or ['未分类'])})))
    out = json.dumps(d, ensure_ascii=False, indent=2) if a.json else render(d, not a.no_toc)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        n_ops = sum(len(g["ops"]) for g in d["groups"])
        print(f"已生成 {a.out}：{len(d['groups'])} 个分组 / {n_ops} 个接口 / {len(out)} 字符")
    else:
        print(out)
    if d["issues"]:
        print(f"\n文档完整性提醒（{len(d['issues'])} 条）：", file=sys.stderr)
        for i in d["issues"][:20]:
            print(f"  - {i}", file=sys.stderr)
        if len(d["issues"]) > 20:
            print(f"  …… 还有 {len(d['issues']) - 20} 条", file=sys.stderr)
    sys.exit(1 if (a.strict and d["issues"]) else 0)


if __name__ == "__main__":
    main()
