#!/usr/bin/env python3
"""两份建表 SQL 的结构对比：列 / 主键 / 索引 / 外键差异 + 迁移 SQL 草稿，纯标准库。

用法：
  python3 schema_diff.py old.sql new.sql                  # 文本报告 + 迁移草稿
  python3 schema_diff.py old.sql new.sql --dialect mysql --sql     # 只要迁移 SQL
  python3 schema_diff.py old.sql new.sql --json
  python3 schema_diff.py old.sql new.sql --strict          # 有 high（破坏性/锁表）退出码 1
输入：mysqldump --no-data 或 pg_dump -s 的输出，也接受手写的建表脚本。
实现：正则与括号配对的启发式解析，认 CREATE TABLE、CREATE INDEX、ALTER TABLE ADD CONSTRAINT、
      COMMENT ON COLUMN；看不懂的语句跳过并在报告里给出条数。
"""
import argparse, json, os, re, sys

IDENT = "`\"[]"
TYPE_CONT = {"unsigned", "zerofill", "signed", "precision", "varying", "with", "without", "time", "zone", "array"}
COL_STOP = {"not", "null", "default", "auto_increment", "comment", "collate", "primary", "unique", "key",
            "references", "check", "generated", "as", "stored", "virtual", "on", "srid", "invisible",
            "visible", "constraint", "identity", "storage", "encoding", "enforced"}
TYPE_ALIAS = {"integer": "int", "int4": "int", "int8": "bigint", "int2": "smallint", "bool": "boolean",
              "character varying": "varchar", "character": "char", "numeric": "decimal", "dec": "decimal",
              "timestamp without time zone": "timestamp", "timestamp with time zone": "timestamptz",
              "time without time zone": "time", "double precision": "double", "float8": "double", "float4": "float"}
NO_WIDTH = ("int", "bigint", "smallint", "tinyint", "mediumint")


# ---------------------------------------------------------------- 词法与切分
def strip_comments(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            q = c; out.append(c); i += 1
            while i < n:
                if text[i] == "\\" and q != "`" and i + 1 < n:
                    out.append(text[i:i + 2]); i += 2; continue
                out.append(text[i])
                if text[i] == q:
                    if i + 1 < n and text[i + 1] == q:
                        out.append(text[i + 1]); i += 2; continue
                    i += 1; break
                i += 1
            continue
        if text[i:i + 2] == "--" or (c == "#" and text[i:i + 2] != "#("):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text[i:i + 2] == "/*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" "); continue
        out.append(c); i += 1
    return "".join(out)


def split_top(s, sep=","):
    """按分隔符切分，跳过括号内与引号内的分隔符。"""
    out, buf, depth, q = [], [], 0, None
    for ch in s:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"`":
            q = ch; buf.append(ch); continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf)); buf = []; continue
        buf.append(ch)
    if "".join(buf).strip():
        out.append("".join(buf))
    return out


def tokens(s):
    """切成词：引号串、括号组、标识符、符号。"""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1; continue
        if c in "'\"`":
            j, q = i + 1, c
            while j < n:
                if s[j] == "\\" and q != "`":
                    j += 2; continue
                if s[j] == q:
                    if j + 1 < n and s[j + 1] == q:
                        j += 2; continue
                    break
                j += 1
            out.append(s[i:j + 1]); i = j + 1; continue
        if c == "(":
            depth, j = 0, i
            while j < n:
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(s[i:j + 1]); i = j + 1; continue
        m = re.match(r"[\w$.]+", s[i:])
        if m:
            out.append(m.group(0)); i += len(m.group(0)); continue
        out.append(c); i += 1
    return out


def unquote(x):
    x = x.strip()
    while x and x[0] in IDENT:
        x = x[1:-1] if len(x) > 1 and x[-1] in IDENT else x[1:]
    return x.strip()


def unq_str(x):
    """字符串字面量去引号，并还原 SQL 里的 '' 转义。"""
    x = x.strip()
    if len(x) > 1 and x[0] == x[-1] and x[0] in "'\"":
        return x[1:-1].replace(x[0] * 2, x[0])
    return unquote(x)


