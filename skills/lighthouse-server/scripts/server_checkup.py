#!/usr/bin/env python3
"""服务器体检：读 sshd 配置、监听端口、磁盘占用，输出按严重度排序的风险清单。

只读：不修改任何系统配置，不联网。纯 Python 标准库，Python 3.8+。

用法：
  # 在服务器上直接跑（加 sudo 才能读到完整 sshd 配置和进程名）
  sudo python3 server_checkup.py

  # 把输出存成文件，拿到任何电脑上跑
  sudo sshd -T > sshd_effective.txt; ss -tulnp > ports.txt; df -hP > df.txt
  python3 server_checkup.py --sshd-effective sshd_effective.txt \
      --ports-file ports.txt --df-file df.txt --format md --out report.md

  # 检查拷下来的 /etc/ssh 目录（Include 会按该目录解析）
  python3 server_checkup.py --sshd-config ./etc-ssh/sshd_config --no-ports --no-disk

退出码：
  0   体检完成（未加 --strict，或没有「高」风险）
  1   参数错误
  2   指定的输入文件读不了 / 报告写不进去
  3   加了 --strict 且发现「高」风险（可当 CI 门禁）
  130 用户按 Ctrl-C 中断
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

SEVERITIES = ("高", "中", "低", "提示")
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
CATEGORY_RANK = {"SSH": 0, "PORT": 1, "DOCKER": 2, "DISK": 3}   # 同一严重度内：登录安全 → 端口 → 磁盘

# OpenSSH 上游默认值（未显式设置时）。发行版可能在自带配置里改写，最终以 `sshd -T` 为准。
SSHD_DEFAULTS = {
    "passwordauthentication": "yes",
    "permitrootlogin": "prohibit-password",   # OpenSSH 7.0 起
    "kbdinteractiveauthentication": "yes",
    "usepam": "no",
    "permitemptypasswords": "no",
    "pubkeyauthentication": "yes",
    "port": "22",
    "maxauthtries": "6",
    "x11forwarding": "no",
}

# 对全网监听时风险较大的端口：端口 -> (常见服务, 严重度, 专门的建议或 None)
RISKY_PORTS = {
    23: ("Telnet，明文传输", "高", "停用 telnet 服务，改用 SSH"),
    2375: ("Docker 远程 API，无加密", "高",
           "去掉 dockerd 的 tcp://0.0.0.0:2375 监听（daemon.json 的 hosts 或服务启动参数）；"
           "远程管理改走 SSH，或用带 TLS 的 2376"),
    2379: ("etcd", "高", None),
    3306: ("MySQL", "高", None),
    5432: ("PostgreSQL", "高", None),
    6379: ("Redis", "高", None),
    9200: ("Elasticsearch", "高", None),
    10250: ("kubelet", "高", None),
    11211: ("Memcached", "高", None),
    27017: ("MongoDB", "高", None),
    1433: ("SQL Server", "高", None),
    21: ("FTP，明文传输", "中", "改用 SFTP（走 SSH，不用另开端口）"),
    111: ("rpcbind", "中", None),
    873: ("rsync", "中", None),
    2049: ("NFS", "中", None),
    3389: ("远程桌面", "中", None),
    5601: ("Kibana", "中", None),
    5672: ("RabbitMQ", "中", None),
    5900: ("VNC", "中", None),
    8888: ("常见为 Jupyter 或管理面板", "中", None),
    9000: ("常见为 php-fpm 或管理面板", "中", None),
    9090: ("常见为 Prometheus 或管理面板", "中", None),
    15672: ("RabbitMQ 管理台", "中", None),
}
APP_PORTS = {3000, 5000, 8000, 8080, 8081, 8443}   # 常见的应用/开发服务器端口
EXPECTED_PORTS = {22: "SSH", 80: "HTTP", 443: "HTTPS"}
UDP_CLIENT_PORTS = {68, 546, 323}                   # DHCP 客户端、chrony 本地端口等，正常
PSEUDO_FS = ("tmpfs", "devtmpfs", "overlay", "squashfs", "udev", "none", "shm", "map ", "devfs")


class InputError(Exception):
    """用户明确指定的输入读不了。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用 -h 查看全部选项。\n" % message)
        sys.exit(1)


