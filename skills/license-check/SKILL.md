---
name: license-check
description: 开源协议合规检查、依赖许可证审计、License 风险扫描。当用户问「项目依赖里有没有 GPL / AGPL」「我们能不能商用这些库」「上线前查一下开源协议合规」「哪些依赖是 copyleft」「SSPL / BUSL 这种能用吗」「生成第三方许可证清单 / NOTICE」「依赖的 license 是什么」时使用。脚本不联网、零依赖：读 package-lock.json / node_modules、Python site-packages 的 dist-info、go.mod 模块缓存，把每个依赖的许可证按 restricted / strong-copyleft / weak-copyleft / unknown / permissive 分级并列表；只给清单与分级，不给法律结论。
author: Captain
version: 0.1.0
display_name: "开源协议合规检查"
display_name_en: "License Compliance Check"
description_zh: "离线读取 npm / Python / Go 依赖的许可证，按 restricted、强/弱 copyleft、未声明、宽松五级分类列表，输出第三方许可证清单草稿。"
description_en: "Offline scan of npm / Python / Go dependency licenses, classified into restricted, strong/weak copyleft, unknown and permissive, with a draft third-party notice."
examples_zh:
  - "查一下这个项目依赖有没有 GPL 或 AGPL 的库"
  - "生成第三方开源许可证清单"
  - "我们做 SaaS，依赖里哪些协议要注意"
examples_en:
  - "Check whether any dependency is GPL or AGPL"
  - "Generate a third-party license notice"
  - "We ship SaaS, which dependency licenses need attention"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "⚖️" } }
---

# 开源协议合规检查

把项目依赖的许可证**列清楚、分好级**，让人能在十分钟内决定"能不能用、怎么用"。本技能提供清单与分级，**不提供法律意见**。

## 核心原则

1. **离线、只读。** 不联网、不改任何文件。
2. **分级只看许可证文本关键字。** 判断标准公开在脚本里，可以核对。
3. **风险取决于用法。** 同一个 GPL 库，作为独立进程调用与静态链接分发，结论不同；AGPL 对 SaaS 有特殊要求。评审时必须问清用法。
4. **unknown 必须人工确认。** 未声明 ≠ 可以随便用。

## 执行流程

### 第 1 步：扫描

```bash
python3 {baseDir}/scripts/license_check.py --path <项目根目录> --md out/licenses.md --out out/licenses.json
```

- npm：优先读 `package-lock.json`（v2/v3 带 license 字段），再补 `node_modules/**/package.json`。
- Python：自动找 `venv/.venv` 的 site-packages；或 `--python-site <路径>`；或 `--use-current-python` 用当前解释器已安装的包。
- Go：`go.mod` 列出的模块，从 `$GOPATH/pkg/mod` 的 LICENSE 文件头识别（需先 `go mod download`）。
- `--fail-on strong-copyleft` 可用于 CI。

### 第 2 步：解读（这一步由你做）

先问清三件事：项目怎么分发（内部使用 / 二进制分发 / SaaS / 开源）、依赖怎么用（进程外调用 / 动态链接 / 静态链接或打包进产物 / 修改过源码）、项目自身的许可证。
然后逐级说明：
- **restricted**（SSPL、BUSL、非商业、未授权）：默认不能用于商业分发，逐个核对官方条款。
- **strong-copyleft**（GPL、AGPL）：打包分发或（AGPL）网络提供服务时会传染；只在进程外调用通常可控。
- **weak-copyleft**（LGPL、MPL、EPL）：修改了库本身要开源修改部分；动态链接/不改源码通常可用。
- **unknown**：打开包主页确认；npm 的 `SEE LICENSE IN` 要看仓库里的文件。
- **permissive**：保留版权声明与许可证文本即可——这就是 NOTICE 清单的用途。

### 第 3 步：交付

分级表 + 三段：必须处理的（替换或获得授权）、需要注意用法的、可以放心用的；再附一份第三方许可证清单草稿（依赖名 / 版本 / 许可证），供 NOTICE 文件使用。

## 输出契约

```
# 开源协议合规检查
- 依赖总数与各级计数
| 风险 | 依赖 | 版本 | 许可证 |   （只列非宽松）
## 结论：必须处理 / 注意用法 / 可放心用
## 第三方许可证清单（NOTICE 草稿）
## 说明与局限
```

## 常见问题

**Maven / Gradle？** 暂不解析；用 `mvn license:add-third-party` 或 Gradle license 插件导出后交给评审步骤。
**双许可证（"MIT OR Apache-2.0"）？** 按对你最有利的一项选择，并在清单里写明选择。
**依赖的依赖？** npm 锁文件与 site-packages 本来就包含传递依赖；go.mod 只含直接依赖，`go list -m all` 可补全。
