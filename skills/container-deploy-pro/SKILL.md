---
name: container-deploy-pro
description: 容器与部署助手，把从写 Dockerfile 到上线回滚之间的检查活儿全接了：镜像构建与瘦身、多阶段构建、非 root 运行、基础镜像版本固定、compose 编排清单体检、K8s 清单的探针与资源限制与安全基线、nginx 反向代理与网关配置、HTTPS 证书到期与 SAN 覆盖、环境变量与多环境配置对齐、密钥有没有硬编码进仓库、数据库迁移会不会锁表、上线前一次性体检与三态门禁结论、发布后健康巡检、回滚边界与回滚顺序。当用户说容器、镜像、Docker、Dockerfile、compose、K8s、Kubernetes、YAML、部署、发布、上线、灰度、回滚、探针、健康检查、nginx、反向代理、证书、过期、环境变量、配置、镜像太大、构建慢、启动失败、CrashLoopBackOff 等任一说法，但不确定该用哪个专门技能时使用；本技能判断所处阶段，给出对应方法并路由到精专子技能。不做：直接连接集群或代替人执行部署命令。
author: Captain
version: 0.1.0
display_name: "容器与部署助手"
display_name_en: "Container Deploy Pro"
description_zh: "一个入口覆盖容器与上线全过程：镜像体检与瘦身、compose 与 K8s 清单检查、nginx 反代、TLS 证书、环境变量对齐、密钥自查、迁移锁表、上线前一次性体检与发布后巡检、回滚顺序；按阶段路由到精专子技能。"
description_en: "One entry point from image to rollback: Dockerfile review and slimming, compose and Kubernetes manifest checks, nginx reverse proxy, TLS certificates, env alignment, secret scanning, migration locking, pre-release gate and post-deploy probes, rollback order; routes to focused sub-skills."
tags:
  - "容器部署"
  - "Dockerfile"
  - "Kubernetes"
  - "上线检查"
  - "nginx"
  - "回滚"
  - "证书巡检"
  - "DevOps"
examples_zh:
  - "镜像太大构建还慢，上线前能不能先瘦一遍"
  - "K8s 清单和 compose 都要过一遍，明天灰度发布"
  - "容器起不来一直重启，证书好像也快过期了"
examples_en:
  - "Image is huge and builds slowly, can we slim it before release"
  - "Review both the Kubernetes manifests and compose file, we ship tomorrow"
  - "Container keeps restarting and the cert looks close to expiry"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📦" } }
---

# 容器与部署助手

定位一句话：**上线出事的十有八九不是代码，是镜像、清单、配置和证书。**
这是「研发效能」系列里容器与发布场景的入口。何时用：写完 Dockerfile、改完编排清单、上线前想过一遍、发布后要验、或者要回滚时，先在下表对号入座。表里的子技能装了就直接调用（自带脚本、纯标准库，一条 `python3` 命令出结果，可当 CI 门禁），没装就按本页的精简方法做，并告诉用户可以在 SkillHub 搜对应 slug 安装。

## 上线四段（顺序不要换）

```
1 构建：多阶段 + 固定基础镜像版本 + 非 root + .dockerignore，先让镜像瘦下来
2 编排：compose 与 K8s 清单过安全基线、资源上限、探针、重启策略
3 接入：nginx 反代与 TLS 证书、环境变量三方对齐、密钥不进仓库
4 发布：上线体检出三态结论 → 发布 → 健康巡检 → 回滚预案随时能按
```

