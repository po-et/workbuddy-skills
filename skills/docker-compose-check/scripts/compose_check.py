#!/usr/bin/env python3
"""docker-compose 体检：不依赖 PyYAML / docker 的最小 YAML 解析 + 上线前静态检查。

用法：
  python3 compose_check.py docker-compose.yml [compose.prod.yaml ...] [--json] [--strict]
  python3 compose_check.py deploy/            # 目录内自动找 compose 文件
  --strict：存在 high/warn 则退出码 1。
覆盖：services 下的镜像、健康检查、重启策略、特权与命名空间、卷挂载、明文密钥、端口暴露、
      资源上限、依赖顺序、废弃字段、container_name 冲突。
限制：不支持 YAML 锚点合并（<<: *x）与多行 flow 集合；先用 docker compose config 渲染更稳妥。
"""
import argparse, json, os, re, sys

SECRET_NAME = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|ACCESS_?KEY|CREDENTIAL|AUTH)", re.I)
# 明文里常见的占位值不算泄露
PLACEHOLDER = re.compile(r"^(changeme|change_me|placeholder|your[-_]?\w*|xxx+|todo|<[^>]+>|\*+)$", re.I)
DB_PORTS = {"3306": "MySQL", "5432": "PostgreSQL", "6379": "Redis", "27017": "MongoDB", "9200": "Elasticsearch",
            "9300": "Elasticsearch 集群", "5672": "RabbitMQ", "11211": "Memcached", "2379": "etcd",
            "1433": "SQL Server", "1521": "Oracle", "7001": "Redis 集群", "8020": "HDFS"}
SENSITIVE_MOUNTS = [
    ("/var/run/docker.sock", "high", "挂载 Docker socket 等于把宿主 root 权限交给容器"),
    ("/etc", "high", "宿主 /etc 可读写会暴露/篡改系统配置"),
    ("/root", "high", "宿主 root 家目录"),
    ("/proc", "high", "宿主 /proc"),
    ("/sys", "high", "宿主 /sys"),
    ("/dev", "high", "宿主 /dev"),
    ("/var/lib/docker", "high", "Docker 数据目录"),
    ("/usr", "warn", "宿主系统目录"),
    ("/boot", "warn", "宿主启动分区"),
]
COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


# ---------- 最小 YAML 解析（与 k8s-manifest-check 同源） ----------
def scalar(s):
    s = s.strip()
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s[:1] in ("'", '"') and s[-1:] == s[:1] and len(s) >= 2:
        return s[1:-1]
    if s in ("true", "True", "TRUE", "yes", "on"): return True
    if s in ("false", "False", "FALSE", "no", "off"): return False
    if re.fullmatch(r"-?\d+", s): return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s): return float(s)
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [scalar(x) for x in inner.split(",")] if inner else []
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for kv in s[1:-1].split(","):
            if ":" in kv:
                k, v = kv.split(":", 1); out[k.strip()] = scalar(v)
        return out
    return s


def split_kv(line):
    """把 'key: value' 切开；忽略引号内的冒号。"""
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q: q = None
        elif ch in ("'", '"'): q = ch
        elif ch == ":" and (i + 1 == len(line) or line[i + 1] in " \t"):
            return line[:i].strip(), line[i + 1:].strip()
    return None, None


def strip_comment(line):
    q, out = None, []
    for i, ch in enumerate(line):
        if q:
            if ch == q: q = None
        elif ch in ("'", '"'): q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_block(lines, i, indent):
    """解析从 lines[i] 开始、缩进为 indent 的块；返回 (值, 下一行号)。"""
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
            if not text.strip(): i += 1; continue
            if ind != indent or not (text.startswith("- ") or text == "-"):
                break
            body = text[1:].strip()
            if not body:
                val, i = parse_block(lines, i + 1, indent + 1); out.append(val); continue
            k, v = split_kv(body)
            if k is not None and not body.startswith(("'", '"', "[", "{")):
                lines[i] = (indent + 2, body)
                val, i = parse_block(lines, i, indent + 2); out.append(val)
            else:
                out.append(scalar(body)); i += 1
        return out, i
    out = {}
    while i < len(lines):
        ind, text = lines[i]
        if not text.strip(): i += 1; continue
        if ind < indent or (ind == indent and (text.startswith("- ") or text == "-")):
            break
        if ind > indent:
            i += 1; continue
        k, v = split_kv(text)
        if k is None:
            i += 1; continue
        if v in ("|", "|-", "|+", ">", ">-", ">+"):
            block, j = [], i + 1
            while j < len(lines) and (not lines[j][1].strip() or lines[j][0] > indent):
                block.append(lines[j][1]); j += 1
            out[k] = "\n".join(block); i = j; continue
        if v == "":
            j = i + 1
            while j < len(lines) and not lines[j][1].strip(): j += 1
            if j < len(lines) and (lines[j][0] > indent or (lines[j][0] == indent and lines[j][1].startswith("- "))):
                out[k], i = parse_block(lines, j, lines[j][0])
            else:
                out[k] = None; i = j
            continue
        if v.startswith("&"):
            v = v.split(" ", 1)[1] if " " in v else ""
        out[k] = scalar(v); i += 1
    return out, i