def sq(x):
    """包成 SQL 字符串字面量。"""
    return "'" + str(x).replace("'", "''") + "'"


def table_key(name):
    n = unquote(name.strip())
    if "." in n:
        sch, _, t = n.rpartition(".")
        return unquote(t) if unquote(sch) in ("public", "dbo") else f"{unquote(sch)}.{unquote(t)}"
    return n


def col_list(group):
    """'(a, b(10), "c" DESC)' -> ['a','b','c']"""
    inner = group.strip()
    if inner.startswith("("):
        inner = inner[1:-1]
    out = []
    for p in split_top(inner):
        p = p.strip()
        p = re.sub(r"\s+(asc|desc)$", "", p, flags=re.I)
        p = re.sub(r"\(\d+\)$", "", p.strip())
        out.append(unquote(p))
    return [x for x in out if x]


# ---------------------------------------------------------------- 结构解析
def norm_type(t):
    """归一化类型，抹掉 dump 噪声：显示宽度 int(11)、大小写、空格、方言别名、修饰词顺序。"""
    t = re.sub(r"\s+", " ", t.strip().lower())
    t = re.sub(r"\s*,\s*", ",", t)
    m = re.match(r"^([a-z0-9_ ]+?)\s*\(([^)]*)\)\s*(.*)$", t)
    base, args, suffix = (m.group(1).strip(), m.group(2).strip(), m.group(3).strip()) if m else (t, None, "")
    words, mods = base.split(), []
    while words and words[-1] in ("unsigned", "zerofill", "signed"):
        mods.insert(0, words.pop())
    base = " ".join(words)
    for w in suffix.split():
        if w in ("unsigned", "zerofill", "signed", "array"):
            mods.append(w)
    if "with time zone" in suffix:
        base += "tz"
    for long, short in TYPE_ALIAS.items():
        if base == long:
            base = short; break
    if base in NO_WIDTH:
        args = None                                 # int(11) 与 int 等价，MySQL 8 已废弃显示宽度
    return " ".join([base + (f"({args})" if args else "")] + sorted(set(mods)))


def norm_default(d):
    if d is None:
        return None
    x = d.strip()
    x = re.sub(r"::[\w\s\"]+$", "", x)               # PG 的 ::text 之类的强制转换
    if len(x) > 1 and x[0] in "'\"" and x[-1] == x[0]:
        x = x[1:-1]
    low = x.lower().replace(" ", "")
    if low in ("current_timestamp()", "now()", "current_timestamp"):
        return "current_timestamp"
    return x.lower() if low in ("null", "true", "false") else x


def parse_column(defn):
    tk = tokens(defn)
    if not tk:
        return None
    name = unquote(tk[0])
    i, ty = 1, []
    while i < len(tk):
        w = tk[i].lower()
        if w == "character" and i + 1 < len(tk) and tk[i + 1].lower() == "set":
            break
        if ty and w in COL_STOP and w not in TYPE_CONT:
            break
        if ty and not (w in TYPE_CONT or tk[i].startswith("(")):
            break
        ty.append(tk[i]); i += 1
    raw_type = " ".join(ty).replace(" (", "(")
    rest = tk[i:]
    low = [w.lower() for w in rest]
    nullable = not ("not" in low and low.index("not") + 1 < len(low) and low[low.index("not") + 1] == "null")
    default = None
    if "default" in low:
        j = low.index("default") + 1
        if j < len(rest):
            default = rest[j]
            if j + 1 < len(rest) and rest[j + 1].startswith("("):     # nextval(...) / now()
                default += rest[j + 1]
            if j + 1 < len(rest) and rest[j + 1].lower().startswith("::"):
                default += rest[j + 1]
    comment = None
    if "comment" in low:
        j = low.index("comment") + 1
        if j < len(rest):
            comment = unq_str(rest[j])
    extra = []
    if "auto_increment" in low:
        extra.append("auto_increment")
    if "identity" in low or (default and "nextval" in str(default).lower()):
        extra.append("identity")
    if "generated" in low and "always" in low and "identity" not in low:
        extra.append("generated")
    return {"name": name, "type": raw_type, "type_norm": norm_type(raw_type), "nullable": nullable,
            "default": default, "default_norm": norm_default(default), "comment": comment,
            "extra": sorted(extra), "raw": " ".join(defn.split())}


