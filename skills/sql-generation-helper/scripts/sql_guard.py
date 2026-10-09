#!/usr/bin/env python3
"""SQL 交付前的机械检查：只读闸门 + 常见坑 + 方言差异 + （可选）字段名核对。

用法：
  python3 scripts/sql_guard.py query.sql
  python3 scripts/sql_guard.py query.sql --dialect mysql            # mysql / mysql57 / postgresql / sqlite
  python3 scripts/sql_guard.py query.sql --columns columns.csv      # 字段清单：information_schema 查询导出的 CSV/TSV
  python3 scripts/sql_guard.py - --dialect postgresql < query.sql   # 从标准输入读

它只读文本，不连数据库、不执行 SQL、不改任何文件。注释和字符串里的内容不参与判断，
所以 REPLACE() 函数、字段名 update_time、注释里的 DELETE 都不会误报成写操作。
检查通过不等于 SQL 一定正确：口径、连接关系仍要按技能里的五步和对账查询核对。

结果码：B 开头 = 写操作、DDL、配置/文件变更或可执行注释（必须过只读闸门）；W 开头 = 常见坑；D 开头 = 方言不支持；
        C 开头 = 字段名在字段清单里找不到。
退出码：0 只读（可能有 W/D/C 提醒）；1 参数有误或字段清单格式不对；2 文件读不了；
        3 含写操作或 DDL，先过只读闸门；130 手动中断（Ctrl+C）。
只用 Python 标准库。
"""

import argparse
import csv
import difflib
import io
import re
import sys
from pathlib import Path

DIALECTS = {"mysql": "mysql", "mysql8": "mysql", "mysql57": "mysql57", "postgresql": "postgresql",
            "postgres": "postgresql", "pg": "postgresql", "sqlite": "sqlite"}
DML_WRITE = {"INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT"}
DDL = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE"}
PROC = {"CALL", "EXEC", "EXECUTE", "COPY"}
MUTATING_COMMANDS = {"SET", "VACUUM"}
CLAUSE_END = {"WHERE", "GROUP", "ORDER", "LIMIT", "UNION", "HAVING", "WINDOW", "JOIN", "INTERSECT", "EXCEPT"}
NOT_ALIAS = CLAUSE_END | {"ON", "USING", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "FULL", "NATURAL",
                          "AS", "SET", "VALUES", "SELECT", "FROM", "LATERAL", "AND", "OR"}
DATE_FUNCS = r"DATE|YEAR|MONTH|DAY|DATE_FORMAT|TO_CHAR|DATE_TRUNC|SUBSTR|SUBSTRING|LEFT|CAST|CONVERT|LOWER|UPPER|TRIM"

GATE = ("只读闸门：先回风险提示，等用户明确回复「确认执行」再给语句——"
        "影响范围（同条件 SELECT COUNT(*) 报出会动多少行）、可回退（备份与回滚方式）、"
        "执行方式（DML 进事务先 ROLLBACK 演练，大表分批；MySQL 的 DDL 会隐式提交）、时机（避开高峰，DDL 先问 DBA）")

