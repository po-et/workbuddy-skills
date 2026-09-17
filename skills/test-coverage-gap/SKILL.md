---
name: test-coverage-gap
description: 测试覆盖缺口、哪些代码没有测试、补测试优先级、覆盖率最低的文件、coverage.xml 与 lcov 分析、没有对应测试文件的源码、测试债盘点、提测前看覆盖。当用户说「哪些文件还没有测试」「最近改的代码有没有测试」「覆盖率最低的文件是哪些」「帮我排个补测试的优先级」「解析一下 coverage.xml」时使用。附纯标准库脚本 scripts/test_coverage_gap.py：按 Python、JS/TS、Go、Java 等常见命名约定把源码文件映射到测试文件，列出没有对应测试的源码，并结合 git 最近 N 天的改动次数排优先级（git 路径可用 GIT_BIN 覆盖）；可选解析 Cobertura coverage.xml 或 lcov.info，列出完全未覆盖与行覆盖率最低的文件；支持 --days、--min-cov、--min-lines、--exclude、--json 与 --strict 门禁。
author: Captain
version: 0.1.0
display_name: "测试覆盖缺口"
display_name_en: "Test Coverage Gap"
description_zh: "一条命令回答「该先给哪些文件补测试」：按命名约定找出没有对应测试的源码，用 git 改动热度排序，再叠加 coverage.xml 或 lcov 找出零覆盖与低覆盖文件；纯 Python 标准库，可作提测门禁。"
description_en: "One command to answer which files need tests first: map sources to tests by naming convention, rank them by recent git churn, and overlay coverage.xml or lcov to surface zero-coverage and low-coverage files; pure Python stdlib, usable as a pre-QA gate."
examples_zh:
  - "测试覆盖缺口看一下，哪些文件还没有测试"
  - "最近改的代码有没有测试，先补哪些"
  - "解析一下 coverage.xml，帮我排个补测试的优先级"
examples_en:
  - "Which source files have no corresponding test file"
  - "Do the files changed recently have any tests"
  - "Parse coverage.xml and rank what to test first"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# 测试覆盖缺口

「覆盖率 62%」没法指导工作，「这 8 个最近改过还一行测试都没有的文件」才可以。这个技能把 **有没有测试文件**、**最近改得多不多**、**覆盖率多少** 三个视角叠在一起，直接给出补测试的顺序。

## 用法

```bash
python3 scripts/test_coverage_gap.py                                  # 当前目录，默认看最近 30 天改动
python3 scripts/test_coverage_gap.py src/ web/src --days 14
python3 scripts/test_coverage_gap.py . --coverage coverage.xml        # 叠加 Cobertura 覆盖率
python3 scripts/test_coverage_gap.py . --coverage coverage/lcov.info  # 叠加 lcov 覆盖率
python3 scripts/test_coverage_gap.py . --min-cov 70 --min-lines 20 --exclude scripts
python3 scripts/test_coverage_gap.py . --json --limit 100
python3 scripts/test_coverage_gap.py . --days 7 --strict              # 有 high 则退出码 1
```

git 路径可用环境变量 `GIT_BIN` 覆盖（默认 `git`）；不在 git 仓库里也能跑，只是少了改动热度排序（加 `--days 0` 可显式跳过）。

## 流程

1. 先跑一次带 `--days` 的扫描，**high** 那一组就是本周期该补的：改动频繁 + 没有任何测试。
2. 每个 high 文件先补一条覆盖主路径的用例，不要一上来追求分支全覆盖；有测试文件之后它会自动从 high 里消失。
3. 有覆盖率报告就加 `--coverage`：**覆盖率为 0** 的文件要么是死代码（删掉），要么是完全没测（补上），二选一。
4. 覆盖率低于 `--min-cov` 的文件，重点看没被执行到的异常分支与边界条件——bug 通常藏在那里。
5. 把 `--strict --days 7` 挂到提测或合并流水线上，防止新增代码不带测试。

## 判定与分级

| 级别 | 判定 | 说明 |
|---|---|---|
| high | 最近 N 天改动过、且没有对应测试文件 | 改动热度来自 `git log --since`，按提交次数降序 |
| high | 行覆盖率为 0 | 来自 `--coverage`，一行都没被执行过 |
| warn | 没有对应测试文件（近期没改动） | 存量测试债，按业务重要性排期 |
| warn | 行覆盖率低于 `--min-cov`（默认 50%） | 有测试但覆盖不足 |
| info | 没有同名测试、但覆盖率报告显示被间接覆盖 | 被集成测试或上层用例带到了，风险较低 |

适用的源码到测试映射约定：Python `foo.py` → `test_foo.py` / `foo_test.py`；JS/TS `foo.ts` → `foo.test.ts` / `foo.spec.ts` / `__tests__/foo.ts`；Go `foo.go` → `foo_test.go`；Java `Foo.java` → `FooTest.java` / `FooTests.java` / `TestFoo.java` / `FooIT.java`；此外 Ruby、PHP、C#、Kotlin、Scala 的常见后缀也认。位于 `test/`、`tests/`、`__tests__/`、`spec/`、`e2e/` 等目录下的文件一律视为测试文件。

## 输出

文本模式先给总览（源码数、测试数、无对应测试占比、改动文件数、总行覆盖率），再按 high/warn/info 分组列出 `改动次数 / 行数 / 文件路径`，最后是覆盖率为 0 与覆盖率偏低的两张清单。`--json` 输出 `gaps`、`zero_coverage`、`low_coverage`、`summary` 等字段，可直接喂给看板或在 PR 里生成评论。

## 边界

- 靠**文件名约定**判定，不解析代码。测试写在一个大文件里、或用 `Given_When_Then` 之类的命名，会被误判成「没有测试」——这种项目请以 `--coverage` 的结果为准。
- 反过来，有同名测试文件不代表测得好（可能只有一句 `assert True`）；本技能**不做**测试质量评估。
- 默认跳过 `node_modules`、`vendor`、`dist`、`target`、`migrations`、`generated` 等目录与少于 10 行的文件（`--min-lines` 可调）。
- 只解析 Cobertura 与 lcov 两种格式；JaCoCo 请用 `jacoco:report` 生成 Cobertura 兼容 XML，Go 用 `gocov-xml`，Python 用 `coverage xml`。
- 常见问题：覆盖率文件里的路径和仓库路径前缀不一致时，脚本按路径后缀做最长匹配；如果结果明显对不上，从仓库根目录运行并传相对路径最稳。