def new_table(name):
    return {"name": name, "cols": {}, "order": [], "pk": [], "indexes": {}, "fks": {}, "options": {}, "ddl": ""}


def parse_create_table(stmt, tables, skipped):
    m = re.match(r"^\s*create\s+(?:temporary\s+|unlogged\s+|global\s+|local\s+)*table\s+(?:if\s+not\s+exists\s+)?"
                 r"([`\"\[\]\w$.]+)\s*(\(.*)$", stmt, re.I | re.S)
    if not m:
        skipped.append(stmt[:80]); return
    name = table_key(m.group(1))
    body_all = m.group(2).strip()
    depth, end = 0, len(body_all)
    for idx, ch in enumerate(body_all):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = idx; break
    body, tail = body_all[1:end], body_all[end + 1:]
    t = tables.setdefault(name, new_table(name))
    t["ddl"] = " ".join(stmt.split())
    for item in split_top(body):
        s = item.strip()
        if not s:
            continue
        low = s.lower()
        cons = re.match(r"^constraint\s+([`\"\[\]\w$.]+)\s+(.*)$", s, re.I | re.S)
        cname, rest = (unquote(cons.group(1)), cons.group(2).strip()) if cons else (None, s)
        rl = rest.lower()
        if rl.startswith("primary key"):
            g = re.search(r"\((.*)\)", rest, re.S)
            t["pk"] = col_list(g.group(0)) if g else []
        elif rl.startswith(("unique key", "unique index", "unique (", "unique(")):
            g = re.search(r"\((.*)\)", rest, re.S)
            nm = cname or unquote(re.sub(r"^unique\s+(key|index)\s*", "", rest, flags=re.I).split("(")[0]) or "uniq_?"
            t["indexes"][nm or "uniq_?"] = {"unique": True, "cols": col_list(g.group(0)) if g else []}
        elif rl.startswith(("key ", "key(", "index ", "index(", "fulltext", "spatial")):
            g = re.search(r"\((.*)\)", rest, re.S)
            nm = unquote(re.sub(r"^(fulltext|spatial)?\s*(key|index)\s*", "", rest, flags=re.I).split("(")[0])
            t["indexes"][nm or "idx_?"] = {"unique": False, "cols": col_list(g.group(0)) if g else []}
        elif rl.startswith("foreign key"):
            fm = re.match(r"foreign\s+key\s*(\([^)]*\))\s*references\s+([`\"\[\]\w$.]+)\s*(\([^)]*\))?(.*)$", rest, re.I | re.S)
            if fm:
                acts = " ".join(fm.group(4).split()).upper() if fm.group(4) else ""
                t["fks"][cname or f"fk_{'_'.join(col_list(fm.group(1)))}"] = {
                    "cols": col_list(fm.group(1)), "ref_table": table_key(fm.group(2)),
                    "ref_cols": col_list(fm.group(3)) if fm.group(3) else [],
                    "actions": " ".join(x for x in acts.split() if x in ("ON", "DELETE", "UPDATE", "CASCADE", "RESTRICT", "SET", "NULL", "NO", "ACTION"))}
        elif rl.startswith("check") or low.startswith(("exclude", "like ", "inherits")):
            continue
        else:
            c = parse_column(s)
            if c and c["name"]:
                if re.search(r"\bprimary\s+key\b", s, re.I):
                    t["pk"] = [c["name"]]
                if re.search(r"\bunique\b", s, re.I) and not re.search(r"\bunique\s*\(", s, re.I):
                    t["indexes"].setdefault(f"uniq_{c['name']}", {"unique": True, "cols": [c["name"]]})
                t["cols"][c["name"]] = c
                t["order"].append(c["name"])
    for k, pat in (("engine", r"engine\s*=\s*(\w+)"), ("charset", r"(?:default\s+)?charset\s*=\s*(\w+)"),
                   ("collate", r"collate\s*=\s*(\w+)"), ("comment", r"comment\s*=\s*('(?:[^']|'')*')")):
        mm = re.search(pat, tail, re.I)
        if mm:
            t["options"][k] = unquote(mm.group(1))
    for c in t["cols"].values():                      # 主键列隐含 NOT NULL，统一口径
        if c["name"] in t["pk"]:
            c["nullable"] = False