DIALECT_RULES = {
    "mysql": [
        (r"\bILIKE\b", "MySQL 没有 ILIKE：用 LOWER(col) LIKE LOWER('…')"),
        (r"::\s*[A-Za-z]", "MySQL 不支持 :: 类型转换：用 CAST(x AS 类型)"),
        (r"\bTO_CHAR\s*\(", "MySQL 没有 to_char：用 DATE_FORMAT(col, '%Y-%m')"),
        (r"\bDATE_TRUNC\s*\(", "MySQL 没有 DATE_TRUNC：按月可用 DATE_FORMAT(col, '%Y-%m-01')"),
        (r"\bFILTER\s*\(\s*WHERE\b", "MySQL 不支持聚合的 FILTER 子句：用 SUM(CASE WHEN … THEN 1 ELSE 0 END)"),
        (r"\bFULL\s+(?:OUTER\s+)?JOIN\b", "MySQL 不支持 FULL JOIN：用 LEFT JOIN … UNION … RIGHT JOIN"),
        (r"\bQUALIFY\b", "MySQL 不支持 QUALIFY：窗口结果放进子查询再过滤"),
        (r"\bSTRING_AGG\s*\(", "MySQL 没有 string_agg：用 GROUP_CONCAT"),
    ],
    "mysql57": [
        (r"\bOVER\s*\(", "MySQL 5.7 不支持窗口函数（8.0 起支持）：升级，或改写成子查询、自连接"),
        (r"^\s*WITH\b", "MySQL 5.7 不支持 WITH（8.0 起支持）：改写成子查询"),
    ],
    "postgresql": [
        (r"\bDATE_FORMAT\s*\(", "PostgreSQL 没有 DATE_FORMAT：用 to_char(col, 'YYYY-MM')"),
        (r"\bIFNULL\s*\(", "PostgreSQL 没有 IFNULL：用 COALESCE"),
        (r"\bLIMIT\s+\d+\s*,\s*\d+", "PostgreSQL 不支持 LIMIT m, n：写成 LIMIT n OFFSET m"),
        (r"\bDATE_SUB\s*\(", "PostgreSQL 没有 DATE_SUB：用 col - INTERVAL '1 day'"),
        (r"\bINTERVAL\s+\d+\s+(?:SECOND|MINUTE|HOUR|DAY|WEEK|MONTH|YEAR)\b",
         "PostgreSQL 的间隔要加引号：INTERVAL '1 day'"),
        (r"\bGROUP_CONCAT\s*\(", "PostgreSQL 没有 GROUP_CONCAT：用 string_agg(col, ',')"),
        (r"\bSTR_TO_DATE\s*\(", "PostgreSQL 没有 STR_TO_DATE：用 to_date / to_timestamp"),
    ],
    "sqlite": [
        (r"\bDATE_FORMAT\s*\(|\bTO_CHAR\s*\(", "SQLite 用 strftime('%Y-%m', col) 格式化日期"),
        (r"\bILIKE\b", "SQLite 没有 ILIKE：LIKE 默认对英文字母不区分大小写"),
        (r"\bFULL\s+(?:OUTER\s+)?JOIN\b|\bRIGHT\s+(?:OUTER\s+)?JOIN\b", "SQLite 3.39 之前不支持 RIGHT/FULL JOIN：先确认版本"),
        (r"\bINTERVAL\b", "SQLite 没有 INTERVAL：用 date(col, '-1 day')"),
    ],
}


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FriendlyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/sql_guard.py query.sql --dialect mysql）" % message,
              file=sys.stderr)
        sys.exit(1)


def read_bytes_text(path, what):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        p = Path(path)
        if not p.exists():
            raise InputError(2, "%s不存在：%s，检查路径" % (what, path))
        if p.is_dir():
            raise InputError(2, "%s 是文件夹，请给出%s文件" % (path, what))
        try:
            data = p.read_bytes()
        except OSError as exc:
            raise InputError(2, "读不了 %s（%s）" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise InputError(2, "%s编码认不出来：请另存为 UTF-8" % what)


def mask(sql, dq_is_string, mysql_comments=False):
    """注释换成空格；字符串内容换成下划线（引号保留）；带引号的标识符换成 q。长度和换行都不变。
    返回 (masked, ident, strings, backticks, executable_comments)：ident 里带引号的标识符去掉了引号，
    strings 记下字符串原值，后两项记录反引号和可执行注释的位置。"""
    out, ident, strings = list(sql), list(sql), {}
    backticks = []
    executable_comments = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        # MySQL 的 -- 后须有空白/控制字符；1--1 是两个减号，不能擦掉后续写操作。
        dash_comment = sql.startswith("--", i) and (
            not mysql_comments or i + 2 == n or sql[i + 2].isspace() or ord(sql[i + 2]) < 32)
        if dash_comment or (c == "#" and dq_is_string):     # MySQL 里 # 也是行注释
            j = sql.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = ident[k] = " "
            i = j
        elif sql.startswith("/*", i):
            if sql.startswith("/*!", i) or sql[i:i + 4].upper() == "/*M!":
                executable_comments.append(i)
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if sql[k] != "\n":
                    out[k] = ident[k] = " "
            i = j
        elif c == "'" or (c == '"' and dq_is_string):
            j = i + 1
            while j < n:
                if sql[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            strings[i] = sql[i + 1:j]
            for k in range(i + 1, min(j, n)):
                if sql[k] != "\n":
                    out[k] = ident[k] = "_"
            i = j + 1
        elif c == "`" or c == '"':
            if c == "`":
                backticks.append(i)
            j = sql.find(c, i + 1)
            j = n - 1 if j < 0 else j
            for k in range(i, j + 1):
                out[k] = "q" if sql[k] != "\n" else "\n"
            ident[i] = ident[j] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out), "".join(ident), strings, backticks, executable_comments


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def tokens_with_depth(seg):
    """[(起点, 大写词, 括号深度)]，括号本身也作为 '(' ')' 记录。"""
    toks, depth = [], 0
    for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_$]*|[()]", seg):
        t = m.group(0)
        if t == "(":
            toks.append((m.start(), "(", depth))
            depth += 1
        elif t == ")":
            depth -= 1
            toks.append((m.start(), ")", depth))
        else:
            toks.append((m.start(), t.upper(), depth))
    return toks