class Finding(object):
    __slots__ = ("sev", "code", "title", "evidence", "advice")

    def __init__(self, sev, code, title, evidence, advice):
        self.sev, self.code, self.title, self.evidence, self.advice = sev, code, title, evidence, advice

    def as_dict(self):
        return {"severity": self.sev, "code": self.code, "title": self.title,
                "evidence": self.evidence, "advice": self.advice}


def read_text(path):
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        raise InputError("找不到文件：%s" % path)
    except IsADirectoryError:
        raise InputError("这是目录，不是文件：%s" % path)
    except PermissionError:
        raise InputError("没有权限读取：%s（加 sudo 运行，或先把内容另存成文件再传入）" % path)
    except OSError as exc:
        raise InputError("读取失败：%s（%s）" % (path, exc))


# ---------------------------------------------------------------- sshd

def _split_kv(line):
    """sshd_config 一行 -> (关键字小写, 值)。关键字与值之间可用空白或 '='。"""
    m = re.match(r"^\s*([A-Za-z][A-Za-z0-9]*)\s*(?:=\s*|\s+)(.*?)\s*$", line)
    if not m:
        return None, None
    value = m.group(2)
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    return m.group(1).lower(), value


def parse_sshd_config(path, state, depth=0):
    """按 sshd 的规则读配置：同一关键字「第一次读到的值」生效；跟随 Include；Match 之后按条件生效，不计入全局。"""
    if depth > 8:
        state["notes"].append("Include 嵌套超过 8 层，已停止展开：%s" % path)
        return
    text = read_text(path)
    state["files"].append(path)
    in_match = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = _split_kv(line)
        if key is None:
            continue
        if key == "match":
            in_match = True
            state["match_blocks"] += 1
            continue
        if in_match:
            continue
        if key == "include":
            for pattern in value.split():
                target = _rebase_include(pattern, state["ssh_dir"])
                hits = sorted(glob.glob(target))
                if not hits:
                    state["notes"].append("Include 没匹配到文件：%s（%s:%d）" % (pattern, path, lineno))
                for hit in hits:
                    try:
                        parse_sshd_config(hit, state, depth + 1)
                    except InputError as exc:
                        state["notes"].append("Include 的文件读不了：%s" % exc)
            continue
        if key == "port":
            state["ports"].append(value)
        if key not in state["settings"]:
            state["settings"][key] = value
            state["sources"][key] = "%s:%d" % (os.path.basename(path), lineno)


def _rebase_include(pattern, ssh_dir):
    """相对路径按 /etc/ssh 解析；检查拷下来的目录时，把 /etc/ssh/ 换成该目录。"""
    if not os.path.isabs(pattern):
        return os.path.join(ssh_dir, pattern)
    if ssh_dir != "/etc/ssh" and pattern.startswith("/etc/ssh/"):
        return os.path.join(ssh_dir, pattern[len("/etc/ssh/"):])
    return pattern


def parse_sshd_effective(text):
    """解析 `sshd -T` 的输出（每行「小写关键字 值」）。"""
    settings, ports = {}, []
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        key, value = parts[0].lower(), parts[1].strip()
        if key == "port":
            ports.append(value)
        settings.setdefault(key, value)
    return settings, ports


