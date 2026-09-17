#!/usr/bin/env python3
"""多环境配置对比：把 .env / JSON / YAML / .properties / INI 拉平成键路径后逐键对比。

用法：
  python3 config_env_diff.py <配置1> <配置2> [配置3 ...] [--base 文件] [--ignore 模式] [--json] [--strict]
  --strict：存在「仅部分文件有」或「类型不同」则退出码 1。
YAML 只支持常见块结构（映射/列表/标量/块字符串），不支持锚点与合并键。
"""
import argparse, configparser, json, os, re, sys, unicodedata
from fnmatch import fnmatch

SECRET_KEY = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|ACCESS_?KEY|CREDENTIAL|AUTH|SALT|CERT)", re.I)
TYPE_NAME = {bool: "bool", int: "number", float: "number", str: "str", list: "list", dict: "object", type(None): "null"}


# ---------------------------------------------------------------- 标量与最小 YAML 解析
# YAML 部分复制自同仓库 skills/k8s-manifest-check/scripts/k8s_check.py 的最小解析器

def scalar(s):
    s = s.strip()
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s[:1] in ("'", '"') and s[-1:] == s[:1] and len(s) >= 2:
        return s[1:-1]
    if s in ("true", "True", "TRUE", "yes", "on"):
        return True
    if s in ("false", "False", "FALSE", "no", "off"):
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [scalar(x) for x in inner.split(",")] if inner else []
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for kv in s[1:-1].split(","):
            if ":" in kv:
                k, v = kv.split(":", 1)
                out[k.strip()] = scalar(v)
        return out
    return s


def split_kv(line):
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
        elif ch == ":" and (i + 1 == len(line) or line[i + 1] in " \t"):
            return line[:i].strip(), line[i + 1:].strip()
    return None, None


def strip_comment(line):
    q, out = None, []
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_block(lines, i, indent):
    while i < len(lines) and not lines[i][1].strip():
        i += 1
    if i >= len(lines):
        return None, i
    ind, text = lines[i]
    if ind < indent:
        return None, i
    if text.startswith("- ") or text == "-":
        out = []
        while i < len(lines):
            ind, text = lines[i]
            if not text.strip():
                i += 1
                continue
            if ind != indent or not (text.startswith("- ") or text == "-"):
                break
            body = text[1:].strip()
            if not body:
                val, i = parse_block(lines, i + 1, indent + 1)
                out.append(val)
                continue
            k, v = split_kv(body)
            if k is not None and not body.startswith(("'", '"', "[", "{")):
                lines[i] = (indent + 2, body)
                val, i = parse_block(lines, i, indent + 2)
                out.append(val)
            else:
                out.append(scalar(body))
                i += 1
        return out, i
    out = {}
    while i < len(lines):
        ind, text = lines[i]
        if not text.strip():
            i += 1
            continue
        if ind < indent or (ind == indent and (text.startswith("- ") or text == "-")):
            break
        if ind > indent:
            i += 1
            continue
        k, v = split_kv(text)
        if k is None:
            i += 1
            continue
        if v in ("|", "|-", "|+", ">", ">-", ">+"):
            block, j = [], i + 1
            while j < len(lines) and (not lines[j][1].strip() or lines[j][0] > indent):
                block.append(lines[j][1])
                j += 1
            out[k] = "\n".join(block)
            i = j
            continue
        if v == "":
            j = i + 1
            while j < len(lines) and not lines[j][1].strip():
                j += 1
            if j < len(lines) and (lines[j][0] > indent or (lines[j][0] == indent and lines[j][1].startswith("- "))):
                out[k], i = parse_block(lines, j, lines[j][0])
            else:
                out[k] = None
                i = j
            continue
        if v.startswith("&"):
            v = v.split(" ", 1)[1] if " " in v else ""
        out[k] = scalar(v)
        i += 1
    return out, i


def load_yaml(text):
    chunk = re.split(r"^---\s*$", text, flags=re.M)
    body = next((c for c in chunk if c.strip()), "")
    raw = [strip_comment(l.replace("\t", "  ")) for l in body.splitlines()]
    lines = [(len(l) - len(l.lstrip(" ")), l.strip()) for l in raw if l.strip() and not l.strip().startswith("%")]
    if not lines:
        return {}
    doc, _ = parse_block(lines, 0, lines[0][0])
    return doc if isinstance(doc, (dict, list)) else {}


# ---------------------------------------------------------------- 各格式解析

