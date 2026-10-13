---
name: test-coverage-gap
description: "测试覆盖缺口、哪些代码没有测试、补测试优先级、覆盖率最低的文件、coverage.xml 与 lcov 分析、没有对应测试文件的源码、测试债盘点、提测前看覆盖。当用户要盘点补测试优先级或核查覆盖率路径时使用。附标准库脚本，按模块路径生成测试命名线索，解析 Cobertura / lcov，输出精确、唯一后缀、歧义和未匹配候选；同名测试不证明执行覆盖。支持显式路径前缀映射、JSON 与 Markdown 报告，严格门禁拦截零覆盖及报告中的未知或歧义，非法或冲突报告报错。"
author: Captain
version: 0.1.1
homepage: https://github.com/po-et/workbuddy-skills
license: "CC-BY-4.0 AND MIT"
display_name: "测试覆盖缺口"
display_name_en: "Test Coverage Gap"
tags:
  - "覆盖率"
  - "coverage"
  - "测试债"
  - "门禁"
  - "lcov"
  - "Cobertura"
  - "路径映射"
  - "JSON"
description_zh: "按模块路径盘点测试命名线索与覆盖率证据；保留歧义候选、未知值和补测试优先级，显式映射路径后生成 JSON / Markdown 交付。纯 Python 标准库，可作保守门禁。"
description_en: "Separate conventional test-file signals from execution coverage. Resolve paths conservatively, retain ambiguous candidates and unknown values, and produce JSON / Markdown reports with a strict evidence gate; Python stdlib only."
examples_zh:
  - "测试覆盖缺口看一下，哪些文件还没有测试"
  - "最近改的代码有没有测试，先补哪些"
  - "解析一下 coverage.xml，帮我排个补测试的优先级"
examples_en:
  - "Which source files have no corresponding test file"
  - "Do the files changed recently have any tests"
  - "Parse coverage.xml and rank what to test first"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# 测试覆盖缺口

先回答「哪些文件缺少明确的测试线索」「覆盖率报告有没有可靠映射到它们」，再给出补测试顺序。同名测试文件是命名线索；输入报告中的覆盖率是一次运行记录。两者都不证明当前版本已执行测试或测试质量。

## 快速使用

在项目根目录运行；脚本路径用本技能实际安装目录替换：

```bash
python3 /path/to/test-coverage-gap/scripts/test_coverage_gap.py src tests --days 0 --json
python3 /path/to/test-coverage-gap/scripts/test_coverage_gap.py . --coverage coverage.xml --output coverage-gaps.md
python3 /path/to/test-coverage-gap/scripts/test_coverage_gap.py . --coverage coverage/lcov.info --strict --json
python3 /path/to/test-coverage-gap/scripts/test_coverage_gap.py src web/src --days 14 --min-cov 70 --min-lines 20 --exclude scripts
```

Python 3.9+、纯标准库、无网络访问。只有 `--days` 大于 0 才调用只读 `git log`；`GIT_BIN` 可覆盖 git 路径。不在 Git 仓库或没有 git 时仍可输出扫描结果，并记录改动热度不可用。

## 执行流程

1. 确认源码目录、测试目录和报告所属的代码版本。传入的扫描目录应包含测试目录；缺少它会减少测试命名线索。
2. 先用 `--days 0 --json` 看 `source_findings`。模块路径参与测试映射：`moduleA/tests/test_user.py` 不会遮住 `moduleB/src/user.py`。多个源码争用一份测试时标记 `ambiguous`。
3. 加 `--coverage` 查看覆盖率匹配候选。先精确匹配规范化路径，再找最长后缀的唯一候选；并列或同一报告条目被多个源码争用时保留歧义，覆盖率为 `null`。
4. 路径前缀不一致时，用显式映射建立精确证据。不要凭同名文件猜选一个条目：

```bash
python3 /path/to/test-coverage-gap/scripts/test_coverage_gap.py src tests \
  --coverage lcov.info --coverage-map '/build/project=.' \
  --days 0 --strict --json --output coverage-gaps.md
```

例如报告 `/build/project/src/user.py` → 源码 `src/user.py`。`--coverage-map` 格式为 `报告前缀=源码前缀`，可重复；最长前缀优先。`.` 表示相对根目录。路径映射冲突属于输入错误。

