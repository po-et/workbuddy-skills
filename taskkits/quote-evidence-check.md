# 两份报价：先核对，后比较

本任务包提供一个可离线运行的 Skill、确定性核对脚本、四份合成输入与19项行为测试。Python 3.9+，仅标准库，不调用模型或网络。

在解压后的 `quote-evidence-check/` 目录运行：

```bash
python3 scripts/quote_check.py assets/synthetic-missing.json --json-output missing-report.json --markdown-output missing-report.md
python3 scripts/quote_check.py assets/synthetic-complete.json --json-output complete-report.json --markdown-output complete-report.md
```

第一份输入中 B 服务费未报价，不能比较完整总额；第二份已补齐明确金额，差额 B−A 为 +3000.00 元。所有样例为合成数据，报价税费不是政策计算值。

自己的数据按 `references/schema.md` 整理。没有报价的金额写 `null`，明确为零写 `"0.00"`；数字和条件必须由你核对原文后才能确认。脚本不证明来源真伪，也不自动更新历史确认状态。

默认报告省略原文和车型、付款、范围的自由文本，但仍包含金额和状态；它不是任意数据自动脱敏。明确要带出处时才加 `--include-source`。已有报告默认不覆盖，请使用新文件名。

若要在支持本地 Skill 的客户端使用，将解压后的完整文件夹放到该客户端支持的本地技能目录，或向助手提供 `SKILL.md` 和报价原文。目录配置以你的客户端说明为准，保留已存在的同名资产。

复跑验证：

```bash
python3 -m unittest discover -s tests -p '*_test.py' -v
```

19项行为验证覆盖缺项与明确零、确认和来源、一分钱精度、条件差异、错误格式、导出范围、文件覆盖保护。另一次独立代理用新合成报价完成核对，准确保留缺项及付款差异；这些都不是独立真人采用证明。

本包是“报价显微镜”开发期间产生的独立工具资产。网页仍在开发，本包不代表 WorkBuddy 原生创作、应用上线、已参赛或获奖。

作者与来源：Captain，https://github.com/po-et/workbuddy-skills 。代码 MIT；正文和合成内容 CC BY 4.0，见随包许可。
