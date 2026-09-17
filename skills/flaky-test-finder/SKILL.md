---
name: flaky-test-finder
description: flaky 测试识别、不稳定测试、时而通过时而失败的用例、CI 随机挂、重跑就过、JUnit XML 报告分析、测试耗时波动、区分真失败与偶发失败。当用户说「CI 老是随机失败」「哪些测试是 flaky 的」「分析一下最近几次的测试报告」「这个用例重跑就过是怎么回事」「测试套件里哪些用例最不稳定」时使用。附纯标准库脚本 scripts/flaky_finder.py：读取多次运行的 JUnit XML（pytest / Jest / Go / Maven / Gradle 等都能导出），按用例汇总通过/失败序列，输出不稳定用例（失败率、✓✗ 序列、最近状态、常见失败信息、均耗时）、稳定失败用例（真坏了）、耗时波动大的用例；支持 --min-runs、--top、--json。
author: Captain
version: 0.1.0
display_name: "flaky 测试识别"
display_name_en: "Flaky Test Finder"
description_zh: "汇总多次运行的 JUnit XML 报告，找出时而通过时而失败的用例并给出失败率、失败序列与常见报错，同时把「每次都失败」和「耗时波动大」的用例分开列出；纯 Python 标准库。"
description_en: "Aggregate JUnit XML reports from multiple runs to find tests that alternate between pass and fail, with fail rate, pass/fail pattern and common error messages, separating always-failing and duration-unstable tests; pure Python stdlib."
examples_zh:
  - "分析 reports/ 下最近 10 次 CI 的 junit 报告，找出 flaky 用例"
  - "这三次运行的测试报告里哪些用例不稳定"
  - "把 flaky 识别接到 CI，每周输出一份榜单"
examples_en:
  - "Analyze the last 10 CI junit reports under reports/ for flaky tests"
  - "Which tests are unstable across these three runs?"
  - "Hook flaky detection into CI and post a weekly leaderboard"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🎲" } }
---

# flaky 测试识别

把多次运行的测试报告叠在一起看：同一个用例有时过有时挂，就是 flaky；每次都挂是真坏了；耗时忽快忽慢通常在等外部资源。三类分开处理。

## 用法

```bash
# 目录结构：每次运行一个子目录（或一个文件），脚本递归读取所有 *.xml
python3 scripts/flaky_finder.py reports/
python3 scripts/flaky_finder.py run1.xml run2.xml run3.xml
python3 scripts/flaky_finder.py reports/ --min-runs 3 --top 20 --json
```

拿 JUnit XML：pytest `--junitxml=report.xml`；Jest 用 jest-junit；Go 用 go-junit-report；Maven Surefire / Gradle 默认就产出；GitHub Actions / GitLab CI 把每次运行的报告作为构件下载到 `reports/<run-id>/`。

## 输出

- **不稳定用例**：失败率、✓✗ 序列（按运行顺序）、最近状态、平均耗时、最常见的失败信息。
- **稳定失败**：每次都失败——不是 flaky，直接修。
- **耗时波动大**：最快与最慢相差 ≥ 5 倍且最慢 ≥ 1 秒——多半依赖网络、数据库或存在竞争。

## 流程

1. 收集至少 3–5 次运行的报告（越多判定越准），跑脚本。
2. 按失败率从高到低处理不稳定用例；先看「常见信息」：超时/连接类 → 外部依赖或资源竞争；断言随机值 → 时间、随机数、顺序依赖；`already exists` 类 → 共享状态未清理。
3. 止血：把确认为 flaky 的用例移入隔离分组并加有限重试；**修复**：去掉共享状态、mock 外部依赖、固定时间与随机种子、消除用例间顺序依赖。
4. 定期（每周）重跑脚本，把榜单贴到团队频道，跟踪数量下降。

## 边界

- 只读 JUnit XML；其他格式（TAP、JSON）先转换。
- 「一次运行」按一级子目录或文件名区分；同一目录下平铺多份同名报告会被合并成一次，请分目录放。
- 参数化用例名字里带随机值时会被当成不同用例；先规范化名字。