5. 根据缺口安排测试，核对业务关键性与未执行分支；生成新的覆盖率报告后重跑。报告 0% 只说明该次报告未记录命中，不能据此自动删源码。

## 分级与门禁

| 条件 | 输出 | 门禁行为 |
|---|---|---|
| 最近 N 天有改动、缺少明确测试命名线索，且无正覆盖率证据 | `high` | `--strict` 返回 1 |
| 报告可靠匹配且覆盖率为 0% | `zero_coverage` / `high` | 有同名测试也返回 1 |
| 无明确测试命名线索，未取得近期变更记录 | `warn` | 不单独阻断 |
| 报告正覆盖率低于 `--min-cov` | `low_coverage` / `warn` | 仍是提示，不是阈值阻断 |
| 无明确同名测试线索，但报告有正覆盖率 | `info` | 保留报告证据 |
| 已提供报告，但文件没有可靠覆盖率、路径并列或数据缺失 | `coverage_unknown`，值为 `null` | `--strict` 返回 1；不冒充 0% |
| 报告损坏、数值非法、重复条目冲突、映射冲突 | 标准错误说明原因 | 返回 2，不能当成功报告 |

没有传报告时覆盖率保持未知，但不凭缺少报告阻断。退出码 0 表示该次配置的门禁通过，1 表示严格门禁未通过，2 表示输入或输出错误。`--strict` 不会执行项目测试；是否覆盖关键行为仍需独立验证。

## 交付与验收

- `--json` 保留 `gaps`、`zero_coverage`、`low_coverage`、`summary` 等原字段，并增加 `source_findings`、`coverage_unknown`、`gate` 和 `notes`。数组确定性排序，候选路径可核查。
- `--output report.md` 保存完整 Markdown 报告。屏幕文本受 `--limit` 限制，JSON 和报告文件不截断。输出路径不能覆盖扫描到的源码、测试或覆盖率输入。
- `total_coverage` 是整份报告的可计算行覆盖率，可能包含扫描范围之外的文件。只有 `line-rate` 摘要而没有行数量时不虚构总行数，保留 `null`。
- 字段与解析规则参见 [输出证据与路径规则](references/evidence-contract.md)。

附带一个合成样例。它不代表真实业务或真实用户测试，测试文件只用于演示命名：

```bash
cd /path/to/test-coverage-gap/examples/demo-project
python3 ../../scripts/test_coverage_gap.py . --days 0 --min-lines 1 \
  --coverage lcov-ambiguous.txt --strict --json --output ambiguous.md
# 预期退出 1：user.py 的报告候选并列，moduleB 不会获得 moduleA 的测试线索
python3 ../../scripts/test_coverage_gap.py . --days 0 --min-lines 1 \
  --coverage lcov-mapped.txt --coverage-map '/build/project=.' --strict --json
# 预期退出 1：路径精确对应后，moduleB 仍有报告 0% 需处理
```

验收要看：`moduleB/src/user.py` 仍在命名缺口里；歧义报告中的覆盖率保持 `null`，而不是拿第一项 100%；映射后的 moduleA 是 100%、moduleB 是 0%；输入文件内容保持不变。

## 边界

- 只按文件名与常见目录层推断测试线索，不解析 import、调用图或运行测试。结构层 `src/source/sources/lib/main` 和测试目录会被折叠，模块与包名保留；特殊布局请检查候选，用执行报告补充证据。
- `exact` 最可靠；`suffix_unique` 只表示此次扫描中的候选唯一，仍可能匹配到报告中另一个项目的同名文件。需要强归属时用显式映射并确认 `exact`。
- 默认跳过依赖、构建与生成目录及小于 10 行的命名缺口；`--min-lines` 只影响命名缺口清单，不把覆盖率未知或零覆盖过滤掉。
- 支持 Cobertura XML 与 lcov 行覆盖率，不支持原生 JaCoCo XML、分支覆盖率或覆盖率合并。冲突的重复行/摘要会被拒绝，请先在覆盖率工具中合并。
- XML 使用标准库字符串解析，不请求外部 DTD；拒绝内部 DTD 子集、实体声明和含空字节的编码。只处理用户提供的本地报告，不访问报告中的外部链接。
- 报告路径与测试文件名可能含项目细节；公开分享前检查范围。报告新鲜度与运行范围由调用者确认，脚本不会推断它们。