def parse_sql(text, stats):
    tables, skipped = {}, []
    for raw in split_top(strip_comments(text), ";"):
        stmt = raw.strip()
        if not stmt:
            continue
        low = stmt.lower()
        if re.match(r"^create\s+(temporary\s+|unlogged\s+|global\s+|local\s+)*table\b", low):
            parse_create_table(stmt, tables, skipped)
        elif re.match(r"^create\s+(unique\s+)?index\b", low) or re.match(r"^create\s+index\b", low):
            m = re.match(r"^create\s+(unique\s+)?index\s+(?:concurrently\s+)?(?:if\s+not\s+exists\s+)?"
                         r"([`\"\[\]\w$.]+)\s+on\s+(?:only\s+)?([`\"\[\]\w$.]+)\s*(?:using\s+\w+\s*)?(\(.*\))", stmt, re.I | re.S)
            if m:
                t = tables.setdefault(table_key(m.group(3)), new_table(table_key(m.group(3))))
                t["indexes"][unquote(m.group(2))] = {"unique": bool(m.group(1)), "cols": col_list(m.group(4))}
            else:
                skipped.append(stmt[:80])
        elif re.match(r"^alter\s+table\b", low):
            m = re.match(r"^alter\s+table\s+(?:only\s+)?(?:if\s+exists\s+)?([`\"\[\]\w$.]+)\s+(.*)$", stmt, re.I | re.S)
            if not m:
                skipped.append(stmt[:80]); continue
            t = tables.setdefault(table_key(m.group(1)), new_table(table_key(m.group(1))))
            body = m.group(2).strip()
            c = re.match(r"add\s+constraint\s+([`\"\[\]\w$.]+)\s+(.*)$", body, re.I | re.S)
            if c:
                cname, rest = unquote(c.group(1)), c.group(2).strip()
                rl = rest.lower()
                if rl.startswith("primary key"):
                    t["pk"] = col_list(re.search(r"\((.*)\)", rest, re.S).group(0))
                elif rl.startswith("unique"):
                    t["indexes"][cname] = {"unique": True, "cols": col_list(re.search(r"\((.*)\)", rest, re.S).group(0))}
                elif rl.startswith("foreign key"):
                    fm = re.match(r"foreign\s+key\s*(\([^)]*\))\s*references\s+([`\"\[\]\w$.]+)\s*(\([^)]*\))?(.*)$", rest, re.I | re.S)
                    if fm:
                        t["fks"][cname] = {"cols": col_list(fm.group(1)), "ref_table": table_key(fm.group(2)),
                                           "ref_cols": col_list(fm.group(3)) if fm.group(3) else [],
                                           "actions": " ".join(fm.group(4).split()).upper()}
                else:
                    skipped.append(stmt[:80])
                continue
            a = re.match(r"alter\s+column\s+([`\"\[\]\w$.]+)\s+(.*)$", body, re.I | re.S)
            if a and unquote(a.group(1)) in t["cols"]:
                col, act = t["cols"][unquote(a.group(1))], a.group(2).strip().lower()
                if act.startswith("set not null"):
                    col["nullable"] = False
                elif act.startswith("drop not null"):
                    col["nullable"] = True
                elif act.startswith("set default"):
                    col["default"] = a.group(2).strip()[len("set default"):].strip()
                    col["default_norm"] = norm_default(col["default"])
                continue
            skipped.append(stmt[:80])
        elif re.match(r"^comment\s+on\s+column\b", low):
            m = re.match(r"^comment\s+on\s+column\s+([`\"\[\]\w$.]+)\.([`\"\[\]\w$]+)\s+is\s+(.*)$", stmt, re.I | re.S)
            if m and table_key(m.group(1)) in tables:
                t = tables[table_key(m.group(1))]
                if unquote(m.group(2)) in t["cols"]:
                    t["cols"][unquote(m.group(2))]["comment"] = unq_str(m.group(3).strip())
        else:
            skipped.append(stmt[:80])
    stats["tables"] = len(tables)
    stats["skipped"] = len(skipped)
    stats["skipped_samples"] = skipped[:5]
    return tables