def check_statement(seg, off, full, ident_seg, strings, backticks, dialect, columns, findings):
    toks = tokens_with_depth(seg)
    words = [(p, t, d) for p, t, d in toks if t not in "()"]
    add = lambda code, pos, msg: findings.append((line_of(full, off + pos), code, msg))

    # ---- 写操作 / DDL
    for i, (p, t, d) in enumerate(words):
        prev = words[i - 1][1] if i else ""
        prev2 = words[i - 2][1] if i > 1 else ""
        if t in DML_WRITE:
            if t == "UPDATE" and (prev == "FOR" or (prev == "KEY" and prev2 == "NO")):
                add("W11", p, "FOR UPDATE 会给读到的行加锁，只读查询不需要")
            elif prev == "ON" or (prev == "KEY" and prev2 == "DUPLICATE"):
                continue              # ON DELETE/ON UPDATE（外键、默认值）或 ON DUPLICATE KEY UPDATE，随所在语句判
            else:
                add("B01", p, "%s 是写操作" % t)
        elif t in DDL:
            add("B02", p, "%s 是 DDL，会改表结构或权限" % t)
        elif t == "REPLACE" and not re.match(r"\s*\(", seg[p + 7:]):
            add("B01", p, "REPLACE INTO 会删除再插入，是写操作")
        elif t in PROC and i == 0:
            add("B04", p, "%s 会调用过程或读写文件，看不到里面做什么，按写操作对待" % t)
        elif t in MUTATING_COMMANDS and i == 0:
            add("B04", p, "%s 会改变配置或数据库文件，不是只读查询" % t)
        elif t == "LOAD" and i + 1 < len(words) and words[i + 1][1] == "DATA":
            add("B01", p, "LOAD DATA 会写入数据")
        elif t == "INTO" and prev not in ("INSERT", "REPLACE", "MERGE") and words and words[0][1] in ("SELECT", "WITH"):
            if not re.match(r"\s*@", seg[p + 4:]):
                add("B03", p, "SELECT … INTO 会新建表或写出文件，不是只读查询")

    # ---- 常见坑
    for m in re.finditer(r"\bSELECT\s+(?:DISTINCT\s+)?(?:\w+\.)?\*|,\s*(?:\w+\.)?\*\s*(?=,|\bFROM\b)", seg, re.I):
        add("W01", m.start(), "SELECT * 会带出不需要的列，表结构一变结果就变：只选要用的列")
    for m in re.finditer(r"\bBETWEEN\s+'(_*)'\s+AND\s+'(_*)'", seg, re.I):
        vals = [strings.get(off + m.start(k) - 1, "") for k in (1, 2)]
        if all(re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", v) for v in vals):
            add("W02", m.start(), "BETWEEN '%s' AND '%s' 会漏掉最后一天 00:00 之后的数据：改成 >= 起点 且 < 次日" % tuple(vals))
    for m in re.finditer(r"\bNOT\s+IN\s*\(\s*SELECT\b", seg, re.I):
        add("W03", m.start(), "NOT IN（子查询）里只要有一个 NULL 就一行都不返回：改用 NOT EXISTS")
    top_words = [t for _, t, d in words if d == 0]
    if "LIMIT" in top_words:
        li = top_words.index("LIMIT")
        if "ORDER" not in top_words[:li]:
            add("W04", next(p for p, t, d in words if t == "LIMIT" and d == 0),
                "LIMIT 没配 ORDER BY，每次返回哪几行不固定")
    for w in re.finditer(r"\bWHERE\b(.*?)(?=\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bHAVING\b|\bUNION\b|$)", seg, re.I | re.S):
        for m in re.finditer(r"\b(%s)\s*\(\s*([A-Za-z_][\w.]*)\s*[,)]" % DATE_FUNCS, w.group(1), re.I):
            add("W05", w.start(1) + m.start(), "WHERE 里 %s(%s) 把函数包在字段上，索引通常用不上：换算放到常量一侧"
                % (m.group(1).upper(), m.group(2)))
    for m in re.finditer(r"(?:=|<>|!=)\s*NULL\b", seg, re.I):
        add("W09", m.start(), "和 NULL 用 = 或 <> 比较永远不成立：改用 IS NULL / IS NOT NULL")

    # JOIN 缺连接条件；LEFT JOIN 后在 WHERE 里过滤右表
    for i, (p, t, d) in enumerate(toks):
        if t != "JOIN":
            continue
        before = [x[1] for x in toks[max(0, i - 2):i]]
        if "CROSS" in before or "NATURAL" in before:
            continue
        has_on, alias, j, depth = False, None, i + 1, d
        after = []
        while j < len(toks):
            pj, tj, dj = toks[j]
            if tj == ")" and dj < d:
                break
            if dj == d and tj != "(" and tj != ")":
                if tj in ("ON", "USING"):
                    has_on = True
                    break
                if tj in CLAUSE_END:
                    break
                after.append(tj)
            j += 1
        if not has_on:
            add("W06", p, "JOIN 缺 ON/USING 连接条件，结果会变成笛卡尔积")
        if "LEFT" in before and after:
            alias = after[-1] if len(after) >= 2 and after[-1] not in NOT_ALIAS else (after[0] if len(after) == 1 else None)
            if alias:
                tail = seg[p:]
                w = re.search(r"\bWHERE\b(.*?)(?=\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bHAVING\b|\bUNION\b|$)", tail, re.I | re.S)
                if w and re.search(r"\b%s\.\w+\s*(?:=|<>|!=|>=|<=|>|<|\bIN\b|\bLIKE\b|\bBETWEEN\b)" % re.escape(alias),
                                   w.group(1), re.I):
                    shown = re.search(r"\b%s\b" % re.escape(alias), seg[p:], re.I).group(0)
                    add("W07", p + w.start(), "LEFT JOIN 后在 WHERE 里过滤右表 %s 的字段，等于变回 INNER JOIN：条件放进 ON" % shown)

    for item in re.finditer(r"[^,]*?/\s*(?:NULLIF\s*\(\s*)?COUNT\s*\([^,]*", seg, re.I):
        text = item.group(0)
        if re.search(r"\b(?:COUNT|SUM)\s*\(", text[:text.rfind("/")], re.I) and not re.search(
                r"1\.0|100\.0|::\s*(?:numeric|float|decimal|real|double)|\bCAST\s*\(", text, re.I):
            if dialect in (None, "postgresql"):
                add("W08", item.start(), "整数相除在 PostgreSQL 会取整：分子乘 1.0 或转成 numeric")

    # ---- 方言
    if dialect == "postgresql":
        inside = [b for b in backticks if off <= b < off + len(seg)]
        if inside:
            add("D01", inside[0] - off, "PostgreSQL 的标识符用双引号，不用反引号")
    if dialect:
        rules = list(DIALECT_RULES.get(dialect, []))
        if dialect == "mysql57":
            rules = DIALECT_RULES["mysql"] + rules
        for pattern, msg in rules:
            m = re.search(pattern, seg, re.I | re.M)
            if m:
                add("D01", m.start(), msg)

    # ---- 字段名
    if columns:
        ctes = {m.group(1).lower() for m in re.finditer(r"(?:\bWITH\s+(?:RECURSIVE\s+)?|,\s*)(\w+)\s+AS\s*\(", seg, re.I)}
        aliases = {}
        for m in re.finditer(r"\b(?:FROM|JOIN)\s+([\w.]+)(?:\s+(?:AS\s+)?(\w+))?", ident_seg, re.I):
            table = m.group(1).split(".")[-1].lower()
            alias = m.group(2)
            if table in ctes or table in ("select", "lateral"):
                continue
            if table not in columns:
                add("C02", m.start(), "表 %s 不在字段清单里，跳过它的字段核对【待确认】" % table)
                continue
            aliases[table] = table
            if alias and alias.upper() not in NOT_ALIAS:
                aliases[alias.lower()] = table
        for m in re.finditer(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", ident_seg):
            a, col = m.group(1).lower(), m.group(2).lower()
            if a in aliases and col not in columns[aliases[a]]:
                near = difflib.get_close_matches(col, sorted(columns[aliases[a]]), n=2, cutoff=0.6)
                add("C01", m.start(), "%s.%s 在字段清单的 %s 表里没有%s【待确认】" % (
                    m.group(1), m.group(2), aliases[a], "；相近的有 " + "、".join(near) if near else ""))


def load_columns(path):
    text = read_bytes_text(path, "字段清单")
    first = text.splitlines()[0] if text.strip() else ""
    delim = "\t" if "\t" in first else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    fields = {(f or "").strip().lower(): f for f in (reader.fieldnames or [])}
    if "table_name" not in fields or "column_name" not in fields:
        raise InputError(1, "字段清单缺 table_name 或 column_name 列：用技能里那条 information_schema 查询导出，保留表头")
    cols = {}
    for row in reader:
        t = (row.get(fields["table_name"]) or "").strip().lower()
        c = (row.get(fields["column_name"]) or "").strip().lower()
        if t and c:
            cols.setdefault(t, set()).add(c)
    if not cols:
        raise InputError(1, "字段清单是空的：确认查询有结果、导出时带上了数据行")
    return cols


def run(sql, dialect, columns, name):
    if not sql.strip():
        raise InputError(1, "SQL 是空的：把要检查的查询贴进来或存进文件")
    masked, ident, strings, backticks, executable_comments = mask(
        sql, dq_is_string=dialect in ("mysql", "mysql57"),
        mysql_comments=dialect in (None, "mysql", "mysql57"))
    findings = [(line_of(sql, pos), "B05", "MySQL/MariaDB 可执行注释不能当普通注释忽略："
                 "先展开成普通 SQL 再核对，不按只读查询交付") for pos in executable_comments]
    start = 0
    for m in list(re.finditer(";", masked)) + [None]:
        end = m.start() if m else len(masked)
        seg = masked[start:end]
        if seg.strip():
            check_statement(seg, start, masked, ident[start:end], strings, backticks, dialect, columns, findings)
        start = end + 1
    findings = sorted(set(findings))

    print("检查 %s（方言：%s）" % (name, dialect or "未指定"))
    if not dialect:
        print("  [待确认] 没指定方言，跳过方言检查；加 --dialect mysql / mysql57 / postgresql / sqlite")
    blockers = [f for f in findings if f[1].startswith("B")]
    for line, code, msg in findings:
        print("  [%s] 第 %d 行：%s" % (code, line, msg))
    if blockers:
        print("结论：触发只读闸门（%d 处），不能当只读查询交付" % len(blockers))
        print(GATE)
        return 3
    if findings:
        print("结论：只读；有 %d 条提醒，逐条确认后再交付" % len(findings))
    else:
        print("结论：只读，没发现常见的坑（不代表口径正确，仍要跑对账查询）")
    return 0


def main(argv=None):
    p = FriendlyParser(description="SQL 交付前检查：只读闸门、常见坑、方言差异、字段名核对。",
                       epilog="退出码：0 只读；1 参数或字段清单有误；2 文件读不了；3 含写操作或 DDL；130 手动中断。")
    p.add_argument("file", help="SQL 文件；写 - 表示从标准输入读")
    p.add_argument("--dialect", help="mysql（即 8.0）/ mysql57 / postgresql / sqlite")
    p.add_argument("--columns", help="字段清单 CSV/TSV，至少含 table_name、column_name 两列")
    args = p.parse_args(argv)
    try:
        dialect = None
        if args.dialect:
            dialect = DIALECTS.get(args.dialect.strip().lower())
            if not dialect:
                raise InputError(1, "不认识的方言「%s」：可选 mysql、mysql57、postgresql、sqlite；"
                                    "其他数据库先不加 --dialect，方言差异人工核对" % args.dialect)
        columns = load_columns(args.columns) if args.columns else None
        sql = read_bytes_text(args.file, "SQL 文件")
        return run(sql, dialect, columns, "标准输入" if args.file == "-" else Path(args.file).name)
    except InputError as exc:
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有改动任何文件", file=sys.stderr)
        sys.exit(130)
