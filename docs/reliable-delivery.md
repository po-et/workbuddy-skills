# 四份有依据的工作产物

用已有技能完成会议待办、日志附件、补测清单和发布前静态检查。四项都在本机运行，不依赖模型 API Key；原始材料、工具检查结果、用户确认和实际业务结果分别记录。

| 今天要交付什么 | 技能 / 已上线版本 | 这次补齐的能力 |
|---|---|---|
| 会议纪要与待办表 | [会议录音整理](https://skillhub.cn/skills/@indiv-captain/meeting-transcript-cleanup) 0.1.2 | 原句与行号核对、Markdown/CSV/JSON；保留条件、取消、冲突和未知负责人 |
| 可供复核的脱敏附件 | [日志与数据脱敏](https://skillhub.cn/skills/@indiv-captain/sensitive-data-mask) 0.1.1 | 输入/输出别名冲突预检、目录保留层级、原子写入、成功/跳过/失败统计 |
| 哪些代码应先补测试 | [测试覆盖缺口](https://skillhub.cn/skills/@indiv-captain/test-coverage-gap) 0.1.1 | 路径映射置信度、同名歧义、显式映射；不能把命名候选当成执行覆盖 |
| 发布前的静态检查证据 | [上线体检](https://skillhub.cn/skills/@indiv-captain/release-readiness-check) 0.1.3 | 输入与检查器哈希、跳过理由、缺证据门禁；检查结果与上线批准分开 |

## 安装

```bash
skillhub install meeting-transcript-cleanup --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
skillhub install sensitive-data-mask --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
skillhub install test-coverage-gap --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
skillhub install release-readiness-check --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
```

目录依据 [SkillHub 官方安装指引](https://skillhub.cn/install/skillhub.md)。核对作者和实际版本；已有本地修改先保留，按官方说明重启 WorkBuddy，再显式指定技能与材料路径。具体依赖和命令以各技能为准；上线体检中的 YAML OpenAPI 解析可选依赖 PyYAML，缺失会报告证据不足。

## 可以直接使用的任务

> 使用“会议录音整理”处理我提供的转写稿。生成纪要、待办 CSV 和 JSON，每项引用原句与行号。建议、条件和取消不能直接当成确认承诺；没有负责人或会议日期就保留待确认。只生成文件，不发送。

> 使用“日志与数据脱敏”处理这个目录，输出到新的独立目录，保留原件和子目录层级。给我成功、跳过、失败与命中统计；不要把未命中等同于完全匿名化。

> 使用“测试覆盖缺口”分析这个多模块仓库与覆盖率报告。列出确定映射、候选与歧义；遇到同名文件不要随意配对。输出补测清单，说明数据未知的地方，不运行项目代码。

> 使用“上线体检”做静态检查。报告输入与检查器哈希，跳过项写清理由，缺证据保留未知。告诉我检查了哪些规则、发现什么，不把静态结果写成生产发布批准。

## 这轮为什么选它们

本地合成样例复现了两处可检查的缺陷：旧脱敏版本在同目录 `--out-dir` 配合 `--force` 时可能截空原件；旧覆盖率匹配在最长后缀平局时取第一个文件，可能把另一模块的覆盖率套过来。修复分别以原件哈希不变和歧义不冒充覆盖证据验收。

会议整理新增的是产物与引用验证，判断摘要是否保留原意仍需回到原文；发布体检只代表本轮静态规则，不涵盖运行时、业务验收或发布授权。合成样例、维护者运行和本地评分都不代表真实用户采用。

完成一次真实任务后，可用[反馈入口](https://github.com/po-et/workbuddy-skills/issues/new?template=skill-feedback.md)记录版本、输入类型、实际产物、失败步骤与是否再次使用。不要上传敏感原件。发布与读回状态见[本轮验收记录](metrics/delivery-verified-2026-10-13.json)。