def detect_dialect(*texts):
    blob = "\n".join(texts)[:200000].lower()
    my = blob.count("`") + blob.count("engine=") * 5 + blob.count("auto_increment") * 3 + blob.count("unsigned")
    pg = blob.count("::") * 3 + blob.count("nextval") * 5 + blob.count("using btree") * 5 + blob.count("public.") * 2 \
        + blob.count("without time zone") * 3 + blob.count("bigserial") * 3
    return "postgres" if pg > my else "mysql"


# ---------------------------------------------------------------- 差异
def diff_tables(old, new):
    d = {"tables_added": sorted(set(new) - set(old)), "tables_removed": sorted(set(old) - set(new)), "tables": {}}
    for name in sorted(set(old) & set(new)):
        o, n = old[name], new[name]
        ch = {"columns_added": [], "columns_removed": [], "column_changes": [], "indexes_added": [],
              "indexes_removed": [], "indexes_changed": [], "fks_added": [], "fks_removed": [],
              "pk_change": None, "options_changed": []}
        for c in n["order"]:
            if c not in o["cols"]:
                ch["columns_added"].append(n["cols"][c])
        for c in o["order"]:
            if c not in n["cols"]:
                ch["columns_removed"].append(o["cols"][c])
        for c in n["order"]:
            if c not in o["cols"]:
                continue
            a, b = o["cols"][c], n["cols"][c]
            if a["type_norm"] != b["type_norm"]:
                ch["column_changes"].append({"column": c, "kind": "type", "old": a["type"], "new": b["type"], "def": b})
            if a["nullable"] != b["nullable"]:
                ch["column_changes"].append({"column": c, "kind": "nullable", "old": "NULL" if a["nullable"] else "NOT NULL",
                                             "new": "NULL" if b["nullable"] else "NOT NULL", "def": b})
            if a["default_norm"] != b["default_norm"]:
                ch["column_changes"].append({"column": c, "kind": "default", "old": a["default"], "new": b["default"], "def": b})
            if (a["comment"] or "") != (b["comment"] or ""):
                ch["column_changes"].append({"column": c, "kind": "comment", "old": a["comment"], "new": b["comment"], "def": b})
            if a["extra"] != b["extra"]:
                ch["column_changes"].append({"column": c, "kind": "extra", "old": ",".join(a["extra"]) or "-",
                                             "new": ",".join(b["extra"]) or "-", "def": b})
        for k, v in n["indexes"].items():
            if k not in o["indexes"]:
                ch["indexes_added"].append(dict(v, name=k))
            elif o["indexes"][k]["cols"] != v["cols"] or o["indexes"][k]["unique"] != v["unique"]:
                ch["indexes_changed"].append({"name": k, "old": o["indexes"][k], "new": v})
        for k, v in o["indexes"].items():
            if k not in n["indexes"]:
                ch["indexes_removed"].append(dict(v, name=k))
        for k, v in n["fks"].items():
            if k not in o["fks"]:
                ch["fks_added"].append(dict(v, name=k))
        for k, v in o["fks"].items():
            if k not in n["fks"]:
                ch["fks_removed"].append(dict(v, name=k))
        if o["pk"] != n["pk"]:
            ch["pk_change"] = {"old": o["pk"], "new": n["pk"]}
        for k in set(o["options"]) | set(n["options"]):
            if o["options"].get(k) != n["options"].get(k):
                ch["options_changed"].append({"key": k, "old": o["options"].get(k), "new": n["options"].get(k)})
        if any(v for v in ch.values()):
            d["tables"][name] = ch
    return d