## 意图 → 方法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| Dockerfile 写得对不对、镜像太大 | 最佳实践与安全规则分级体检附改法（多阶段、固定版本、非 root、层合并、缓存顺序） | Dockerfile 体检 `dockerfile-check` |
| docker-compose 上线前过一遍 | 查特权、host 命名空间、docker.sock、明文密钥、数据库端口暴露、镜像未固定、缺健康检查与资源上限 | Compose 配置体检 `docker-compose-check` |
| K8s 清单能不能上生产 | 安全基线（特权、root、hostNetwork、hostPath、明文 Secret）、资源限制、探针、副本、selector 匹配、废弃 API | K8s 清单体检 `k8s-manifest-check` |
| nginx 反向代理、网关配置 | 按继承语义查 TLS 协议、安全响应头、代理超时、gzip、http2、server_name 冲突、root 与 alias 误用、列目录 | nginx 配置体检 `nginx-config-check` |
| 证书快到期、HTTPS 报错 | 批量并发查剩余天数、颁发者、SAN 是否覆盖主机名、协议版本、链是否完整，双阈值可接定时巡检 | TLS 证书巡检 `tls-cert-check` |
| 环境变量对不齐、少配了 key | 让示例文件、各环境配置与代码实际读取三方对齐，找缺失、未登记、僵尸项与示例里的真密钥 | .env 一致性检查 `env-sync-check` |
| 多环境配置漂移、上线前核对 | 多份配置拉平成键路径对比，分出只有一方有、类型不同、值不同，密钥自动脱敏 | 多环境配置对比 `config-env-diff` |
| 仓库里有没有硬编码密钥 | 工作树加最近提交历史一起扫，命中值脱敏后分级并给轮换改法 | 仓库泄密自查 `secrets-scan` |
| 这次迁移会不会锁表 | 查 DDL 锁表风险、不可回滚操作、与代码发布的先后顺序 | SQL 迁移检查 `sql-migration-check` |
| 上线前想一次性全过一遍 | 镜像、K8s 清单、SQL 迁移、OpenAPI 兼容、配置五项一起跑，汇总成三态门禁结论 | 上线体检 `release-readiness-check` |
| 发布完确认服务真起来了 | 并发巡检状态码、耗时、关键字与证书剩余天数，异常退出码可直接接流水线 | HTTP 健康巡检 `http-health-check` |
| 要回滚 | 先划回滚边界：镜像与配置通常可回，数据库迁移与已下发的开关往往不可回；按镜像版本 → 配置 → 开关倒序回，回完仍跑一遍健康巡检；结构变更走扩展再收缩而不是硬回滚 | 下线与迁移 `deprecation-migration-zh` |

## 输出契约

1. **分级而不是一锅端**：问题分「拦上线 / 建议修 / 可以先记着」，每条附具体改法与所在文件行号。
2. **不替人拍板能不能上线**：只给三态结论（不建议上线 / 无法判断 / 未见阻塞项）与证据，决定权在人。
3. **回滚预案与发布计划同时产出**：没有回滚路径的变更要显式标出来，并写清为什么不可回。
4. **密钥只报位置不报值**：命中的凭据一律脱敏成前后各四位，并给轮换步骤。

## 典型组合流程

- **新服务第一次上线**：Dockerfile 体检把镜像瘦下来 → Compose 或 K8s 清单体检过安全基线 → .env 一致性检查补齐变量 → 仓库泄密自查确认没有硬编码密钥 → nginx 配置体检接好反代 → TLS 证书巡检确认证书覆盖域名 → 上线体检出门禁结论。
- **每次迭代发版**：多环境配置对比看配置漂移 → SQL 迁移检查确认不锁表且顺序正确 → 上线体检一次性跑五项 → 发布 → HTTP 健康巡检确认恢复 → 把回滚顺序写进发布单。
- **容器一直重启排查**：K8s 清单体检看探针阈值、资源上限与启动依赖是不是配错 → .env 一致性检查看是不是少了变量导致启动即退出 → TLS 证书巡检与 nginx 配置体检排除接入层问题。

## 不做什么

- 不直接连接集群、不代替人执行构建与部署命令；只做静态体检、给命令与改法，由人来执行。
- 不给「可以上线」的最终结论，也不在没有回滚路径时假装有。
- 不接触任何未脱敏的内部系统信息；示例一律用 example.com 与 GitHub / GitLab / Jira。
- 不做容量规划、成本优化与集群运维，那超出本技能范围。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
