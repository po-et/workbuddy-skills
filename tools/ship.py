#!/usr/bin/env python3
"""技能发布收口：核对 → doctor → 生成 SkillHub 副本 → dry-run →（加 --publish 才）发布 → 记录。

用法：
  python3 tools/ship.py new <技能目录名...> [--publish] [--tag 批次名]
  python3 tools/ship.py upgrade <技能目录名...> [--publish] [--changelog "…"]

new      新技能：display_name 非空；版本是 SemVer；本命名空间下还没有这个 slug。
         发布后写名次基线 docs/metrics/rename-baseline-<tag>-<日期>.json（query = display_name），
         上线后用 `python3 tools/readout_rename.py <基线>` 读「是否已上线 + 搜索名次」。
upgrade  已上线技能升版本：与 git HEAD 比，name、display_name、description 第一句都不变，版本号严格变大，
         且大于线上 latestVersion。
共同门禁：skillkit doctor --min 70；SKILL.md 的相对链接都存在；无无扩展名文件和 __pycache__；scripts/*.py 能编译。
发布：串行、每次间隔 75 秒；「发布频率过高」按 10 分钟退避，最多重试 6 次（滚动 24 小时约 100 次的配额，
      见 docs/platform-notes.md）。发布成功只代表进了安全扫描队列，上线以 latestVersion 为准。
日志：dist/ship-logs/ship-<日期>.log，格式兼容 tools/record_skillids.py。
凭据：沿用 skillhub CLI 已登录的凭据；本脚本不读取、不打印任何 token。
退出码：0 全部通过（或全部发布成功）；1 有技能没过门禁或发布失败；2 参数/环境错误；130 手动中断。
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import skillhub_prep as prep  # noqa: E402

API = "https://api.skillhub.cn"
NAMESPACE = "indiv-captain"
HDR = {"User-Agent": "skillhub-cli/0.1", "Accept": "application/json"}
CLI = str(Path.home() / ".local/bin/skillhub")
GAP_SECONDS = 75
RATE_WAIT = 600
RATE_TRIES = 6


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def api(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers=HDR)
            return json.load(urllib.request.urlopen(req, timeout=25))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        time.sleep(3 * (i + 1))


def vtuple(v):
    return tuple(int(x) for x in v.split(".")) if re.fullmatch(r"\d+\.\d+\.\d+", v or "") else None


def first_sentence(desc):
    return re.split(r"[。.!！?？]", desc, maxsplit=1)[0].strip()


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def head_text(rel):
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def local_links_ok(src):
    """SKILL.md 与 references/examples 里的相对链接必须指向存在的文件。"""
    bad = []
    for md in [src / "SKILL.md", *sorted(src.glob("references/*.md")), *sorted(src.glob("examples/*.md"))]:
        for target in re.findall(r"\]\(([^)\s#]+)(?:#[^)]*)?\)", md.read_text("utf-8")):
            if re.match(r"^[a-z]+://|^mailto:", target):
                continue
            if not (md.parent / target).exists():
                bad.append(f"{md.relative_to(src)} → {target}")
    return bad


def gate(name, mode):
    """返回 (slug, meta, 问题列表)。"""
    src = prep.source_dir(name)
    rel = str((src / "SKILL.md").relative_to(ROOT))
    fm = frontmatter((src / "SKILL.md").read_text("utf-8"))
    meta = {k: prep.get(fm, k) for k in ("name", "display_name", "version", "description")}
    slug = prep.SLUGS.get(name, name)
    errs = []
    if not meta["display_name"]:
        errs.append("缺 display_name")
    if not vtuple(meta["version"]):
        errs.append(f"version 不是 SemVer：{meta['version']!r}")
    online = api(f"/api/v1/skills/{urllib.parse.quote(slug)}?namespace={NAMESPACE}")
    online_v = ((online or {}).get("latestVersion") or {}).get("version") or ""
    if mode == "new":
        if online:
            errs.append(f"命名空间下已有 {slug}（线上 {online_v or '未上线版本'}），应走 upgrade")
    else:
        old = head_text(rel)
        if old is None:
            errs.append("git HEAD 里没有这个 SKILL.md，不是升级")
        else:
            ofm = frontmatter(old)
            for k in ("name", "display_name"):
                if prep.get(ofm, k) != meta[k]:
                    errs.append(f"{k} 被改了：{prep.get(ofm, k)!r} → {meta[k]!r}")
            if first_sentence(prep.get(ofm, "description")) != first_sentence(meta["description"]):
                errs.append("description 第一句被改了")
            ov = vtuple(prep.get(ofm, "version"))
            if ov and vtuple(meta["version"]) and vtuple(meta["version"]) <= ov:
                errs.append(f"版本没有变大：{prep.get(ofm, 'version')} → {meta['version']}")
        if not online:
            errs.append(f"线上查不到 {slug}，应走 new")
        elif vtuple(online_v) and vtuple(meta["version"]) and vtuple(meta["version"]) <= vtuple(online_v):
            errs.append(f"版本不大于线上 latestVersion {online_v}")
    d = subprocess.run([sys.executable, "-m", "skillkit", "doctor", str(src), "--min", "70"], cwd=ROOT, capture_output=True, text=True)
    score = re.search(r"\]\s+(\d+) 分", d.stdout)
    meta["doctor"] = score.group(1) if score else "?"
    if d.returncode != 0:
        errs.append("doctor 未通过：" + (d.stdout.strip().splitlines() or ["(无输出)"])[-1])
    errs += [f"坏链接 {b}" for b in local_links_ok(src)]
    for f in src.rglob("*"):
        if f.name == "__pycache__" or (f.is_file() and not f.suffix and f.name not in ("LICENSE", "NOTICE")):
            errs.append(f"不允许的文件：{f.relative_to(src)}")
    for py in sorted(src.glob("scripts/*.py")):
        try:
            compile(py.read_text("utf-8"), str(py), "exec")
        except SyntaxError as e:
            errs.append(f"脚本编译失败 {py.name}：第 {e.lineno} 行 {e.msg}")
    meta["online_version"] = online_v
    return slug, meta, errs


def run_cli(args):
    r = subprocess.run([CLI, "--skip-self-upgrade", *args], cwd=ROOT, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def publish(pkg, changelog, logf, slug):
    for i in range(RATE_TRIES + 1):
        args = ["publish", str(pkg)] + (["--changelog", changelog] if changelog else [])
        code, out = run_cli(args)
        with open(logf, "a", encoding="utf-8") as fh:
            fh.write(f"--- {slug} {datetime.datetime.now():%H:%M:%S} ---\n{out}\n")
        if "频率过高" in out and i < RATE_TRIES:
            log(f"{slug}：发布频率过高，{RATE_WAIT // 60} 分钟后重试（{i + 1}/{RATE_TRIES}）")
            time.sleep(RATE_WAIT)
            continue
        sid = re.search(r"skillId=(\d+)", out)
        return (code == 0 and bool(sid)), (sid.group(1) if sid else ""), out.splitlines()[-1] if out else ""
    return False, "", "重试用尽"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["new", "upgrade"])
    ap.add_argument("names", nargs="+", help="skills/ 下的目录名")
    ap.add_argument("--publish", action="store_true", help="真的发布（默认只做门禁 + dry-run）")
    ap.add_argument("--changelog", default="", help="upgrade 时的更新说明")
    ap.add_argument("--tag", default="", help="new 的批次名，用于基线文件名")
    a = ap.parse_args()
    if not Path(CLI).exists():
        print(f"找不到 skillhub CLI：{CLI}", file=sys.stderr)
        return 2
    out_dir = ROOT / "dist/skillhub"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = ROOT / "dist/ship-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logf = log_dir / f"ship-{datetime.date.today()}.log"

    ready, failed = [], []
    for n in a.names:
        try:
            slug, meta, errs = gate(n, a.mode)
        except SystemExit as e:
            failed.append((n, str(e)))
            log(f"✗ {n}：{e}")
            continue
        if not errs:
            pkg = prep.prep(n, out_dir)
            errs += prep.check(pkg)
            if not errs:
                code, out = run_cli(["publish", str(pkg), "--dry-run"])
                if code != 0 or "Dry-run passed" not in out:
                    errs.append("dry-run 失败：" + (out.splitlines() or [""])[-1])
        if errs:
            failed.append((n, "；".join(errs)))
            log(f"✗ {n}（{meta.get('display_name')}）：" + "；".join(errs))
        else:
            ready.append((n, slug, meta, pkg))
            log(f"✓ {n} → {slug}「{meta['display_name']}」v{meta['version']}（线上 {meta['online_version'] or '无'}，doctor {meta['doctor']}）")
    log(f"门禁：通过 {len(ready)}，未通过 {len(failed)}")
    if not a.publish:
        return 1 if failed else 0

    published = []
    for i, (n, slug, meta, pkg) in enumerate(ready):
        if i:
            time.sleep(GAP_SECONDS)
        ok, sid, last = publish(pkg, a.changelog, logf, slug)
        log(("↑ " if ok else "✗ ") + f"{slug} v{meta['version']} {('skillId=' + sid) if sid else last}")
        if ok:
            published.append({"slug": slug, "dir": n, "query": meta["display_name"], "rank_before": None,
                              "new_version": meta["version"], "skill_id": sid,
                              "published_at": datetime.datetime.now().isoformat(timespec="minutes")})
        else:
            failed.append((n, last))
    if a.mode == "new" and published:
        tag = a.tag or "new"
        p = ROOT / f"docs/metrics/rename-baseline-{tag}-{datetime.date.today()}.json"
        old = json.loads(p.read_text("utf-8")) if p.exists() else []
        keep = {r["slug"] for r in published}
        p.write_text(json.dumps([r for r in old if r["slug"] not in keep] + published, ensure_ascii=False, indent=1), "utf-8")
        log(f"基线已写 {p.relative_to(ROOT)}（{len(published)} 条）")
    if a.mode == "upgrade" and published:
        p = ROOT / f"docs/metrics/upgrade-published-{datetime.date.today()}.json"
        old = json.loads(p.read_text("utf-8")) if p.exists() else []
        keep = {r["slug"] for r in published}
        p.write_text(json.dumps([r for r in old if r["slug"] not in keep] + published, ensure_ascii=False, indent=1), "utf-8")
        log(f"升级记录已写 {p.relative_to(ROOT)}（{len(published)} 条）")
    log(f"发布：成功 {len(published)}，失败 {len(failed)}；日志 {logf.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