def severity(kind, detail=None):
    if kind in ("table_removed", "column_removed", "type_change", "pk_change"):
        return "high"
    if kind == "nullable_change" and detail == "NOT NULL":
        return "high"
    if kind == "unique_added":
        return "high"
    if kind in ("index_removed", "fk_added", "fk_removed", "default_change", "index_changed", "extra_change", "options"):
        return "warn"
    return "info"


# ---------------------------------------------------------------- 迁移草稿
def q(name, dialect):
    return f"`{name}`" if dialect == "mysql" else '"' + name + '"'


def migration(d, old, new, dialect):
    sql, locks = [], []
    for t in d["tables_added"]:
        sql.append(new[t]["ddl"].rstrip(";") + ";")
    for t in d["tables_removed"]:
        sql.append(f"-- [破坏性] 删表不可逆，确认没有任何读写后再手工执行\n-- DROP TABLE {q(t, dialect)};")
    for name, ch in d["tables"].items():
        tq = q(name, dialect)
        for c in ch["columns_added"]:
            if dialect == "mysql":
                sql.append(f"ALTER TABLE {tq} ADD COLUMN {c['raw']};")
            else:
                bits = [f"{q(c['name'], dialect)} {c['type']}"]
                if c["default"] is not None:
                    bits.append(f"DEFAULT {c['default']}")
                if not c["nullable"]:
                    bits.append("NOT NULL")
                sql.append(f"ALTER TABLE {tq} ADD COLUMN {' '.join(bits)};")
                if c["comment"]:
                    sql.append(f"COMMENT ON COLUMN {tq}.{q(c['name'], dialect)} IS {sq(c['comment'])};")
            if not c["nullable"] and c["default"] is None:
                locks.append(f"{name}.{c['name']}：新增 NOT NULL 且无默认值，存量行会失败，先加默认值或分两步上线")
        for c in ch["columns_removed"]:
            sql.append(f"-- [破坏性] 删列会丢数据，确认代码已不再引用\n-- ALTER TABLE {tq} DROP COLUMN {q(c['name'], dialect)};")
        touched = []                                  # MySQL 把同一列的多处变化合成一条 MODIFY
        for c in ch["column_changes"]:
            col, b = c["column"], c["def"]
            if c["kind"] == "type":
                locks.append(f"{name}.{col}：改类型 {c['old']} → {c['new']} 会重建表/全表校验，大表请用 gh-ost、pt-osc 或 PG 的加列换列法")
            if c["kind"] == "nullable" and c["new"] == "NOT NULL":
                locks.append(f"{name}.{col}：加 NOT NULL 需要全表校验，存量 NULL 会直接报错，先回填再改")
            if dialect == "mysql":
                if col not in touched:
                    touched.append(col)
                    sql.append(f"ALTER TABLE {tq} MODIFY COLUMN {b['raw']};")
                continue
            if c["kind"] == "type":
                sql.append(f"ALTER TABLE {tq} ALTER COLUMN {q(col, dialect)} TYPE {b['type']} "
                           f"USING {q(col, dialect)}::{b['type']};")
            elif c["kind"] == "nullable":
                sql.append(f"ALTER TABLE {tq} ALTER COLUMN {q(col, dialect)} "
                           f"{'SET' if c['new'] == 'NOT NULL' else 'DROP'} NOT NULL;")
            elif c["kind"] == "default":
                sql.append(f"ALTER TABLE {tq} ALTER COLUMN {q(col, dialect)} "
                           f"{'SET DEFAULT ' + str(c['new']) if c['new'] is not None else 'DROP DEFAULT'};")
            elif c["kind"] == "comment" and c["new"]:
                sql.append(f"COMMENT ON COLUMN {tq}.{q(col, dialect)} IS {sq(c['new'])};")
        for ix in ch["indexes_added"]:
            cols = ", ".join(q(c, dialect) for c in ix["cols"])
            if dialect == "mysql":
                sql.append(f"ALTER TABLE {tq} ADD {'UNIQUE ' if ix['unique'] else ''}INDEX {q(ix['name'], dialect)} ({cols});")
            else:
                sql.append(f"CREATE {'UNIQUE ' if ix['unique'] else ''}INDEX CONCURRENTLY {q(ix['name'], dialect)} ON {tq} ({cols});")
            if ix["unique"]:
                locks.append(f"{name}.{ix['name']}：加唯一索引，存量重复值会导致失败，先跑一遍 GROUP BY 查重")
            elif dialect == "mysql":
                locks.append(f"{name}.{ix['name']}：MySQL 5.6+ 加普通索引是 online DDL，但大表仍有主从延迟风险")
        for ix in ch["indexes_removed"]:
            if dialect == "mysql":
                sql.append(f"-- [破坏性] 确认没有查询依赖该索引\n-- ALTER TABLE {tq} DROP INDEX {q(ix['name'], dialect)};")
            else:
                sql.append(f"-- [破坏性] 确认没有查询依赖该索引\n-- DROP INDEX CONCURRENTLY {q(ix['name'], dialect)};")
        for fk in ch["fks_added"]:
            cols = ", ".join(q(c, dialect) for c in fk["cols"])
            ref = ", ".join(q(c, dialect) for c in fk["ref_cols"]) or "id"
            base = (f"ALTER TABLE {tq} ADD CONSTRAINT {q(fk['name'], dialect)} FOREIGN KEY ({cols}) "
                    f"REFERENCES {q(fk['ref_table'], dialect)} ({ref})")
            sql.append(base + (";" if dialect == "mysql" else " NOT VALID;"))
            if dialect != "mysql":
                sql.append(f"ALTER TABLE {tq} VALIDATE CONSTRAINT {q(fk['name'], dialect)};")
            locks.append(f"{name}.{fk['name']}：加外键会校验存量数据并对被引用表加锁，先确认孤儿行")
        for fk in ch["fks_removed"]:
            drop = "DROP FOREIGN KEY" if dialect == "mysql" else "DROP CONSTRAINT"
            sql.append(f"-- [破坏性] 确认业务不再依赖该约束\n-- ALTER TABLE {tq} {drop} {q(fk['name'], dialect)};")
        if ch["pk_change"]:
            locks.append(f"{name}：主键变化 {ch['pk_change']['old']} → {ch['pk_change']['new']}，等于重建整张表，必须停机或用在线改表工具")
            sql.append(f"-- [高危] 主键变化需要单独评审，草稿不自动生成 ALTER；old={ch['pk_change']['old']} new={ch['pk_change']['new']}")
    return sql, locks