def check_sshd(settings, sources, ports, match_blocks, origin):
    out = []

    def get(key):
        if key == "kbdinteractiveauthentication" and key not in settings:
            if "challengeresponseauthentication" in settings:
                return settings["challengeresponseauthentication"].lower(), sources.get(
                    "challengeresponseauthentication", origin)
        if key in settings:
            return settings[key].lower(), sources.get(key, origin)
        return SSHD_DEFAULTS[key], "未显式设置，按 OpenSSH 默认值"

    pw, pw_src = get("passwordauthentication")
    root, root_src = get("permitrootlogin")
    kbd, kbd_src = get("kbdinteractiveauthentication")
    pam, _ = get("usepam")
    empty, empty_src = get("permitemptypasswords")
    pub, pub_src = get("pubkeyauthentication")

    if root == "yes" and pw == "yes":
        out.append(Finding("高", "SSH-01", "root 可以用密码登录",
                           "PermitRootLogin yes（%s）+ PasswordAuthentication yes（%s）" % (root_src, pw_src),
                           "先建 sudo 用户并配好密钥，再设 PermitRootLogin no、PasswordAuthentication no"))
    elif root == "yes":
        out.append(Finding("中", "SSH-01", "root 可以直接登录（仅密钥）",
                           "PermitRootLogin yes（%s）" % root_src,
                           "改用 sudo 用户登录后，设 PermitRootLogin no（或 prohibit-password）"))
    if pw == "yes":
        out.append(Finding("高", "SSH-02", "允许密码登录，暴露在全网爆破之下",
                           "PasswordAuthentication yes（%s）" % pw_src,
                           "确认密钥能登录后设为 no；按 references/ssh-hardening.md 走，保留救命会话"))
    elif kbd == "yes" and pam == "yes":
        out.append(Finding("中", "SSH-03", "密码登录已关，但键盘交互认证 + PAM 仍可能接受密码",
                           "KbdInteractiveAuthentication yes（%s）+ UsePAM yes" % kbd_src,
                           "同时设 KbdInteractiveAuthentication no（老版本为 ChallengeResponseAuthentication no）"))
    if empty == "yes":
        out.append(Finding("高", "SSH-04", "允许空密码登录",
                           "PermitEmptyPasswords yes（%s）" % empty_src, "立即改为 no"))
    if pub == "no" and pw == "no":
        out.append(Finding("高", "SSH-05", "密钥和密码登录都关了，重载后可能谁都进不去",
                           "PubkeyAuthentication no（%s）+ PasswordAuthentication no（%s）" % (pub_src, pw_src),
                           "先把 PubkeyAuthentication 改回 yes 再重载 sshd"))
    elif pub == "no":
        out.append(Finding("中", "SSH-05", "密钥登录被关闭，只能用密码",
                           "PubkeyAuthentication no（%s）" % pub_src, "设为 yes 并改用密钥登录"))
    try:
        tries = int(settings.get("maxauthtries", SSHD_DEFAULTS["maxauthtries"]))
        if tries > 6:
            out.append(Finding("低", "SSH-07", "单次连接允许的认证次数偏多",
                               "MaxAuthTries %d（%s）" % (tries, sources.get("maxauthtries", origin)),
                               "一般 3–6 即可"))
    except ValueError:
        pass
    if settings.get("x11forwarding", "no").lower() == "yes":
        out.append(Finding("低", "SSH-08", "开启了 X11 转发，服务器一般用不到",
                           "X11Forwarding yes（%s）" % sources.get("x11forwarding", origin), "设为 no"))
    effective_ports = ports or [SSHD_DEFAULTS["port"]]
    if "22" in effective_ports:
        out.append(Finding("提示", "SSH-06", "SSH 在默认 22 端口，扫描流量会比较多",
                           "Port %s" % " / ".join(effective_ports),
                           "改端口只能降噪，不能替代密钥登录；要改就先在控制台防火墙放行新端口"))
    if not any(k in settings for k in ("allowusers", "allowgroups")):
        out.append(Finding("提示", "SSH-09", "没有限定哪些账号能 SSH 登录",
                           "未设置 AllowUsers / AllowGroups",
                           "可加 AllowUsers <你的用户>；写错会把所有人挡在外面，改后务必新开终端验证"))
    if match_blocks:
        out.append(Finding("提示", "SSH-10", "存在 Match 条件块，上面的结论只针对全局设置",
                           "发现 %d 个 Match 块" % match_blocks, "以 sudo sshd -T 的输出为准"))
    return out


# ---------------------------------------------------------------- 端口

_PROTO_TOKENS = {"tcp": "tcp", "tcp4": "tcp", "tcp6": "tcp", "tcp46": "tcp",
                 "udp": "udp", "udp4": "udp", "udp6": "udp", "udp46": "udp"}


def parse_addr(token):
    """'0.0.0.0:22' / '[::]:22' / '*:80' / ':::80' / '127.0.0.53%lo:53' / '*.22'(BSD) -> (地址, 端口)。"""
    token = token.strip()
    m = re.match(r"^(.*)[:](\d{1,5})$", token)
    if not m:
        m = re.match(r"^(\*|[0-9.]+|[0-9a-fA-F:]*:[0-9a-fA-F:.]*)\.(\d{1,5})$", token)   # BSD：地址.端口
    if not m:
        return None
    addr, port = m.group(1), int(m.group(2))
    if addr.startswith("[") and addr.endswith("]"):
        addr = addr[1:-1]
    addr = addr.split("%", 1)[0]
    if addr.startswith("::ffff:"):
        addr = addr[len("::ffff:"):]
    if not 0 < port < 65536:
        return None
    return addr, port