def load_env(text):
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v[:1] in ("'", '"') and v[-1:] == v[:1] and len(v) >= 2:
            v = v[1:-1]
        else:
            v = v.split(" #", 1)[0].strip()
        out[k] = scalar(v) if v != "" else ""
    return out


def load_properties(text):
    out, buf = {}, ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line[:1] in ("#", "!")):
            continue
        if line.endswith("\\"):
            buf += line[:-1]
            continue
        buf += line
        m = re.match(r"([^=:\s]+)\s*[=:]\s*(.*)$", buf)
        if m:
            out[m.group(1)] = scalar(m.group(2).strip()) if m.group(2).strip() != "" else ""
        buf = ""
    return out


def load_ini(text):
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=", ":"))
    cp.optionxform = str
    try:
        cp.read_string(text)
    except configparser.Error as e:
        raise ValueError(f"INI 解析失败：{e}") from e
    out = {}
    for sec in cp.sections():
        for k, v in cp.items(sec):
            out[f"{sec}.{k}"] = scalar(v) if v is not None and v != "" else ""
    for k, v in cp.defaults().items():
        out.setdefault(k, scalar(v) if v else "")
    return out


def sniff(path, text):
    ext = os.path.splitext(path)[1].lower()
    base = os.path.basename(path).lower()
    if ext in (".json",):
        return "json"
    if ext in (".yaml", ".yml"):
        return "yaml"
    if ext in (".properties",):
        return "properties"
    if ext in (".ini", ".cfg", ".conf", ".toml"):
        return "ini"
    if base.startswith(".env") or ext == ".env" or ".env." in base:
        return "env"
    head = text.lstrip()[:1]
    if head in ("{", "["):
        return "json"
    if re.search(r"^\s*\[[^\]]+\]\s*$", text, re.M):
        return "ini"
    if re.search(r"^\s*[\w.-]+:\s", text, re.M) or re.search(r"^\s+-\s", text, re.M):
        return "yaml"
    return "env"


def load(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    kind = sniff(path, text)
    if kind == "json":
        data = json.loads(text)
        return flatten(data), kind
    if kind == "yaml":
        return flatten(load_yaml(text)), kind
    if kind == "properties":
        return load_properties(text), kind
    if kind == "ini":
        return load_ini(text), kind
    return load_env(text), kind


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = {}
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        if not obj and prefix:
            out[prefix] = []
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix or "(root)"] = obj
    return out


# ---------------------------------------------------------------- 对比

def tname(v):
    return TYPE_NAME.get(type(v), type(v).__name__)


def fmt(v, width):
    if v is None:
        s = "null"
    elif isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    s = s.replace("\n", "\\n")
    return s if len(s) <= width else s[:width - 1] + "…"


def mask(v):
    s = "" if v is None else str(v)
    if len(s) <= 4:
        return "*" * max(len(s), 4)
    return f"{s[:2]}{'*' * min(6, len(s) - 4)}{s[-2:]}"


def compare(files, ignores, do_mask, width):
    labels = [f["label"] for f in files]
    keys = sorted({k for f in files for k in f["data"]})
    rows = []
    for key in keys:
        if any(fnmatch(key, p) for p in ignores):
            continue
        present = [key in f["data"] for f in files]
        vals = [f["data"].get(key) for f in files]
        secret = bool(SECRET_KEY.search(key)) and do_mask
        cells = []
        for ok, v in zip(present, vals):
            if not ok:
                cells.append("（缺失）")
            elif secret:
                cells.append(mask(v))
            else:
                cells.append(fmt(v, width))
        if not all(present):
            kind, sev = "missing", "high"
        else:
            types = {tname(v) for v in vals}
            uniq = {json.dumps(v, ensure_ascii=False, sort_keys=True) for v in vals}
            if len(types) > 1:
                kind, sev = "type", "warn"
                cells = [f"{c} ({tname(v)})" for c, v in zip(cells, vals)]  # 类型差异要看得见类型
            elif len(uniq) > 1:
                kind, sev = "value", "info"
            else:
                continue
        rows.append({"key": key, "kind": kind, "severity": sev, "cells": cells,
                     "types": [tname(v) if ok else "-" for ok, v in zip(present, vals)],
                     "present": present, "masked": secret,
                     "values": ["(masked)" if secret else v for v in vals],
                     "missing_in": [labels[i] for i, ok in enumerate(present) if not ok]})
    return rows