def load_yaml(text):
    raw = [strip_comment(l.replace("\t", "  ")) for l in text.splitlines()]
    lines = [(len(l) - len(l.lstrip(" ")), l.strip()) for l in raw if l.strip()]
    if not lines:
        return {}
    doc, _ = parse_block(lines, 0, lines[0][0])
    return doc if isinstance(doc, dict) else {}


# ---------- 工具 ----------
def as_list(v):
    if v is None: return []
    return v if isinstance(v, list) else [v]


def env_items(env):
    """environment 支持 map 与 'KEY=value' 列表两种写法，统一成 (key, value) 列表。"""
    out = []
    if isinstance(env, dict):
        for k, v in env.items():
            out.append((str(k), "" if v is None else str(v)))
    else:
        for item in as_list(env):
            s = str(item)
            k, _, v = s.partition("=")
            out.append((k.strip(), v.strip()))
    return out


def mount_source(v):
    """卷条目 -> 宿主侧路径（短语法 src:dst[:mode]，长语法 type/source/target）。"""
    if isinstance(v, dict):
        return str(v.get("source") or "") if v.get("type") in (None, "bind") else ""
    s = str(v)
    if ":" not in s:
        return ""
    src = s.split(":")[0]
    return src if src.startswith(("/", ".", "~", "$")) else ""


def port_binding(p):
    """端口条目 -> (监听地址, 宿主端口, 容器端口)；只关心发布到宿主的端口。"""
    if isinstance(p, dict):
        return (str(p.get("host_ip") or "0.0.0.0"), str(p.get("published") or ""), str(p.get("target") or ""))
    s = str(p).strip().strip("'\"")
    proto = ""
    if "/" in s:
        s, _, proto = s.partition("/")
    parts = s.split(":")
    if len(parts) == 1:
        return ("", "", parts[0])            # 只写容器端口，随机映射，不算显式暴露
    if len(parts) == 2:
        return ("0.0.0.0", parts[0], parts[1])
    return (":".join(parts[:-2]), parts[-2], parts[-1])


def norm_path(p):
    p = str(p).strip()
    return p[:-1] if len(p) > 1 and p.endswith("/") else p