# ---------------------------------------------------------------- 报告
def collect_findings(d):
    f = []

    def add(sev, table, text):
        f.append({"severity": sev, "table": table, "change": text})

    for t in d["tables_added"]:
        add("info", t, "新增表")
    for t in d["tables_removed"]:
        add("high", t, "删除表")
    for name, ch in d["tables"].items():
        for c in ch["columns_added"]:
            sev = "high" if (not c["nullable"] and c["default"] is None) else "info"
            add(sev, name, f"新增列 {c['name']} {c['type']} {'NOT NULL' if not c['nullable'] else 'NULL'}"
                           + (f" DEFAULT {c['default']}" if c["default"] is not None else ""))
        for c in ch["columns_removed"]:
            add("high", name, f"删除列 {c['name']} {c['type']}")
        for c in ch["column_changes"]:
            kind = {"type": "类型", "nullable": "可空性", "default": "默认值", "comment": "注释", "extra": "属性"}[c["kind"]]
            sev = severity({"type": "type_change", "nullable": "nullable_change", "default": "default_change",
                            "comment": "comment", "extra": "extra_change"}[c["kind"]], c["new"])
            add(sev, name, f"列 {c['column']} {kind} {c['old']} → {c['new']}")
        for ix in ch["indexes_added"]:
            add("high" if ix["unique"] else "info", name,
                f"新增{'唯一' if ix['unique'] else ''}索引 {ix['name']} ({', '.join(ix['cols'])})")
        for ix in ch["indexes_removed"]:
            add("warn", name, f"删除索引 {ix['name']} ({', '.join(ix['cols'])})")
        for ix in ch["indexes_changed"]:
            add("warn", name, f"索引 {ix['name']} 变化 {ix['old']['cols']} → {ix['new']['cols']}")
        for fk in ch["fks_added"]:
            add("warn", name, f"新增外键 {fk['name']} → {fk['ref_table']}")
        for fk in ch["fks_removed"]:
            add("warn", name, f"删除外键 {fk['name']} → {fk['ref_table']}")
        if ch["pk_change"]:
            add("high", name, f"主键变化 {ch['pk_change']['old']} → {ch['pk_change']['new']}")
        for o in ch["options_changed"]:
            add("warn", name, f"表选项 {o['key']} {o['old']} → {o['new']}")
    return f