# ---------------------------------------------------------------- 输出

def dw(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, w):
    return s + " " * max(0, w - dw(s))


def table(rows, labels, note):
    head = ["键"] + labels
    cols = [max([dw(head[0])] + [dw(r["key"]) for r in rows])] + \
           [max([dw(head[i + 1])] + [dw(r["cells"][i]) for r in rows]) for i in range(len(labels))]
    print("  " + "  ".join(pad(h, c) for h, c in zip(head, cols)))
    print("  " + "  ".join("-" * c for c in cols))
    for r in rows:
        print("  " + "  ".join(pad(x, c) for x, c in zip([r["key"]] + r["cells"], cols)))
    if note:
        print(f"  {note}")


def main():
    ap = argparse.ArgumentParser(description="多环境配置对比")
    ap.add_argument("files", nargs="+", help="两份或多份配置文件")
    ap.add_argument("--base", help="以哪份为基准（默认第一个），影响列顺序与 diff 叙述")
    ap.add_argument("--ignore", action="append", default=[], help="忽略的键模式（fnmatch，可重复），如 --ignore 'BUILD_*'")
    ap.add_argument("--no-mask", action="store_true", help="不脱敏密钥类键值（默认脱敏）")
    ap.add_argument("--width", type=int, default=28, help="值列最大宽度")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 missing/type 差异则退出码 1")
    a = ap.parse_args()

    if len(a.files) < 2:
        print("至少需要两份配置文件", file=sys.stderr)
        sys.exit(2)
    files = []
    for p in a.files:
        if not os.path.isfile(p):
            print(f"文件不存在：{p}", file=sys.stderr)
            sys.exit(2)
        try:
            data, kind = load(p)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"{p} 解析失败：{e}", file=sys.stderr)
            sys.exit(2)
        files.append({"path": p, "label": os.path.basename(p), "kind": kind, "data": data})
    if a.base:
        idx = next((i for i, f in enumerate(files) if f["path"] == a.base or f["label"] == a.base), None)
        if idx is None:
            print(f"--base 不在文件列表里：{a.base}", file=sys.stderr)
            sys.exit(2)
        files.insert(0, files.pop(idx))
    # 同名文件加目录前缀区分
    if len({f["label"] for f in files}) < len(files):
        for f in files:
            f["label"] = os.path.join(os.path.basename(os.path.dirname(os.path.abspath(f["path"]))), f["label"])

    labels = [f["label"] for f in files]
    rows = compare(files, a.ignore, not a.no_mask, a.width)
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in ("missing", "type", "value")}
    same = len({k for f in files for k in f["data"]}) - len(rows)

    if a.json:
        print(json.dumps({"files": [{"path": f["path"], "label": f["label"], "format": f["kind"],
                                     "keys": len(f["data"])} for f in files],
                          "base": labels[0], "same_keys": same, "summary": counts,
                          "diffs": [{k: r[k] for k in ("key", "kind", "severity", "types", "present",
                                                       "masked", "values", "missing_in")} for r in rows]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"== 对比 {len(files)} 份配置（基准 {labels[0]}）")
        for f in files:
            print(f"  {pad(f['label'], max(dw(l) for l in labels))}  {f['kind']:10s} {len(f['data'])} 个键")
        for kind, sev, title, tip in (
                ("missing", "HIGH", "仅部分文件有", "缺的那一侧上线后会读到空值或走默认分支，先确认是漏配还是有意为之"),
                ("type", "WARN", "类型不同", "同一键在不同环境是不同类型，反序列化/强类型配置框架会直接报错"),
                ("value", "INFO", "值不同", "环境差异多数正常；重点看超时、开关、域名、副本数这类会改变行为的键")):
            sub = [r for r in rows if r["kind"] == kind]
            print(f"\n[{sev}] {title}（{len(sub)}）")
            if not sub:
                print("  ✓ 无")
                continue
            table(sub, labels, None)
            print(f"  → {tip}")
        print(f"\n小计：仅部分文件有 {counts['missing']} / 类型不同 {counts['type']} / 值不同 {counts['value']}"
              f"，完全一致的键 {same} 个")
        if any(r["masked"] for r in rows):
            print("  密钥类键值已脱敏（前 2 后 2 位），需要原值请加 --no-mask")
    sys.exit(1 if (a.strict and (counts["missing"] or counts["type"])) else 0)


if __name__ == "__main__":
    main()