# ---------- 检查 ----------
def check_service(name, svc, add):
    if not isinstance(svc, dict):
        add("C012", "warn", f"服务 {name} 的定义不是映射，已跳过", "检查缩进；或先跑 docker compose config 渲染")
        return
    img = str(svc.get("image") or "")
    if not img and not svc.get("build") and not svc.get("extends"):
        add("C012", "high", f"服务 {name} 既没有 image 也没有 build", "至少写一个；纯 extends/override 片段请放到单独文件并排除检查")
    if img:
        last = img.split("/")[-1]
        tagless = "@sha256:" not in img and ":" not in last
        if tagless or img.endswith(":latest"):
            add("C001", "warn", f"服务 {name} 镜像未固定版本：{img}", "写明确 tag（如 nginx:1.27.3-alpine）或 digest，保证可回滚可复现")

    if not svc.get("healthcheck"):
        add("C002", "warn", f"服务 {name} 没有 healthcheck", "加 healthcheck（test/interval/timeout/retries/start_period），否则 depends_on 与编排都无法判断可用")
    elif isinstance(svc.get("healthcheck"), dict) and svc["healthcheck"].get("disable") is True:
        add("C002", "warn", f"服务 {name} 显式 healthcheck.disable: true", "线上服务建议保留健康检查")

    restart = svc.get("restart")
    deploy = svc.get("deploy") if isinstance(svc.get("deploy"), dict) else {}
    if not restart and not (deploy.get("restart_policy")):
        add("C003", "warn", f"服务 {name} 没有 restart 策略", "单机加 restart: unless-stopped（或 always）；Swarm 用 deploy.restart_policy")
    elif restart == "no":
        add("C003", "info", f"服务 {name} restart: \"no\"", "确认是一次性任务；常驻服务改 unless-stopped")

    if svc.get("privileged") is True:
        add("C004", "high", f"服务 {name} privileged: true", "几乎等于宿主 root；改用 cap_add 精确授权（如 NET_ADMIN）")
    if str(svc.get("network_mode") or "") == "host":
        add("C004", "high", f"服务 {name} network_mode: host", "容器与宿主共用网络栈，端口隔离失效；改用自定义 bridge 网络 + ports")
    if str(svc.get("pid") or "") == "host":
        add("C004", "high", f"服务 {name} pid: host", "容器能看到并操作宿主全部进程；仅监控类组件可例外")
    if str(svc.get("ipc") or "") == "host":
        add("C004", "warn", f"服务 {name} ipc: host", "共享宿主 IPC 命名空间，确认确有共享内存需求")
    if str(svc.get("userns_mode") or "") == "host":
        add("C004", "warn", f"服务 {name} userns_mode: host", "关闭了用户命名空间重映射")
    for cap in as_list(svc.get("cap_add")):
        if str(cap).upper() in ("ALL", "SYS_ADMIN"):
            add("C004", "high", f"服务 {name} cap_add: {cap}", "等价于特权容器；只加真正需要的 capability")

    for v in as_list(svc.get("volumes")):
        src = norm_path(mount_source(v))
        if not src:
            continue
        ro = isinstance(v, str) and v.rstrip().endswith((":ro", ":ro,z", ":ro,Z"))
        if src == "/":
            add("C005", "high", f"服务 {name} 挂载了宿主根目录 /", "改成只挂真正需要的子目录")
            continue
        if src in ("~", "$HOME", "${HOME}") or src.startswith(("~/", "$HOME/", "${HOME}/")):
            add("C005", "high", f"服务 {name} 挂载了家目录 {src}", "家目录含 SSH 私钥与云凭据；改挂项目内的具体子目录")
            continue
        for prefix, sev, why in SENSITIVE_MOUNTS:
            if src == prefix or src.startswith(prefix + "/"):
                if prefix == "/var/run/docker.sock" and ro:
                    add("C005", "high", f"服务 {name} 挂载 {src}（只读也不安全）", "只读 socket 仍可创建特权容器；改用 docker-socket-proxy 限制 API")
                else:
                    add("C005", "high" if sev == "high" else "warn", f"服务 {name} 挂载宿主敏感路径 {src}", f"{why}；确需只读时至少加 :ro，并改挂最小子路径")
                break

    for k, v in env_items(svc.get("environment")):
        if not SECRET_NAME.search(k) or not v:
            continue
        if v.startswith("${") or v.startswith("$"):
            m = re.match(r"^\$\{[A-Za-z_]\w*:?-(.+)\}$", v)
            if m and not PLACEHOLDER.match(m.group(1)):
                add("C006", "warn", f"服务 {name} 的 {k} 用了带默认值的插值 {v}", "去掉默认值，改用 ${VAR:?missing} 强制外部注入")
            continue
        if PLACEHOLDER.match(v):
            add("C006", "info", f"服务 {name} 的 {k} 是占位值", "上线前确认改为 env_file / secrets 注入")
        else:
            add("C006", "high", f"服务 {name} 的环境变量 {k} 写了明文值", "移到 env_file（并加进 .gitignore）或 docker secrets；仓库里已泄露的凭据要轮换")

    for p in as_list(svc.get("ports")):
        ip, host_port, cport = port_binding(p)
        if not host_port:
            continue
        pub = host_port.split("-")[0]
        cp = cport.split("-")[0]
        if ip in ("0.0.0.0", "::", "*") and (cp in DB_PORTS or pub in DB_PORTS):
            svc_kind = DB_PORTS.get(cp) or DB_PORTS.get(pub)
            add("C007", "high", f"服务 {name} 把 {svc_kind} 端口 {pub} 绑到所有网卡", "改成 127.0.0.1:%s:%s 只在本机暴露，或删掉 ports 走 compose 内部网络互访" % (pub, cp))
        elif ip in ("0.0.0.0", "::", "*"):
            add("C007", "info", f"服务 {name} 端口 {pub} 绑定 0.0.0.0", "只给本机用的端口写 127.0.0.1:%s:%s；对外端口确认有防火墙/网关兜底" % (pub, cp))

    limits = deploy.get("resources", {}).get("limits") if isinstance(deploy.get("resources"), dict) else None
    limits = limits if isinstance(limits, dict) else {}
    if not limits.get("memory") and not svc.get("mem_limit"):
        add("C008", "warn", f"服务 {name} 没有内存上限", "单机写 mem_limit: 512m；Swarm/compose v3 写 deploy.resources.limits.memory")
    if not limits.get("cpus") and not svc.get("cpus") and not svc.get("cpu_quota"):
        add("C008", "info", f"服务 {name} 没有 CPU 上限", "写 cpus: \"1.0\" 或 deploy.resources.limits.cpus，避免单容器打满宿主")

    dep = svc.get("depends_on")
    if isinstance(dep, list) and dep:
        add("C009", "info", f"服务 {name} 的 depends_on 只保证启动顺序", "改用长语法 depends_on: {%s: {condition: service_healthy}} 并给被依赖方配 healthcheck" % dep[0])
    elif isinstance(dep, dict):
        for d, cond in dep.items():
            c = cond.get("condition") if isinstance(cond, dict) else None
            if c != "service_healthy" and c != "service_completed_successfully":
                add("C009", "info", f"服务 {name} 依赖 {d} 的 condition 是 {c or '未写'}", "依赖数据库/中间件时用 condition: service_healthy，避免启动时连接失败")

    if svc.get("user") in (None, "root", "0", 0, "0:0"):
        add("C013", "info", f"服务 {name} 以 root 运行（未设置 user）", "镜像内建非 root 用户后写 user: \"1000:1000\"；配合 read_only: true 更稳")


