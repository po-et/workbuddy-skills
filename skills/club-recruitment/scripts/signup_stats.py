#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社团招新报名表：统计与去重（只用 Python 标准库）。

用法：
  python3 scripts/signup_stats.py 报名表.csv
  python3 scripts/signup_stats.py 报名表.csv --out 去重后.csv
  python3 scripts/signup_stats.py 报名表.csv --col 意向部门=第一志愿 --col 意向部门=第二志愿 --json
  cat 报名表.csv | python3 scripts/signup_stats.py -

做什么：
  1. 识别列：姓名、学号、联系方式、年级、专业、意向部门、提交时间；认不出的用 --col 字段=列名 指定。
     联系方式、意向部门允许多列（如手机号 + 微信号、第一志愿 + 第二志愿）。
  2. 去重：学号相同或联系方式相同即视为同一人（可传递合并），保留最后提交的一条；
     姓名+年级+专业相同、但学号和联系方式都不同的，只列为「疑似重复」，不自动合并。
     「无」「同上」「同手机号」这类占位答案不参与判重。
  3. 统计：年级、专业、意向部门（多选拆开计数）；有两列及以上志愿时另计第一志愿；
     列出缺关键字段的行。
  4. 只读：默认只打印结果，联系方式、学号脱敏；给 --out 才写去重后的新 CSV
     （UTF-8 带 BOM，先写临时文件再替换；不覆盖输入文件；目标已存在需加 --force）。

退出码：0 成功；1 参数错误；2 文件读写失败；3 表格内容无法识别；130 用户中断。
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter, OrderedDict
from datetime import datetime, timezone

EXIT_OK = 0
EXIT_ARGS = 1
EXIT_IO = 2
EXIT_DATA = 3
EXIT_INTERRUPT = 130

MULTI_FIELDS = ("联系方式", "意向部门")

# 字段 -> 表头关键词（按优先级；中文按包含匹配，英文按整词匹配）
FIELD_KEYWORDS = OrderedDict([
    ("学号", ("学号", "学生证号", "student id", "student no")),
    ("联系方式", ("手机", "电话", "联系方式", "微信", "qq", "phone", "mobile", "tel", "wechat", "contact")),
    ("姓名", ("姓名", "名字", "name")),
    ("年级", ("年级", "入学年份", "grade", "year")),
    ("专业", ("专业", "学院", "院系", "major", "college")),
    ("意向部门", ("意向部门", "部门", "志愿", "意向", "department", "dept")),
    ("提交时间", ("提交时间", "提交答卷时间", "答卷时间", "填写时间", "提交日期", "timestamp", "submitted")),
])

# 表头里出现这些词就不当作该字段（例如「为什么想加入该部门」不是意向部门）
FIELD_EXCLUDE = {
    "学号": (),
    "联系方式": ("紧急", "家长", "父母", "emergency"),
    "姓名": ("紧急", "家长", "父母", "推荐人", "昵称", "emergency"),
    "年级": (),
    "专业": ("特长", "技能"),
    "意向部门": ("为什么", "原因", "理由", "经历", "志愿者", "介绍", "期待", "想法", "了解"),
    "提交时间": (),
}

FIELD_ALIASES = {
    "姓名": "姓名", "名字": "姓名", "name": "姓名",
    "学号": "学号", "id": "学号", "studentid": "学号",
    "联系方式": "联系方式", "手机": "联系方式", "手机号": "联系方式", "电话": "联系方式",
    "微信": "联系方式", "phone": "联系方式", "contact": "联系方式",
    "年级": "年级", "grade": "年级",
    "专业": "专业", "学院": "专业", "major": "专业",
    "意向部门": "意向部门", "部门": "意向部门", "志愿": "意向部门", "dept": "意向部门",
    "department": "意向部门",
    "提交时间": "提交时间", "时间": "提交时间", "time": "提交时间",
}

# 这些答案等于没填，不能拿来判重（否则所有填「无」的人会被合并成一个人）
PLACEHOLDERS = {
    "无", "暂无", "没有", "空", "-", "--", "—", "——", "/", "\\", "0", "同上", "同手机",
    "同手机号", "手机同号", "同电话", "同电话号码", "n/a", "na", "none", "null", "nil",
}

