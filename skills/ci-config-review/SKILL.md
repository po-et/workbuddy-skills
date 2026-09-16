---
name: ci-config-review
description: CI 配置审查、GitHub Actions 安全检查、GitLab CI 流水线审查、workflow 文件 review。当用户说「帮我看看这个 workflow 有没有安全问题」「GitHub Actions 配置审查」「流水线为什么跑那么久」「action 要不要固定 SHA」「pull_request_target 安全吗」「CI 里 secret 会不会泄露」「.gitlab-ci.yml 有什么坑」「CI 最佳实践检查」时使用。脚本离线扫描 .github/workflows/*.yml 与 .gitlab-ci.yml：第三方 action 未固定 commit SHA、pull_request_target 检出 PR 代码、脚本注入（把 github.event 文本直接放进命令）、未声明 permissions、secret 打印、curl | sh、缺 timeout / concurrency、continue-on-error 掩盖失败、镜像未固定版本。基于文本模式，结论为"疑似"需人工确认。
author: Captain
version: 0.1.0
display_name: "CI 配置审查"
display_name_en: "CI Config Review"
description_zh: "离线扫描 GitHub Actions / GitLab CI 配置的安全与可靠性问题：未固定 SHA、pull_request_target、脚本注入、权限、secret 泄露、超时与并发，按 high/medium/low 分级。"
description_en: "Offline scan of GitHub Actions / GitLab CI configs for security and reliability issues: unpinned actions, pull_request_target, script injection, permissions, secret leaks, timeouts and concurrency, graded high/medium/low."
examples_zh:
  - "审查一下 .github/workflows 里的安全问题"
  - "这个 workflow 用了 pull_request_target，有风险吗"
  - "我们的 GitLab CI 配置有哪些可靠性隐患"
examples_en:
  - "Audit the security of .github/workflows"
  - "This workflow uses pull_request_target, is it risky?"
  - "What reliability issues are in our GitLab CI config"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# CI 配置审查

CI 配置是仓库里权限最高、被 review 最少的代码。本技能用一份固定清单把最常见的坑先扫一遍，再由你判断。

## 核心原则

1. **供应链优先。** 第三方 action 用 tag 引用等于把仓库 secrets 交给对方账号的未来。
2. **不信任事件里的文本。** PR 标题、issue 正文、分支名都是外部输入，进 shell 前先进 `env`。
3. **最小权限、有超时、可取消。** 这三样缺一个都会在某个周五晚上变成事故。
4. **结论是"疑似"。** 脚本不做完整 YAML 解析，每条都要看上下文。

## 执行流程

### 第 1 步：扫描

```bash
python3 {baseDir}/scripts/ci_lint.py --path <仓库根目录> --md out/ci.md --out out/ci.json
```

检查项（GitHub Actions）：
- **high**：`pull_request_target` + 检出 PR head；第三方 action 未固定 40 位 SHA；`${{ github.event.*.title/body/… }}` 或 `github.head_ref` 直接进表达式/命令。
- **medium**：未声明 `permissions`；`echo/printf/cat` 输出 `secrets.*`；`curl … | sh`。
- **low**：官方 action 未固定 SHA；`actions/checkout@v1/v2`；没有 `timeout-minutes`。
- **info**：PR 工作流没有 `concurrency`；`continue-on-error: true`。

GitLab CI：镜像未固定版本、打印 CI 凭证、`curl | sh`、缺 `timeout`、缺 `interruptible`。

### 第 2 步：逐条判断（这一步由你做）

- 对每条 high：给出修法（SHA 固定写法 `uses: owner/action@<sha> # v1.2.3`；注入改为 `env: TITLE: ${{ github.event.pull_request.title }}` 后 `"$TITLE"`；`pull_request_target` 改为 `pull_request` 或拆成两段工作流）。
- 对 medium/low：说明影响与代价，让用户决定是否现在修。
- 检查脚本没覆盖的：自托管 runner 是否隔离、OIDC 是否替代长期密钥、缓存 key 是否包含锁文件哈希、矩阵是否过大。

### 第 3 步：交付

按文件分组的清单 + 一份"可直接粘贴"的修复 diff（至少覆盖全部 high）。

## 输出契约

```
# CI 配置审查
- 文件数 / 发现数（high/medium）
## <文件>
- **级别** L行：问题 → 修法
## 未覆盖项（需人工）
```

## 常见问题

**官方 action 也要固定 SHA 吗？** 建议固定，Dependabot/Renovate 可以自动更新；至少固定到主版本。
**固定 SHA 后怎么知道版本？** 行尾注释 `# v4.1.1`，Renovate 能识别。
**内部 GitLab？** 同样的原则；镜像来自内部仓库时仍要固定 digest。