def check_file(path, findings):
    rel = os.path.relpath(path) if os.path.abspath(path).startswith(os.getcwd()) else path
    text = open(path, encoding="utf-8", errors="replace").read()

    def add(rule, sev, msg, fix):
        findings.append({"rule": rule, "severity": sev, "file": rel, "message": msg, "fix": fix})

    if re.search(r"<<:\s*\*", text):
        add("C000", "info", "文件使用了 YAML 锚点合并（<<: *），最小解析器会忽略被合并的字段", "先跑 docker compose config > rendered.yml 再检查渲染结果")
    doc = load_yaml(text)
    if not doc:
        add("C000", "warn", "没解析出任何内容", "确认是 compose 文件且缩进正确")
        return 0
    if "version" in doc:
        add("C010", "info", f"顶层 version: {doc.get('version')} 已废弃", "Compose V2 起忽略该字段，直接删掉，避免误以为在用 v3 的语义")
    services = doc.get("services")
    if not isinstance(services, dict):
        services = {k: v for k, v in doc.items() if isinstance(v, dict) and (v.get("image") or v.get("build"))}
        if services:
            add("C010", "info", "没有顶层 services，按 compose v1 格式解析", "升级到 services: 开头的 V2/V3 写法")
    if not services:
        add("C000", "warn", "没找到 services", "确认文件路径与内容")
        return 0

    names = {}
    for name, svc in services.items():
        if isinstance(svc, dict) and svc.get("container_name"):
            names.setdefault(str(svc["container_name"]), []).append(name)
        check_service(name, svc, add)
    for cn, owners in names.items():
        if len(owners) > 1:
            add("C011", "high", f"container_name {cn} 被多个服务共用：{', '.join(owners)}", "容器名全局唯一，二者不可能同时起来；删掉 container_name 让 compose 自动命名")
        elif len(owners) == 1:
            add("C011", "info", f"服务 {owners[0]} 写死了 container_name {cn}", "写死名字会挡住 scale 与多环境并存；一般交给 compose 自动命名")
    return len(services)


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for r, dirs, fs in os.walk(p):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv", "__pycache__")]
                for f in sorted(fs):
                    if f in COMPOSE_NAMES or re.fullmatch(r"(docker-)?compose[.\w-]*\.ya?ml", f):
                        files.append(os.path.join(r, f))
        else:
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser(description="docker-compose 配置体检")
    ap.add_argument("paths", nargs="+", help="compose 文件或目录")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 high/warn 时退出码 1")
    a = ap.parse_args()
    files = collect(a.paths)
    if not files:
        sys.exit("没有找到 compose 文件（docker-compose.yml / compose.yaml）")
    findings, n_svc = [], 0
    for f in files:
        if not os.path.isfile(f):
            findings.append({"rule": "C000", "severity": "warn", "file": f, "message": "文件不存在", "fix": "检查路径"})
            continue
        n_svc += check_file(f, findings)
    order = {"high": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda x: (order[x["severity"]], x["file"], x["rule"]))
    counts = {s: sum(1 for x in findings if x["severity"] == s) for s in ("high", "warn", "info")}
    if a.json:
        print(json.dumps({"files": len(files), "services": n_svc, "summary": counts, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        print(f"检查 {len(files)} 个文件、{n_svc} 个服务")
        if not findings:
            print("  ✓ 没有发现问题")
        cur = None
        for x in findings:
            if x["file"] != cur:
                print(f"\n== {x['file']}"); cur = x["file"]
            print(f"  [{x['severity'].upper():4}] {x['rule']}: {x['message']}\n         → {x['fix']}")
        print(f"\n小计：high {counts['high']} / warn {counts['warn']} / info {counts['info']}")
    sys.exit(1 if (a.strict and (counts["high"] or counts["warn"])) else 0)


if __name__ == "__main__":
    main()
