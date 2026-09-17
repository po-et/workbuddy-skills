---
name: dockerfile-check
description: Dockerfile 体检、Dockerfile 最佳实践检查、镜像瘦身、构建缓存优化、容器安全基线（非 root、不把密钥打进镜像、固定基础镜像版本）、Docker lint。当用户说「帮我看看这个 Dockerfile 有什么问题」「镜像太大怎么优化」「Dockerfile 安全检查」「为什么每次构建都不命中缓存」「按最佳实践改一下 Dockerfile」时使用。附纯标准库脚本 scripts/dockerfile_check.py：解析续行与多阶段构建，18 条规则（基础镜像未固定版本、ENV/ARG 写入密钥、未切换非 root、curl 管道进 sh、sudo、chmod 777、apt/apk/yum/pip/npm 缓存与清理、COPY . . 早于依赖安装、缺 HEALTHCHECK/WORKDIR/.dockerignore、CMD shell 形式、ADD 代替 COPY、MAINTAINER 废弃、RUN 层过多），按 high/warn/info 分级并给出改法；支持目录递归、--json、--strict（CI 门禁）。
author: Captain
version: 0.1.0
display_name: "Dockerfile 体检"
display_name_en: "Dockerfile Check"
description_zh: "一条命令给 Dockerfile 做体检：18 条最佳实践与安全规则，分级输出并附具体改法；纯 Python 标准库，可作 CI 门禁。"
description_en: "One command to audit a Dockerfile: 18 best-practice and security rules, graded output with concrete fixes; pure Python stdlib, usable as a CI gate."
examples_zh:
  - "检查一下当前目录的 Dockerfile 有哪些问题"
  - "我们的镜像 1.2G，帮我从 Dockerfile 找瘦身点"
  - "把 Dockerfile 检查加进 CI，有 warn 就失败"
examples_en:
  - "Audit the Dockerfile in this directory"
  - "Our image is 1.2GB, find slimming opportunities in the Dockerfile"
  - "Add the Dockerfile check to CI, fail on warnings"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🐳" } }
---

# Dockerfile 体检

给 Dockerfile 做一次基于最佳实践的静态检查，输出分级问题与改法。纯 Python 标准库，不需要 Docker 守护进程。

## 用法

```bash
python3 scripts/dockerfile_check.py                 # 当前目录的 Dockerfile
python3 scripts/dockerfile_check.py path/to/Dockerfile services/   # 文件或目录（递归找 Dockerfile*、*.dockerfile）
python3 scripts/dockerfile_check.py --json          # 机器可读
python3 scripts/dockerfile_check.py --strict        # 有 high/warn 则退出码 1，用于 CI 门禁
```

## 流程

1. 跑脚本，先看 **high**（密钥打进镜像）和 **warn**（未固定版本、root 运行、管道执行远程脚本、缓存层失效）。
2. 按输出里的「→ 改法」逐条修改；每条规则的改法都是可直接落地的写法。
3. 改完再跑一次；镜像体积问题结合 `docker history <image>` 看哪一层最大。
4. 加进 CI：`--strict` 作为门禁；只想报告不拦截就去掉 `--strict`。

## 规则一览

| 级别 | 规则 | 检查点 |
|---|---|---|
| high | DF006 | ENV/ARG 把 PASSWORD/SECRET/TOKEN/KEY 类值写进镜像层 |
| warn | DF001 | 基础镜像无标签或 latest（不可复现） |
| warn | DF005 | 最终阶段没有 USER，容器以 root 运行 |
| warn | DF003 | apt-get install 与 update 不在同一 RUN（过期缓存） |
| warn | DF002 | apt-get upgrade（不可复现、膨胀） |
| warn | DF011 / DF012 / DF016 | sudo；curl/wget 管道进 sh；chmod 777 |
| info | DF002 / DF007 | apt/apk/yum/pip/npm 的缓存清理与 --no-install-recommends / --no-cache-dir / npm ci |
| info | DF008 | COPY . . 早于依赖安装，缓存被源码改动打穿 |
| info | DF004 / DF009 / DF013 / DF014 / DF015 / DF017 / DF018 | ADD 代替 COPY；缺 HEALTHCHECK；缺或相对 WORKDIR；RUN 层过多；CMD/ENTRYPOINT shell 形式；MAINTAINER；缺 .dockerignore |

## 边界

- 静态启发式，不执行构建；`FROM $VAR`、`FROM scratch`、带 digest 的镜像跳过版本检查。
- 只看最终阶段是否有 USER / HEALTHCHECK / WORKDIR；构建阶段允许 root。
- 不替代 hadolint；想要更全的规则集可把本脚本当第一道快速门禁。