DEFAULT_SEPS = "、,，;；|┋\n"
TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
    "%Y年%m月%d日 %H:%M:%S", "%Y年%m月%d日 %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日",
)
OPTION_PREFIX_RE = re.compile(r"^[A-Za-z][.、)]\s*")
PHONEISH_RE = re.compile(r"[\d\s\-+()]+")


class UserError(Exception):
    """带退出码的友好错误。"""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message


class FriendlyParser(argparse.ArgumentParser):
    """argparse 默认参数错误退出码是 2，这里统一成 1，并给中文提示。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用 --help 查看用法。\n" % message)
        sys.exit(EXIT_ARGS)


# ------------------------------------------------------------------ 规整

def norm(value):
    """统一全角半角、去掉首尾空白和 BOM。"""
    return unicodedata.normalize("NFKC", value or "").replace("\ufeff", "").strip()


def meaningful(value):
    """规整后的值；占位答案（无、同上……）当作空。"""
    v = norm(value)
    return "" if v.lower() in PLACEHOLDERS else v


# ------------------------------------------------------------------ 读取

def read_bytes(path):
    if path == "-":
        return sys.stdin.buffer.read(), "标准输入"
    if os.path.isdir(path):
        raise UserError(EXIT_IO, "读不了文件：%s 是一个文件夹，请传入 CSV 文件路径。" % path)
    try:
        with open(path, "rb") as fh:
            return fh.read(), path
    except FileNotFoundError:
        raise UserError(EXIT_IO, "读不了文件：找不到 %s，请检查路径和文件名。" % path)
    except PermissionError:
        raise UserError(EXIT_IO, "读不了文件：没有权限读取 %s。" % path)
    except OSError as exc:
        raise UserError(EXIT_IO, "读不了文件：%s（%s）" % (path, exc))


def decode(raw):
    if raw.startswith(b"PK\x03\x04"):
        raise UserError(EXIT_DATA, "表格内容无法识别：这是 Excel 工作簿（.xlsx），"
                                   "请用 Excel 或 WPS「另存为」CSV 后再运行。")
    if raw.startswith(b"\xd0\xcf\x11\xe0"):
        raise UserError(EXIT_DATA, "表格内容无法识别：这是旧版 Excel 文件（.xls），"
                                   "请用 Excel 或 WPS「另存为」CSV 后再运行。")
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise UserError(EXIT_IO, "读不了文件：编码既不是 UTF-8 也不是 GBK，"
                             "请用 Excel 或 WPS 另存为「CSV UTF-8」后再运行。")


def pick_delimiter(text):
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    counts = {d: first.count(d) for d in (",", "\t", ";")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def parse_rows(text):
    """返回 (规整后的表头, 原始表头, [(Excel 行号, 原始单元格)], 跳过的空行数)。"""
    delim = pick_delimiter(text)
    try:
        records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
    except csv.Error as exc:
        raise UserError(EXIT_DATA, "表格内容无法识别：CSV 格式有误（%s）。" % exc)
    header_idx = next((i for i, r in enumerate(records) if any(c.strip() for c in r)), None)
    if header_idx is None:
        raise UserError(EXIT_DATA, "表格内容无法识别：文件是空的。")
    header_raw = records[header_idx]
    header = [norm(c) or "（第%d列）" % (i + 1) for i, c in enumerate(header_raw)]
    rows, blank = [], 0
    for i in range(header_idx + 1, len(records)):
        cells = records[i]
        if not any(c.strip() for c in cells):
            blank += 1
            continue
        rows.append((i + 1, cells))
    if not rows:
        raise UserError(EXIT_DATA, "表格内容无法识别：只有表头，没有报名数据。")
    return header, header_raw, rows, blank


# ------------------------------------------------------------------ 列识别

def keyword_hit(header, keyword):
    h = header.lower()
    if re.search(r"[a-z]", keyword):
        return re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(keyword), h) is not None
    return keyword in h


def parse_col_overrides(specs, header):
    overrides = OrderedDict()
    for spec in specs or []:
        if "=" not in spec:
            raise UserError(EXIT_ARGS, "参数错误：--col 的写法是「字段=列名」，例如 --col 意向部门=第一志愿；"
                                       "收到的是 %r。" % spec)
        field_raw, col_raw = spec.split("=", 1)
        field = FIELD_ALIASES.get(norm(field_raw).lower())
        if not field:
            raise UserError(EXIT_ARGS, "参数错误：不认识字段 %r，可用：姓名、学号、联系方式、年级、专业、"
                                       "意向部门、提交时间。" % field_raw)
        col = norm(col_raw)
        matches = [i for i, h in enumerate(header) if h == col]
        if not matches:
            raise UserError(EXIT_ARGS, "参数错误：表头里没有列 %r。现有的列：%s" % (col_raw, "｜".join(header)))
        overrides.setdefault(field, [])
        if field in MULTI_FIELDS:
            overrides[field].extend(m for m in matches if m not in overrides[field])
        else:
            overrides[field] = matches[:1]
    return overrides


def detect_columns(header, overrides):
    mapping = OrderedDict((f, []) for f in FIELD_KEYWORDS)
    used = set()
    for field, idxs in overrides.items():
        mapping[field] = list(idxs)
        used.update(idxs)
    for field, keywords in FIELD_KEYWORDS.items():
        if mapping[field]:
            continue
        found = []
        for kw in keywords:
            for i, h in enumerate(header):
                if i in used or i in found:
                    continue
                if any(x in h.lower() for x in FIELD_EXCLUDE[field]):
                    continue
                if keyword_hit(h, kw):
                    found.append(i)
                    if field not in MULTI_FIELDS:
                        break
            if found and field not in MULTI_FIELDS:
                break
        mapping[field] = sorted(found)
        used.update(found)
    return mapping


# ------------------------------------------------------------------ 取值

def cell(cells, idx):
    return meaningful(cells[idx]) if idx < len(cells) else ""


def first_value(cells, idxs):
    for i in idxs:
        v = cell(cells, i)
        if v:
            return v
    return ""


def phone_digits(v):
    if not PHONEISH_RE.fullmatch(v):
        return None
    digits = re.sub(r"\D", "", v)
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    return digits


def contact_key(value):
    v = meaningful(value)
    if not v:
        return None
    digits = phone_digits(v)
    if digits is not None and len(digits) >= 5:
        return "tel:" + digits
    return "id:" + re.sub(r"\s+", "", v).lower()


def mask_contact(value):
    v = meaningful(value)
    if not v:
        return "（无）"
    digits = phone_digits(v)
    if digits is not None:
        return digits[:3] + "****" + digits[-4:] if len(digits) >= 7 else "****" + digits[-2:]
    return "***" if len(v) <= 3 else v[:2] + "***" + v[-1:]


def mask_id(value):
    v = norm(value)
    return "****" + v[-4:] if len(v) > 4 else ("****" if v else "（无）")


def split_depts(cells, idxs, seps):
    out = []
    pattern = "[" + re.escape(seps) + "]"
    for i in idxs:
        for part in re.split(pattern, cell(cells, i)):
            p = meaningful(OPTION_PREFIX_RE.sub("", part.strip()))
            if p and p not in out:
                out.append(p)
    return out


def parse_time(value):
    v = norm(value)
    if not v:
        return None
    t = None
    try:
        t = datetime.fromisoformat(v)
    except ValueError:
        for fmt in TIME_FORMATS:
            try:
                t = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
    if t is not None and t.tzinfo is not None:
        t = t.astimezone(timezone.utc).replace(tzinfo=None)
    return t


# ------------------------------------------------------------------ 核心

def analyse(header, rows, mapping, seps):
    notes = []
    id_cols = mapping["学号"]
    contact_cols = mapping["联系方式"]
    dept_cols = mapping["意向部门"]
    if not id_cols and not contact_cols:
        raise UserError(EXIT_DATA, "表格内容无法识别：没找到学号或联系方式列，无法判断重复报名。"
                                   "请用 --col 联系方式=列名 或 --col 学号=列名 指定。现有的列：%s"
                                   % "｜".join(header))

    people = []
    for rowno, cells in rows:
        sid = first_value(cells, id_cols)
        contacts = [cell(cells, i) for i in contact_cols if cell(cells, i)]
        keys = []
        if sid:
            keys.append("sid:" + re.sub(r"\s+", "", sid).upper())
        for c in contacts:
            k = contact_key(c)
            if k and k not in keys:
                keys.append(k)
        people.append({
            "row": rowno,
            "cells": cells,
            "name": first_value(cells, mapping["姓名"]),
            "sid": sid,
            "contact": contacts[0] if contacts else "",
            "grade": first_value(cells, mapping["年级"]),
            "major": first_value(cells, mapping["专业"]),
            "depts": split_depts(cells, dept_cols, seps),
            "first_choice": (split_depts(cells, dept_cols[:1], seps) or [""])[0],
            "time_raw": first_value(cells, mapping["提交时间"]),
            "keys": keys,
        })

    # 谁更晚提交：提交时间全部能识别才按时间，否则按行顺序
    order_by = "行顺序"
    if mapping["提交时间"]:
        parsed = [parse_time(p["time_raw"]) for p in people]
        if all(t is not None for t in parsed):
            order_by = "提交时间"
            for p, t in zip(people, parsed):
                p["time"] = t
        else:
            bad = [str(p["row"]) for p, t in zip(people, parsed) if t is None][:5]
            notes.append("提交时间有空白或无法识别（如第 %s 行），改按行顺序判断谁更晚提交。" % "、".join(bad))
    else:
        notes.append("没有识别到提交时间列，按行顺序判断：越靠下视为越晚提交。")

    def order_key(i):
        p = people[i]
        return (p["time"], p["row"]) if order_by == "提交时间" else (p["row"],)

    # 并查集：共享任一学号或联系方式即同一人
    parent = list(range(len(people)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, p in enumerate(people):
        for k in p["keys"]:
            if k in owner:
                ra, rb = find(i), find(owner[k])
                if ra != rb:
                    parent[ra] = rb
            else:
                owner[k] = i

    groups = OrderedDict()
    for i in range(len(people)):
        groups.setdefault(find(i), []).append(i)

    kept_idx, dup_groups = [], []
    for members in groups.values():
        latest = max(members, key=order_key)
        kept_idx.append(latest)
        if len(members) > 1:
            shared = set()
            for a in members:
                for b in members:
                    if a < b:
                        shared.update(k.split(":", 1)[0] for k in set(people[a]["keys"]) & set(people[b]["keys"]))
            labels = []
            if "sid" in shared:
                labels.append("学号相同")
            if shared & {"tel", "id"}:
                labels.append("联系方式相同")
            dup_groups.append({
                "rows": sorted(people[m]["row"] for m in members),
                "kept_row": people[latest]["row"],
                "reason": "、".join(labels) or "经其他记录间接关联",
                "name": people[latest]["name"] or "（无姓名）",
                "contact": mask_contact(people[latest]["contact"]) if contact_cols else "",
                "student_id": mask_id(people[latest]["sid"]) if id_cols else "",
            })
    kept_idx.sort(key=lambda i: people[i]["row"])
    kept = [people[i] for i in kept_idx]

    # 疑似重复：姓名+年级+专业相同，但没有共享学号或联系方式
    suspected = []
    if mapping["姓名"]:
        bucket = OrderedDict()
        for p in kept:
            nm = re.sub(r"\s+", "", p["name"])
            if nm:
                bucket.setdefault((nm, p["grade"], p["major"]), []).append(p)
        for (nm, _g, _m), ps in bucket.items():
            if len(ps) > 1:
                suspected.append({"rows": [p["row"] for p in ps], "name": nm})

    missing = []
    for p in kept:
        lack = []
        if mapping["姓名"] and not p["name"]:
            lack.append("姓名")
        if contact_cols and not p["contact"]:
            lack.append("联系方式")
        if dept_cols and not p["depts"]:
            lack.append("意向部门")
        if lack:
            missing.append({"row": p["row"], "name": p["name"] or "（无姓名）", "missing": lack})

    counts = OrderedDict()
    if mapping["年级"]:
        counts["年级"] = Counter(p["grade"] or "（未填）" for p in kept)
    else:
        notes.append("没找到年级列，跳过年级统计（可用 --col 年级=列名 指定）。")
    if mapping["专业"]:
        counts["专业"] = Counter(p["major"] or "（未填）" for p in kept)
    else:
        notes.append("没找到专业或学院列，跳过专业统计（可用 --col 专业=列名 指定）。")
    if dept_cols:
        counts["意向部门（多选拆开计，人次）"] = Counter(d for p in kept for d in p["depts"])
        if len(dept_cols) >= 2:
            counts["第一志愿（人）"] = Counter(p["first_choice"] or "（未填）" for p in kept)
        else:
            notes.append("意向部门只有一列：多选题的选项顺序不代表志愿先后，所以不单独统计第一志愿。")
    else:
        notes.append("没找到意向部门列，跳过部门统计（可用 --col 意向部门=列名 指定）。")

    return {
        "people": kept,
        "duplicates": dup_groups,
        "suspected": suspected,
        "missing": missing,
        "counts": counts,
        "order_by": order_by,
        "notes": notes,
    }


def sorted_counts(counter, top):
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return items[:top] if top and top > 0 else items


# ------------------------------------------------------------------ 输出

def render_text(src, enc, total, blank, header, mapping, result, top):
    out = ["读取：%s（编码 %s，%d 行数据%s）"
           % (src, enc, total, "，跳过空行 %d 行" % blank if blank else "")]
    cols = ["%s=%s" % (f, "+".join(header[i] for i in idxs) if idxs else "（未找到）")
            for f, idxs in mapping.items()]
    out.append("识别到的列：" + "｜".join(cols))
    merged = total - len(result["people"])
    out.append("去重：%d 行 → %d 人（合并 %d 条重复；按%s保留最后一次提交）"
               % (total, len(result["people"]), merged, result["order_by"]))
    for g in result["duplicates"]:
        extra = [x for x in (("联系方式 " + g["contact"]) if g["contact"] else "",
                             ("学号 " + g["student_id"]) if g["student_id"] else "") if x]
        out.append("  - 第 %s 行：%s → 保留第 %d 行（%s）"
                   % ("、".join(str(r) for r in g["rows"]), g["reason"], g["kept_row"],
                      "，".join([g["name"]] + extra)))
    if result["suspected"]:
        out.append("疑似重复（姓名+年级+专业相同，但学号和联系方式都不同；未合并，请人工确认）：")
        for s in result["suspected"]:
            out.append("  - 第 %s 行：%s" % ("、".join(str(r) for r in s["rows"]), s["name"]))
    if result["missing"]:
        out.append("缺关键字段（请补问）：")
        for m in result["missing"]:
            out.append("  - 第 %d 行：%s 缺%s" % (m["row"], m["name"], "、".join(m["missing"])))
    for title, counter in result["counts"].items():
        items = sorted_counts(counter, top)
        out.append("按%s：" % title)
        out.append("  " + " | ".join("%s %d" % kv for kv in items))
        if top and len(counter) > top:
            out.append("  （另有 %d 项未显示，去掉 --top 可看全部）" % (len(counter) - top))
    for n in result["notes"]:
        out.append("提示：" + n)
    out.append("提醒：输出里有姓名，别整段转发到大群。")
    return "\n".join(out)


def render_json(src, enc, total, blank, header, mapping, result):
    data = OrderedDict()
    data["file"] = src
    data["encoding"] = enc
    data["rows"] = total
    data["blank_rows_skipped"] = blank
    data["people"] = len(result["people"])
    data["merged_duplicates"] = total - len(result["people"])
    data["order_by"] = result["order_by"]
    data["columns"] = OrderedDict((f, [header[i] for i in idxs]) for f, idxs in mapping.items())
    data["duplicate_groups"] = result["duplicates"]
    data["suspected_duplicates"] = result["suspected"]
    data["missing_fields"] = result["missing"]
    data["counts"] = OrderedDict((k, OrderedDict(sorted_counts(v, 0))) for k, v in result["counts"].items())
    data["notes"] = result["notes"]
    return json.dumps(data, ensure_ascii=False, indent=2)


def check_output_target(out_path, src_path, force):
    """在读数据之前就检查 --out，避免统计打印完才报错。"""
    target = os.path.abspath(out_path)
    if src_path != "-" and os.path.exists(src_path) and os.path.exists(target) \
            and os.path.samefile(src_path, target):
        raise UserError(EXIT_ARGS, "参数错误：--out 不能指向输入文件本身，请换一个文件名。")
    if os.path.isdir(target):
        raise UserError(EXIT_ARGS, "参数错误：--out 指向的是文件夹，请写到具体的 .csv 文件。")
    if os.path.exists(target) and not force:
        raise UserError(EXIT_ARGS, "参数错误：%s 已存在。确认要覆盖请加 --force，或换一个文件名。" % out_path)
    if not os.path.isdir(os.path.dirname(target)):
        raise UserError(EXIT_IO, "写不了文件：文件夹 %s 不存在。" % os.path.dirname(target))
    return target


def write_output(target, header_raw, people):
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".signup_", suffix=".tmp", dir=os.path.dirname(target))
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header_raw)
            for p in people:
                writer.writerow(p["cells"])
        os.replace(tmp_path, target)
        tmp_path = None
    except OSError as exc:
        raise UserError(EXIT_IO, "写不了文件：%s（%s）" % (target, exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def build_parser():
    p = FriendlyParser(
        prog="signup_stats.py",
        description="社团招新报名表统计与去重：按年级、专业、意向部门计数，合并重复报名。默认只读。",
        epilog="退出码：0 成功；1 参数错误；2 文件读写失败；3 表格内容无法识别；130 用户中断。",
    )
    p.add_argument("csv", help="报名表导出的 CSV 文件路径；传 - 表示从标准输入读取")
    p.add_argument("--col", action="append", metavar="字段=列名",
                   help="手动指定列，可重复；意向部门、联系方式可指定多列（按志愿顺序写）")
    p.add_argument("--sep", default=DEFAULT_SEPS, help="多选答案的分隔符（默认：、,，;；|┋ 和换行）")
    p.add_argument("--out", help="把去重后的结果写成新的 CSV（不覆盖输入文件）")
    p.add_argument("--force", action="store_true", help="--out 的目标已存在时允许覆盖")
    p.add_argument("--json", action="store_true", help="输出 JSON，便于其他程序读取")
    p.add_argument("--top", type=int, default=0, help="每项统计只显示前 N 个（默认全部）")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.top < 0:
        raise UserError(EXIT_ARGS, "参数错误：--top 不能是负数。")
    seps = unicodedata.normalize("NFKC", args.sep)
    if not seps:
        raise UserError(EXIT_ARGS, "参数错误：--sep 不能为空。")
    target = check_output_target(args.out, args.csv, args.force) if args.out else None

    raw, src = read_bytes(args.csv)
    text, enc = decode(raw)
    header, header_raw, rows, blank = parse_rows(text)
    mapping = detect_columns(header, parse_col_overrides(args.col, header))
    result = analyse(header, rows, mapping, seps)

    if args.json:
        print(render_json(src, enc, len(rows), blank, header, mapping, result))
    else:
        print(render_text(src, enc, len(rows), blank, header, mapping, result, args.top))
    if target:
        write_output(target, header_raw, result["people"])
        msg = "已写入去重结果：%s（%d 人，UTF-8 带 BOM，可直接用 Excel 打开）" % (args.out, len(result["people"]))
        print(msg, file=sys.stderr if args.json else sys.stdout)
    return EXIT_OK


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(errors="replace")
            sys.stderr.reconfigure(errors="replace")
        sys.exit(main())
    except UserError as err:
        sys.stderr.write(err.message + "\n")
        sys.exit(err.code)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断，输入文件没有被改动。\n")
        sys.exit(EXIT_INTERRUPT)
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        sys.exit(EXIT_OK)