def parse_listeners(text):
    """解析 `ss -tulnp` / `ss -tlnp` / `netstat -tulnp` / `netstat -an` 的输出。"""
    rows, seen = [], set()
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) < 4:
            continue
        head = tokens[0].lower()
        if head in ("state", "netid", "proto", "active") or head.startswith("recv"):
            continue
        proto = _PROTO_TOKENS.get(head)
        rest = tokens[1:] if proto else tokens
        upper = [t.upper() for t in rest]
        if proto is None:
            proto = "udp" if "UNCONN" in upper else "tcp"
        if proto == "tcp" and "LISTEN" not in upper:
            continue                    # 已建立的连接等，不是监听
        local = None
        for tok in rest:
            if tok.isdigit() or tok.upper() in ("LISTEN", "UNCONN"):
                continue
            local = parse_addr(tok)
            if local:
                break
        if not local:
            continue
        process = ""
        m = re.search(r'users:\(\("([^"]+)"', line)
        if m:
            process = m.group(1)
        else:
            m = re.search(r"\s\d+/(\S+)", line)
            if m:
                process = m.group(1).rstrip(":")
        key = (proto, local[0], local[1], process)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"proto": proto, "addr": local[0], "port": local[1], "process": process})
    rows.sort(key=lambda r: (r["port"], r["proto"], r["addr"], r["process"]))
    return rows


def scope_of(addr):
    if addr in ("0.0.0.0", "::", "*", ""):
        return "public", "所有网卡"
    if addr.startswith("127.") or addr == "::1" or addr == "localhost":
        return "local", "仅本机"
    return "specific", "指定地址 %s" % addr


