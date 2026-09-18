---
name: docker-compose-check
description: docker-compose 配置体检、compose.yaml 上线前检查、容器编排安全基线、镜像用 latest 没固定版本、缺 healthcheck 健康检查、缺 restart 重启策略、privileged 特权容器、network_mode host、pid host、挂载 /var/run/docker.sock 与 /etc 与家目录等宿主敏感路径、environment 里 PASSWORD/SECRET/TOKEN 明文密码、MySQL/Redis/PostgreSQL/MongoDB/ES 端口绑 0.0.0.0 对公网暴露、没有 mem_limit 内存上限、depends_on 没用 service_healthy、version 字段废弃、container_name 重名冲突。当用户说「帮我看看这个 docker-compose 有没有问题」「compose 文件能上生产吗」「容器为什么能访问宿主机」「这套编排安全吗」「docker compose lint」时使用。附脚本 scripts/compose_check.py，纯标准库、内置最小 YAML 解析，13 条规则分 high/warn/info 并附改法，支持目录扫描、--json、--strict 做 CI 门禁。
author: Captain
version: 0.1.0
display_name: "Compose 配置体检"
display_name_en: "Docker Compose Check"
description_zh: "不装任何依赖就能给 docker-compose.yml 做上线前体检：安全基线（特权、host 命名空间、docker.sock 与宿主敏感目录、明文密钥、数据库端口暴露）、可靠性（镜像固定版本、健康检查、重启策略、内存与 CPU 上限、依赖顺序）、废弃字段与 container_name 冲突；分级输出附改法，可作 CI 门禁。"
description_en: "Zero-dependency pre-production audit for docker-compose files: security baseline (privileged, host namespaces, docker.sock and sensitive host mounts, plaintext secrets, exposed database ports), reliability (pinned images, healthchecks, restart policy, memory and CPU limits, dependency conditions), deprecated fields and container_name clashes; graded findings with fixes, CI-gate ready."
examples_zh:
  - "帮我看看这个 docker-compose 有没有问题"
  - "这套编排安全吗，有没有挂 docker.sock 或写明文密码"
  - "compose 文件能上生产吗，顺便把配置体检加进 CI 做门禁"
examples_en:
  - "Check this docker-compose.yml for production risks"
  - "Does this stack mount docker.sock or expose database ports?"
  - "Add the compose check to CI and fail on warnings"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🐳" } }
---

# Compose 配置体检

给 docker-compose.yml / compose.yaml 做一次上线前静态检查。适用于单机 Compose 部署、本地开发栈转生产、交接别人写的编排文件、以及容器安全基线自查。脚本自带最小 YAML 解析器，不需要 PyYAML，也不需要 docker 守护进程或拉取镜像。

## 用法

```bash
python3 scripts/compose_check.py docker-compose.yml
python3 scripts/compose_check.py deploy/                    # 目录内自动找 compose 文件
python3 scripts/compose_check.py compose.yaml --json        # 结构化输出，便于二次加工
python3 scripts/compose_check.py compose.yaml --strict      # 有 high/warn 退出码 1
docker compose config > /tmp/rendered.yml && python3 scripts/compose_check.py /tmp/rendered.yml
```

输出按 high / warn / info 三级排序，每条给出规则号、问题位置（文件 + 服务名）与具体改法。

## 流程

1. 先跑一遍不带 `--strict` 的检查，看 high 数量。**high 必须处理**：特权容器、host 网络/PID 命名空间、`cap_add: SYS_ADMIN`、挂 docker.sock 或 `/`、`/etc`、家目录、明文密钥、数据库端口绑 0.0.0.0、container_name 重名、既无 image 又无 build。
2. **warn 上线前处理**：镜像没固定版本、缺 healthcheck、缺 restart、缺内存上限、带默认值的密码插值。
3. **info 按团队基线取舍**：CPU 上限、depends_on 的 condition、以 root 运行、废弃的 version 字段、端口绑 0.0.0.0。
4. 密钥类问题按「先止血再改配置」处理：把值移到 `env_file` 或 `secrets`，并把已经进过仓库的凭据轮换掉，光删文件没用。
5. 改完复跑 `--strict`；接 CI 时对生产用的那份 compose（或 `docker compose config` 渲染结果）跑门禁，例外在团队基线文档里登记。

## 规则一览

| 级别 | 规则 | 检查点 |
|---|---|---|
| high | C004 / C005 | privileged、network_mode host、pid host、cap_add ALL/SYS_ADMIN；挂载 docker.sock、`/`、`/etc`、`/root`、`/proc`、`/sys`、`/dev`、家目录 |
| high | C006 / C007 | PASSWORD/SECRET/TOKEN/KEY 类环境变量写明文；3306、5432、6379、27017、9200 等数据库端口绑到所有网卡 |
| high | C011 / C012 | 多个服务共用同一 container_name；服务既没有 image 也没有 build |
| warn | C001 / C002 / C003 / C008 | 镜像无标签或 latest；缺 healthcheck；缺 restart 策略；缺 mem_limit 或 deploy.resources.limits.memory |
| warn | C004 / C006 | ipc host、userns_mode host；`${VAR:-明文默认值}` 形式的密码插值 |
| info | C007 / C008 / C009 / C010 / C011 / C013 | 普通端口绑 0.0.0.0；缺 CPU 上限；depends_on 未用 condition service_healthy；顶层 version 已废弃、compose v1 格式；写死 container_name；以 root 运行 |

## 边界

- 只做静态检查，不连 docker 守护进程，不做镜像扫描（镜像层里的漏洞用 trivy 之类补充），也不做端口连通性验证。
- 最小 YAML 解析支持常见块结构与单行 flow 集合（`["CMD", "curl"]`、`{cpus: 1}`），不支持锚点合并 `<<: *x` 与多行 flow 集合；检测到锚点会提示先用 `docker compose config` 渲染。
- `${VAR}` 插值不做求值，只判断写法；`.env` 文件里的实际值不读取，所以本工具不会替你确认线上到底注入了什么。
- extends / 多文件 override 的合并结果不做还原，单独检查片段文件时可能误报「既无 image 也无 build」，这类文件不用纳入门禁。
- Swarm 专属字段只看 `deploy.resources.limits` 与 `deploy.restart_policy`，副本数、放置约束、更新策略不在规则内。