def main():
    ap = argparse.ArgumentParser(description="两份建表 SQL 的结构对比与迁移草稿")
    ap.add_argument("old"); ap.add_argument("new")
    ap.add_argument("--dialect", choices=["auto", "mysql", "postgres"], default="auto")
    ap.add_argument("--sql", action="store_true", help="只输出迁移 SQL 草稿")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 high（破坏性或锁表）变更时退出码 1")
    a = ap.parse_args()
    for p in (a.old, a.new):
        if not os.path.isfile(p):
            sys.exit(f"文件不存在：{p}")
    to, tn = open(a.old, encoding="utf-8", errors="replace").read(), open(a.new, encoding="utf-8", errors="replace").read()
    dialect = detect_dialect(to, tn) if a.dialect == "auto" else a.dialect
    so, sn = {}, {}
    old, new = parse_sql(to, so), parse_sql(tn, sn)
    d = diff_tables(old, new)
    findings = collect_findings(d)
    sql, locks = migration(d, old, new, dialect)
    counts = {s: sum(1 for x in findings if x["severity"] == s) for s in ("high", "warn", "info")}
    if a.json:
        print(json.dumps({"dialect": dialect, "old": {"file": a.old, **so}, "new": {"file": a.new, **sn},
                          "summary": counts, "diff": d, "findings": findings, "migration": sql, "locks": locks},
                         ensure_ascii=False, indent=2, default=str))
    elif a.sql:
        print("\n".join(sql) if sql else "-- 结构一致，无需迁移")
    else:
        print(f"对比 {a.old} → {a.new}   方言 {dialect}")
        print(f"解析：旧 {so['tables']} 张表（跳过 {so['skipped']} 条语句）/ 新 {sn['tables']} 张表（跳过 {sn['skipped']} 条语句）")
        if not findings:
            print("\n  ✓ 结构一致")
        order = {"high": 0, "warn": 1, "info": 2}
        cur = None
        for x in sorted(findings, key=lambda x: (x["table"], order[x["severity"]])):
            if x["table"] != cur:
                print(f"\n== {x['table']}"); cur = x["table"]
            print(f"  [{x['severity'].upper():4}] {x['change']}")
        if locks:
            print("\n锁表与风险提示")
            for l in locks:
                print(f"  ! {l}")
        if sql:
            print(f"\n迁移 SQL 草稿（{dialect}，破坏性语句已注释，执行前必须人工复核）")
            for s in sql:
                print("  " + s.replace("\n", "\n  "))
        print(f"\n小计：high {counts['high']} / warn {counts['warn']} / info {counts['info']}")
    sys.exit(1 if (a.strict and counts["high"]) else 0)


if __name__ == "__main__":
    main()