def check_ports(rows, sshd_ports):
    out, table = [], []
    by_port = {}
    for r in rows:
        scope, label = scope_of(r["addr"])
        r["scope"], r["scope_label"] = scope, label
        by_port.setdefault((r["proto"], r["port"]), []).append(r)
    for (proto, port), items in sorted(by_port.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        scopes = {i["scope"] for i in items}
        procs = sorted({i["process"] for i in items if i["process"]})
        proc_txt = ",".join(procs) or "未知进程（用 sudo 运行 ss 才看得到）"
        exposed = "public" in scopes or "specific" in scopes
        verdict = "仅本机，正常"
        if exposed:
            where = "所有网卡" if "public" in scopes else "指定地址"
            evidence = "%s %d 监听在%s，进程 %s" % (proto, port, where, proc_txt)
            if proto == "tcp" and (port in EXPECTED_PORTS or str(port) in sshd_ports):
                verdict = "对外（%s，常规）" % EXPECTED_PORTS.get(port, "SSH")
            elif proto == "udp" and port == 443:
                verdict = "对外（HTTP/3，常规）"
            elif port in RISKY_PORTS:
                name, sev, special = RISKY_PORTS[port]
                verdict = "对外（%s，风险）" % name
                advice = special or ("改为只听 127.0.0.1（容器用 -p 127.0.0.1:%d:%d 或不映射端口）" % (port, port))
                out.append(Finding(sev, "PORT-%d" % port, "%d 端口（%s）对外监听" % (port, name), evidence,
                                   advice + "；并确认控制台防火墙没有放行 %d" % port))
            elif proto == "udp" and port in UDP_CLIENT_PORTS:
                verdict = "系统客户端端口，正常"
            elif proto == "udp" and port == 53:
                verdict = "对外（DNS）"
                out.append(Finding("中", "PORT-53", "DNS 服务对外监听，可能被当作开放解析器滥用", evidence,
                                   "不对外提供 DNS 就改为只听本机，控制台防火墙不放行 53"))
            elif port in APP_PORTS:
                verdict = "对外（应用端口）"
                out.append(Finding("中", "PORT-%d" % port, "应用端口直接对外，没经过 Nginx 与 HTTPS", evidence,
                                   "应用改听 127.0.0.1:%d，由 Nginx 反代并启用 HTTPS" % port))
            else:
                verdict = "对外（非常用端口）"
                out.append(Finding("低", "PORT-%d" % port, "非常用端口对外监听", evidence,
                                   "确认是否必须对外；不需要就改听 127.0.0.1，并在控制台防火墙关闭"))
            if "docker-proxy" in procs:
                out.append(Finding("中", "DOCKER-%d" % port, "Docker 映射的端口不受主机 ufw 规则约束", evidence,
                                   "容器端口映射写成 127.0.0.1:%d:容器端口，外层靠控制台防火墙" % port))
        table.append({"proto": proto, "port": port,
                      "scope": "/".join(sorted({i["scope_label"] for i in items})),
                      "process": ",".join(procs) or "-", "verdict": verdict})
    tcp_ports = {str(r["port"]) for r in rows if r["proto"] == "tcp"}
    missing = [p for p in sshd_ports if p not in tcp_ports]
    if rows and sshd_ports and missing:
        out.append(Finding("提示", "SSH-11", "sshd 配置里的端口没有出现在监听列表",
                           "配置 Port %s，监听列表里没有" % "/".join(missing),
                           "可能改了配置还没重启/重载，或使用 socket 激活（Ubuntu 较新版本）；以 ss -tlnp 实际为准"))
    return out, table


def collect_ports_live():
    """在本机跑 ss / netstat（只读）。返回 (文本, 用的命令) 或 (None, 原因)。"""
    for cmd in (["ss", "-tulnp"], ["netstat", "-tulnp"], ["netstat", "-an"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except (subprocess.TimeoutExpired, OSError):
            continue
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout, " ".join(cmd)
    return None, "本机没有可用的 ss / netstat，或运行失败"


# ---------------------------------------------------------------- 磁盘

def parse_df(text):
    rows = []
    inode_mode = False
    for line in text.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0].lower() == "filesystem":
            inode_mode = any("inode" in t.lower() or t.lower() == "iuse%" for t in tokens)
            continue
        pct_idx = next((i for i, t in enumerate(tokens) if re.match(r"^\d+%$", t)), None)
        if pct_idx is None or pct_idx == len(tokens) - 1:
            continue
        fs, mount = tokens[0], " ".join(tokens[pct_idx + 1:])
        if any(fs.lower().startswith(p.strip()) for p in PSEUDO_FS):
            continue
        if mount.startswith(("/dev", "/run", "/sys", "/proc", "/snap")) or fs.startswith("/dev/loop"):
            continue
        rows.append({"mount": mount, "fs": fs, "pct": int(tokens[pct_idx][:-1]),
                     "kind": "inode" if inode_mode else "space"})
    return rows


def disk_live(paths):
    rows, notes = [], []
    for p in paths:
        try:
            u = shutil.disk_usage(p)
        except OSError as exc:
            notes.append("读不到 %s 的磁盘占用（%s）" % (p, exc))
            continue
        pct = int(round(u.used * 100.0 / u.total)) if u.total else 0
        rows.append({"mount": p, "fs": "-", "pct": pct, "kind": "space",
                     "free_gb": round(u.free / 1024.0 ** 3, 1)})
    return rows, notes


def check_disk(rows, warn, crit):
    out = []
    for r in rows:
        what = "inode" if r["kind"] == "inode" else "空间"
        evidence = "%s %s 已用 %d%%" % (r["mount"], what, r["pct"])
        if r["pct"] >= crit:
            out.append(Finding("高", "DISK-%s" % r["mount"], "磁盘%s快满了" % what, evidence,
                               "先 du 找大目录（日志、Docker 镜像、备份），确认后再清理；必要时扩容"))
        elif r["pct"] >= warn:
            out.append(Finding("中", "DISK-%s" % r["mount"], "磁盘%s占用偏高" % what, evidence,
                               "排查增长来源，设置日志轮转与 Docker 日志上限"))
    return out


# ---------------------------------------------------------------- 输出

MANUAL_CHECKS = (
    "控制台防火墙：只放行 SSH 端口、80、443（脚本看不到控制台规则，以腾讯云控制台为准）",
    "快照与机外备份：最近 7 天内有，且做过一次恢复演练",
    "流量：控制台里本月流量用量未接近套餐上限（计费与限速规则以官方为准）",
    "备案：国内地域对外提供网站服务通常需要备案，以官方要求为准",
)


def _pad(text, width):
    """按显示宽度补空格（中文占两格），让终端里的表格对齐。"""
    shown = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)
    return text + " " * max(1, width - shown)


def render(report, fmt):
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    counts = report["summary"]
    lines = []
    md = fmt == "md"
    lines.append("# 服务器体检报告" if md else "服务器体检报告")
    lines.append("")
    lines.append("## 输入" if md else "【输入】")
    for item in report["inputs"]:
        lines.append(("- " if md else "  ") + item)
    lines.append("")
    lines.append("## 风险清单" if md else "【风险清单】（高 → 中 → 低 → 提示）")
    if md:
        lines.append("| 严重度 | 编号 | 问题 | 证据 | 建议 |")
        lines.append("|---|---|---|---|---|")
    for f in report["findings"]:
        if md:
            lines.append("| %s | %s | %s | %s | %s |" % (f["severity"], f["code"], f["title"],
                                                        f["evidence"].replace("|", "/"), f["advice"]))
        else:
            lines.append("[%s] %s %s" % (f["severity"], f["code"], f["title"]))
            lines.append("      证据：%s" % f["evidence"])
            lines.append("      建议：%s" % f["advice"])
    if not report["findings"]:
        lines.append("（没有发现问题——但下面【说明】里有没做成的检查，先补上再下结论）"
                     if report["notes"] else "（没有发现问题）")
    if report["ports"]:
        lines.append("")
        lines.append("## 监听端口" if md else "【监听端口】")
        if md:
            lines.append("| 协议 | 端口 | 监听范围 | 进程 | 判断 |")
            lines.append("|---|---|---|---|---|")
        for p in report["ports"]:
            if md:
                lines.append("| %s | %d | %s | %s | %s |" % (p["proto"], p["port"], p["scope"], p["process"], p["verdict"]))
            else:
                lines.append("  " + _pad(p["proto"], 5) + _pad(str(p["port"]), 7) + _pad(p["scope"], 12)
                             + _pad(p["process"], 18) + p["verdict"])
    if report["disks"]:
        lines.append("")
        lines.append("## 磁盘" if md else "【磁盘】")
        for d in report["disks"]:
            what = "inode" if d["kind"] == "inode" else "空间"
            lines.append(("- " if md else "  ") + "%s %s 已用 %d%%" % (d["mount"], what, d["pct"]))
    if report["notes"]:
        lines.append("")
        lines.append("## 说明" if md else "【说明】")
        for n in report["notes"]:
            lines.append(("- " if md else "  ") + n)
    lines.append("")
    lines.append("## 脚本看不到、需要人工核对" if md else "【脚本看不到、需要人工核对】")
    for m in MANUAL_CHECKS:
        lines.append(("- [ ] " if md else "  □ ") + m)
    lines.append("")
    lines.append("汇总：高 %d / 中 %d / 低 %d / 提示 %d" % (counts["高"], counts["中"], counts["低"], counts["提示"]))
    return "\n".join(lines) + "\n"


def write_atomic(path, content):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise InputError("输出目录不存在：%s" % directory)
    fd, tmp = tempfile.mkstemp(prefix=".checkup-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise InputError("报告写入失败：%s（%s）" % (path, exc))


def build_parser():
    p = Parser(description="服务器体检（只读）：sshd 配置 + 监听端口 + 磁盘占用 -> 风险清单。",
               epilog="退出码：0 完成；1 参数错误；2 读写文件失败；3 --strict 且有高风险；130 中断。")
    p.add_argument("--sshd-config", help="sshd_config 路径（默认 /etc/ssh/sshd_config；会跟随 Include）")
    p.add_argument("--sshd-effective", help="`sudo sshd -T` 的输出文件（最准确；给了就不再读 sshd_config）")
    p.add_argument("--no-sshd", action="store_true", help="跳过 sshd 检查")
    p.add_argument("--ports-file", help="`ss -tulnp` 或 `netstat -tulnp` 的输出文件；'-' 表示从标准输入读")
    p.add_argument("--no-ports", action="store_true", help="跳过端口检查")
    p.add_argument("--df-file", help="`df -hP`（或 `df -iP`）的输出文件")
    p.add_argument("--path", action="append", help="直接统计的挂载点，可多次给出（默认 /）")
    p.add_argument("--no-disk", action="store_true", help="跳过磁盘检查")
    p.add_argument("--disk-warn", type=int, default=80, help="磁盘占用「中」阈值，百分比（默认 80）")
    p.add_argument("--disk-crit", type=int, default=90, help="磁盘占用「高」阈值，百分比（默认 90）")
    p.add_argument("--format", choices=("text", "md", "json"), default="text", help="输出格式（默认 text）")
    p.add_argument("--out", help="把报告写入文件（先写临时文件再替换）")
    p.add_argument("--strict", action="store_true", help="有「高」风险时退出码为 3")
    return p


def run(args):
    if not 0 < args.disk_warn < args.disk_crit <= 100:
        raise ValueError("--disk-warn 必须小于 --disk-crit，且都在 1–100 之间")
    findings, notes, inputs = [], [], []
    ports_table, disks = [], []
    sshd_ports = []          # sshd 配置里显式写的 Port
    sshd_checked = False

    if not args.no_sshd:
        if args.sshd_effective:
            settings, sshd_ports = parse_sshd_effective(read_text(args.sshd_effective))
            if not settings:
                raise InputError("%s 里没有识别到「关键字 值」格式的行，确认是 `sudo sshd -T` 的输出" % args.sshd_effective)
            findings += check_sshd(settings, {}, sshd_ports, 0, "sshd -T")
            sshd_checked = True
            inputs.append("sshd：%s（sshd -T 生效配置，%d 项）" % (args.sshd_effective, len(settings)))
        else:
            explicit = bool(args.sshd_config)
            path = args.sshd_config or "/etc/ssh/sshd_config"
            state = {"settings": {}, "sources": {}, "ports": [], "files": [], "notes": [],
                     "match_blocks": 0, "ssh_dir": os.path.dirname(os.path.abspath(path))}
            try:
                parse_sshd_config(path, state)
            except InputError as exc:
                if explicit:
                    raise
                notes.append("跳过 sshd 检查：%s。可在服务器上 `sudo sshd -T > sshd_effective.txt` 后用 --sshd-effective 传入" % exc)
                state = None
            if state:
                sshd_ports = state["ports"]
                findings += check_sshd(state["settings"], state["sources"], sshd_ports,
                                       state["match_blocks"], os.path.basename(path))
                notes += state["notes"]
                sshd_checked = True
                inputs.append("sshd：%s（共读 %d 个文件，含 Include）" % (path, len(state["files"])))

    if not args.no_ports:
        if args.ports_file:
            text, source = read_text(args.ports_file), args.ports_file
        else:
            text, source = collect_ports_live()
        if text is None:
            notes.append("未能获取监听端口：%s。请在服务器上运行 `ss -tulnp > ports.txt`，再用 --ports-file 传入" % source)
        else:
            rows = parse_listeners(text)
            if not rows:
                notes.append("%s 里没有识别到监听中的端口：请用 `ss -tulnp` 或 `netstat -tulnp` 的原样输出" % source)
            effective = (sshd_ports or ["22"]) if sshd_checked else []
            port_findings, ports_table = check_ports(rows, effective)
            findings += port_findings
            inputs.append("端口：%s（识别到 %d 条监听）" % (source, len(rows)))

    if not args.no_disk:
        if args.df_file:
            disks = parse_df(read_text(args.df_file))
            if not disks:
                notes.append("%s 里没有识别到磁盘行：请用 `df -hP` 的原样输出" % args.df_file)
            inputs.append("磁盘：%s（%d 个挂载点）" % (args.df_file, len(disks)))
        else:
            disks, disk_notes = disk_live(args.path or ["/"])
            notes += disk_notes
            inputs.append("磁盘：本机实时统计 %s" % ", ".join(args.path or ["/"]))
        findings += check_disk(disks, args.disk_warn, args.disk_crit)

    if not inputs:
        notes.append("所有检查都被跳过了，没有可报告的内容")
    findings.sort(key=lambda f: (SEV_RANK[f.sev], CATEGORY_RANK.get(f.code.split("-")[0], 9), f.code, f.evidence))
    summary = {s: sum(1 for f in findings if f.sev == s) for s in SEVERITIES}
    report = {"inputs": inputs, "findings": [f.as_dict() for f in findings], "ports": ports_table,
              "disks": disks, "notes": notes, "summary": summary}
    return report


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except ValueError as exc:
        sys.stderr.write("参数错误：%s\n" % exc)
        return 1
    except InputError as exc:
        sys.stderr.write("输入/输出错误：%s\n" % exc)
        return 2
    text = render(report, args.format)
    if args.out:
        try:
            write_atomic(args.out, text)
        except InputError as exc:
            sys.stderr.write("输入/输出错误：%s\n" % exc)
            return 2
        s = report["summary"]
        print("报告已写入 %s（高 %d / 中 %d / 低 %d / 提示 %d）" % (args.out, s["高"], s["中"], s["低"], s["提示"]))
    else:
        sys.stdout.write(text)
    if args.strict and report["summary"]["高"]:
        return 3
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(130)
