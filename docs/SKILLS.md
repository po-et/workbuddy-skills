# 技能索引（线上 180 个）

生成日期：2026-09-24。依据两份 ground truth：一，[`docs/metrics/status-ns-2026-09-23.json`](metrics/status-ns-2026-09-23.json) 里 `"mine": true` 的 168 行（2026-09-23 前的线上清单）；二，2026-09-24 新验证上线且排名第一的 12 个 slug，来自 [`rename-readout-wave4a-2026-09-24.json`](metrics/rename-readout-wave4a-2026-09-24.json)、[`rename-readout-wave4b-2026-09-24.json`](metrics/rename-readout-wave4b-2026-09-24.json)、[`rename-readout-wave4c-2026-09-24.json`](metrics/rename-readout-wave4c-2026-09-24.json) 三份文件的 `slug` 字段。

分组与 [README](../README.md)「按场景找技能」一致：日常场景 → 开发者与运维 → 工程实践复刻系列。README 只完整列出日常场景，这里是全部 180 个。

**读表说明**

- **中文名**：源 `SKILL.md` 里的 `display_name`，也就是 SkillHub 上的展示名；链接指向仓库里的源目录。
- **一句话**：由源 `SKILL.md` 的 `description_zh` 缩写而来。
- **slug**：SkillHub 上的 slug。目录名到 slug 的映射在 `tools/skillhub_prep.py` 的 `SLUGS` 里，没列进去的目录，slug 就是目录名。技能页地址形如 `https://skillhub.cn/skills/indiv-captain/<slug>`。
- **安装**：`skillhub install <slug> --namespace indiv-captain`。`code-review-zh`、`pr-description`、`secrets-scan`、`skillhub-publish-helper` 这几个 slug 和其他作者的技能同名，不带 `--namespace` 可能装到别人的那个。
- 日常场景 65 个里，除公文写作、PPT汇报演示、简历优化助手、职场防骗、理财入门、保单解读、个税申报、CSV 数据画像这 8 个，46 个是 2026-09-23 新上线的（名单来自 `docs/metrics/rename-baseline-wave*-2026-09-23.json`），另有 11 个是 2026-09-24 新上线的（名单来自 `docs/metrics/rename-readout-wave4a/b/c-2026-09-24.json`，含新分组「让 AI 助手更好用」的 4 个）。
- 仓库里另有 19 个技能目录不在这份线上清单里，本索引不收录。

| 部分 | 分组 | 个数 |
|---|---|---|
| [日常场景](#日常场景) | [职场写作与沟通](#职场写作与沟通)、[学习与考试](#学习与考试)、[家庭与生活](#家庭与生活)、[数据与办公自动化](#数据与办公自动化)、[让 AI 助手更好用](#让-ai-助手更好用) | 65 |
| [开发者与运维](#开发者与运维) | [研发总入口与方案评审](#研发总入口与方案评审)、[上线与发布检查](#上线与发布检查)、[线上排查与可观测](#线上排查与可观测)、[代码与仓库治理](#代码与仓库治理)、[接口与契约](#接口与契约)、[数据与文本处理](#数据与文本处理)、[Agent 与技能开发](#agent-与技能开发) | 56 |
| [工程实践复刻系列](#工程实践复刻系列) | [需求与方案](#需求与方案)、[文档研究与学习](#文档研究与学习)、[计划与执行](#计划与执行)、[测试调试与验证](#测试调试与验证)、[代码设计与评审](#代码设计与评审)、[Git 工作流](#git-工作流)、[上线运维与安全](#上线运维与安全)、[Agent 与上下文工程](#agent-与上下文工程) | 59 |
| 合计 | | 180 |

## 日常场景

65 个，普通人日常会碰到的事：职场、学习、家庭生活、数据与办公。

### 职场写作与沟通

25 个。公文、汇报、邮件、检讨与请假；求职、加薪与离职；招聘、入职与带人；会议、调研与各类文案；文风改写去AI味。

| 中文名 | 一句话 | slug |
|---|---|---|
| [公文写作](../skills/gov-doc-expert/) | 通知、请示、报告、纪要、述职等公文：选文种、定格式、素材加工成稿 | `gov-doc-expert` |
| [PPT汇报演示](../skills/presentation-expert/) | 整场汇报：先定受众要做的决定，搭故事线、选图表、写讲稿 | `presentation-expert` |
| [英文邮件](../skills/english-email/) | 商务英文邮件：七种意图的结构与句式、三档语气，附中式英语自查 | `english-email` |
| [检讨书](../skills/reflection-letter/) | 检讨书与情况说明：按事实、责任、影响、整改四层写，附三套模板 | `reflection-letter` |
| [请假条](../skills/leave-request-note/) | 请假条：学校、公司两套填空格式，各类假别的写法差异与常附材料 | `leave-request-note` |
| [简历优化助手](../skills/resume-job-expert/) | 整条求职链路：按 JD 改简历、投递、各轮面试、offer 比较与谈薪 | `resume-job-expert` |
| [职场防骗](../skills/workplace-antiscam-expert/) | 识别求职与职场骗局：招聘收费、培训贷、刷单、冒充领导转账等 | `workplace-antiscam-expert` |
| [加薪申请](../skills/salary-raise-request/) | 准备加薪沟通：盘点可举证的成果、选时机、三段式谈，附申请模板 | `salary-raise-request` |
| [离职谈话](../skills/resignation-conversation/) | 离职谈话：员工怎么提、被挽留怎么回；管理者怎么谈、交接怎么排 | `resignation-conversation` |
| [招聘 JD](../skills/job-description-writer/) | 写招聘 JD：三段式结构、写清薪资区间，排查歧视性表述，附三份模板 | `job-description-writer` |
| [入职指南](../skills/onboarding-guide/) | 给新同事写入职指南：按首日、首周、首月列清单，含导师机制与模板 | `onboarding-guide` |
| [新人带教](../skills/new-hire-mentoring/) | 带教新同事：30/60/90 天目标、每周一对一、由易到难排任务、给反馈 | `new-hire-mentoring` |
| [KPI 制定](../skills/kpi-design/) | 制定团队或岗位 KPI：从上级目标拆指标，过 SMART，定权重与口径 | `kpi-design` |
| [团建方案](../skills/team-building-plan/) | 团建方案：先定目的，按预算与人数选形式，附三份模板与避雷清单 | `team-building-plan` |
| [会议安排](../skills/meeting-arrangement/) | 安排会议：先判断要不要开，再定目标、参会人与议程，附议程模板 | `meeting-arrangement` |
| [会议录音整理](../skills/meeting-transcript-cleanup/) | 会议转写稿整理成纪要：按议题重组，抽出决议、待办与负责人 | `meeting-transcript-cleanup` |
| [长文总结](../skills/long-doc-summary/) | 长文总结：按读者与用途出 100/300/1000 字三版，关键数字标出处 | `long-doc-summary` |
| [访谈提纲](../skills/interview-outline/) | 用户与专家访谈提纲：主线只问过去的具体行为，附追问句式与记录模板 | `interview-outline` |
| [问卷设计](../skills/questionnaire-design/) | 问卷设计：从调研目标推出题目，选题型、排题序，排查诱导与双重提问 | `questionnaire-design` |
| [主持词](../skills/event-host-script/) | 年会、婚礼、发布会等六类活动主持词：开场、串场、收尾与冷场话术 | `event-host-script` |
| [广播稿](../skills/radio-script/) | 校园、社区、企业广播稿：开场与串联词，书面稿改口语，附填空模板 | `radio-script` |
| [上新文案](../skills/new-product-copy/) | 新品上市文案：参数转卖点，改写成详情页、推文与短视频口播脚本 | `new-product-copy` |
| [UI 文案](../skills/ui-microcopy/) | 界面文案：按钮、空状态、错误提示、确认弹窗等的模板与中英对照 | `ui-microcopy` |
| [图片描述](../skills/image-alt-description/) | 给图片写描述：无障碍 alt 文本、商品图、社媒配文、图表文字化 | `image-alt-description` |
| [降AI味](../skills/reduce-ai-tone/) | 12 条清单认出中文 AI 腔，按六步改写，附脚本统计套话与句长 | `reduce-ai-tone` |

### 学习与考试

11 个。论文与学生写作、演讲与辩论、单词与日语、数学题、编程入门、驾考，以及给家长的孩子学习计划。

| 中文名 | 一句话 | slug |
|---|---|---|
| [开题报告](../skills/thesis-opening-report/) | 开题报告六部分的填空模板与示例，附导师常打回的 8 种情况与改法 | `thesis-opening-report` |
| [观后感](../skills/after-viewing-essay/) | 观后感：从打动你的一个细节写起、不复述剧情，附学生版与成人版模板 | `after-viewing-essay` |
| [辩论稿](../skills/debate-speech/) | 辩论赛发言稿：一辩立论、攻辩问题链、自由辩分工、四辩结辩 | `debate-speech` |
| [毕业致辞](../skills/graduation-speech/) | 毕业致辞：学生、教师、家长三种身份，用故事、共同记忆与期许搭全篇 | `graduation-speech` |
| [背单词](../skills/vocab-memorization-plan/) | 背单词计划：按目标和每天可用时间算新词量，按间隔复习排期 | `vocab-memorization-plan` |
| [日语学习](../skills/japanese-learning-plan/) | 日语零基础到 N4/N3：首周拿下假名，沿语法主线推进，附两版日程 | `japanese-learning-plan` |
| [数学题](../skills/math-problem-tutor/) | 中小学数学题讲解：列已知与所求、分步推导、代回验算，不代做作业 | `math-problem-tutor` |
| [编程入门](../skills/coding-for-beginners/) | 零基础编程入门：按目标选语言，前 30 天每日任务与每周一个小项目 | `coding-for-beginners` |
| [驾照考试](../skills/driving-test-prep/) | 驾照四个科目的备考方法与考前一周计划，只教方法、不给题目答案 | `driving-test-prep` |
| [阅读计划](../skills/kids-reading-plan/) | 3–12 岁分三档的阅读计划：每日时长、共读比例、选书标准、记录表 | `kids-reading-plan` |
| [儿童编程](../skills/kids-coding/) | 6–12 岁儿童编程：图形化还是 Python 起步，8 周计划，家长怎么陪 | `kids-coding` |

### 家庭与生活

13 个。理财、保险与个税；租房、买车与购物；送礼与生日；孩子的屏幕时间、养狗、跑步与睡眠；晨间待办简报。

| 中文名 | 一句话 | slug |
|---|---|---|
| [理财入门](../skills/financial-literacy-expert/) | 看懂年化、复利、费率与产品怎么赚怎么亏，识别保本稳赚话术 | `financial-literacy-expert` |
| [保单解读](../skills/insurance-policy-expert/) | 读懂手上的保单：免责条款、健康告知、理赔与拒赔、续保与退保 | `insurance-policy-expert` |
| [个税申报](../skills/tax-filing-expert/) | 个税年度汇算：办不办、专项附加扣除、年终奖计税、退税被驳回 | `tax-filing-expert` |
| [租房攻略](../skills/renting-guide/) | 租房全流程清单：定预算、看房检查、签约核对、入住交接、退租拿押金 | `renting-guide` |
| [买车](../skills/car-buying-checklist/) | 买车决策清单：拆预算、定新车二手与油电，附试驾与合同交付核对项 | `car-buying-checklist` |
| [购物清单](../skills/shopping-list-planner/) | 按场景生成可勾选的分类购物清单：按动线排序、设预算、防重复买 | `shopping-list-planner` |
| [礼物清单](../skills/gift-list/) | 按对象与预算定礼物方向（只给品类），附卡片文案与避雷清单 | `gift-list` |
| [生日策划](../skills/birthday-party-planner/) | 生日策划：按寿星与预算定主题场地，三段时间线，附三份现成方案 | `birthday-party-planner` |
| [手机管理](../skills/kids-screen-time/) | 给家长的孩子屏幕规则：和孩子一起写约定，附冲突时的说法与复盘 | `kids-screen-time` |
| [养狗](../skills/dog-care-basics/) | 新手养狗：接狗准备、第一周安排、三项基础训练、疫苗驱虫常识 | `dog-care-basics` |
| [跑步入门](../skills/running-for-beginners/) | 零基础跑步 8 周计划：从跑 1 分钟走 2 分钟起步，到连续慢跑 30 分钟 | `running-for-beginners` |
| [睡眠计划](../skills/sleep-plan/) | 两周改善睡眠的作息计划：先钉住起床时间，附睡眠日志，不做诊断 | `sleep-plan` |
| [晨间简报](../skills/morning-briefing/) | 把待办、日程、消息按优先级整理成五段式简报，分三种长度 | `morning-briefing` |

### 数据与办公自动化

12 个。报表、取数 SQL、一次性脚本与办公自动化；Excel、Word、PPT 这类文档处理；视频抽帧与音频剪辑；以及 CSV、JSON、Markdown 这类格式活。

| 中文名 | 一句话 | slug |
|---|---|---|
| [报表制作](../skills/report-making/) | 做业务报表：先问读者要做的决定，写清指标口径，再搭表选图 | `report-making` |
| [SQL 生成](../skills/sql-generation-helper/) | 把取数需求写成只读 SQL：先确认表结构与口径，每条附说明与坑 | `sql-generation-helper` |
| [Python 脚本](../skills/python-script-writer/) | 写一次性 Python 脚本：先问清输入输出，给可运行骨架与三个模板 | `python-script-writer` |
| [自动化办公](../skills/office-automation-scripts/) | 先算自动化能不能回本，再在公式、宏、Python 间选工具，附模板 | `office-automation-scripts` |
| [CSV 数据画像](../skills/csv-profile/) | CSV/TSV 体检：逐列类型、空值率、分位数，汇总重复行与疑似个人信息 | `csv-profile` |
| [JSON 格式化](../skills/json-formatting/) | JSON 美化、压缩与报错定位，必填字段粗校验，与 YAML、CSV 互转 | `json-formatting` |
| [Markdown 转换](../skills/markdown-conversion/) | pandoc 互转 Markdown、Word、HTML、PDF，含中文排版设置 | `markdown-conversion` |
| [Excel 处理](../skills/excel-processing/) | 用 openpyxl 批量建表、筛选、写公式、合并 xlsx，附 8 个坑修法 | `excel-processing` |
| [Word 排版](../skills/word-formatting/) | 先样式后内容排版 Word：编号、题注、页码、目录，附三套常见规格 | `word-formatting` |
| [PPT 制作](../skills/pptx-making/) | 写故事线与结论式标题，按内容选版式配图表，附大纲模板与自检清单 | `pptx-making` |
| [视频抽帧](../skills/video-frame-extract/) | 用 ffmpeg 按时间点、间隔或关键帧截图抽帧，拼缩略图、转 GIF | `video-frame-extract` |
| [音频剪辑](../skills/audio-editing/) | 用 ffmpeg 裁剪拼接音频、转格式调音量、去静音、提取视频音轨 | `audio-editing` |

### 让 AI 助手更好用

4 个。把踩过的坑记下来复用、按关键词搜技能、装前先扫风险、任务收尾主动提醒下一步。

| 中文名 | 一句话 | slug |
|---|---|---|
| [踩坑记录](../skills/lessons-learned-log/) | 把出错、返工按现象、根因、做法记成条目，开工前按关键词检索 | `lessons-learned-log` |
| [技能搜索](../skills/skill-search-helper/) | 把需求改写成搜索词找候选技能，按匹配度等比较，给首选与备选 | `skill-search-helper` |
| [安装前检查](../skills/skill-preinstall-check/) | 装技能前静态扫描六类危险动作，按高中低列出风险信号，不作安全认证 | `skill-preinstall-check` |
| [主动助手](../skills/proactive-assistant/) | 任务收尾固定汇报四段与风险，主动提醒截止与矛盾，对外动作先征求同意 | `proactive-assistant` |

## 开发者与运维

56 个。`skills/` 下的原创研发技能。带脚本的那些不装 Agent 也能当命令行工具直接跑，见 README「命令行 30 秒上手」。

### 研发总入口与方案评审

2 个。不确定该用哪个技能时从总入口进；技术方案落地前先过一遍多视角评审。

| 中文名 | 一句话 | slug |
|---|---|---|
| [研发全能助手](../skills/dev-workflow-pro/) | 研发流程总入口：需求、提交、评审、上线、排查等按意图路由到子技能 | `dev-workflow-pro` |
| [技术方案评审官](../skills/tech-design-review/) | 按 QA、SRE、安全、数据、成本五视角审技术方案，意见分三级 | `tech-design-review` |

### 上线与发布检查

14 个。发版前把能静态查出来的事故一次查完，检查类大多能直接当 CI 门禁。

| 中文名 | 一句话 | slug |
|---|---|---|
| [上线体检](../skills/release-readiness-check/) | 五项一起查：Dockerfile/K8s/SQL 迁移/OpenAPI/.env | `release-readiness-check` |
| [上线检查清单](../skills/release-checklist/) | 对比两个版本的实际改动，生成带验证与回滚方案的可勾选上线清单 | `release-checklist-git` |
| [Changelog 生成器](../skills/changelog/) | 按 tag 区间读提交，按 Keep a Changelog 生成发布说明 | `changelog-keep` |
| [数据库迁移风险](../skills/sql-migration-check/) | 扫迁移 SQL 里会锁表、丢数据的语句，给 MySQL/PG 各自的安全写法 | `sql-migration-check` |
| [K8s 配置检查](../skills/k8s-manifest-check/) | K8s YAML 生产就绪检查：安全基线、资源限制、探针、废弃 API | `k8s-manifest-check` |
| [Compose 配置体检](../skills/docker-compose-check/) | docker-compose.yml 体检：特权、明文密钥、镜像版本、健康检查 | `docker-compose-check` |
| [nginx 配置体检](../skills/nginx-config-check/) | nginx 配置安全与性能体检：TLS、安全响应头、代理超时等 17 条规则 | `nginx-config-check` |
| [.env 一致性检查](../skills/env-sync-check/) | .env.example、各环境 .env 与代码读取的变量三方对齐，查真密钥 | `env-sync-check` |
| [多环境配置对比](../skills/config-env-diff/) | 多份配置拉平成键路径逐个对比，分三类差异，密钥自动脱敏 | `config-env-diff` |
| [多语言文案键检查](../skills/i18n-missing-keys/) | 多语言文案对齐：缺失键、多余键、占位符不一致、用了却没定义的键 | `i18n-missing-keys` |
| [依赖漏洞体检](../skills/dep-vuln-check/) | 解析六种锁文件查 OSV.dev 已知漏洞，给严重度与建议升级版本 | `dep-vuln-check-osv` |
| [依赖过期检查](../skills/dep-outdated-check/) | 七种依赖清单查落后多少版本，按主/次/补丁分级给升级顺序 | `dep-outdated-check` |
| [开源协议合规检查](../skills/license-check/) | 离线读 npm/Python/Go 依赖许可证，五级分类并出第三方清单草稿 | `license-check-offline` |
| [CI 配置审查](../skills/ci-config-review/) | 离线扫 CI 配置：未固定 SHA、脚本注入、权限、secret 泄露 | `ci-config-review` |

### 线上排查与可观测

13 个。出事时把日志、指标、变更对齐成证据；平时做巡检与容量摸底。

| 中文名 | 一句话 | slug |
|---|---|---|
| [线上排查简报](../skills/incident-brief/) | 变更、指标异常与人工观察对齐成时间线，排候选给反证，不下根因 | `incident-brief-sre` |
| [日志突变检测](../skills/log-anomaly/) | 日志或指标 CSV 转时间序列，用 3σ 找出异常开始、峰值与恢复点 | `log-anomaly-3sigma` |
| [日志时间线重建](../skills/log-timeline/) | 多个格式、时区不同的日志合成一条时间线，标出错误爆发点 | `log-timeline` |
| [日志模板聚类](../skills/log-pattern-cluster/) | 日志按模板归并计数：最常见的是噪音，最少见的指向新错误 | `log-pattern-cluster` |
| [访问日志统计](../skills/access-log-stats/) | 访问日志变接口级报表：请求量、P50/P95/P99、5xx、高峰、Top IP | `access-log-stats` |
| [慢查询分析](../skills/sql-slow-query-digest/) | 慢查询日志按指纹聚合成 Top SQL 报表，标出无索引等问题与改法 | `sql-slow-query-digest` |
| [Prometheus 规则体检](../skills/prometheus-rule-check/) | 不连 Prometheus 评审告警与录制规则：缺 for、窗口不匹配、告警风暴 | `prometheus-rule-check` |
| [HTTP 健康巡检](../skills/http-health-check/) | 并发巡检一批 URL：状态码、耗时、关键字、HTTPS 证书剩余天数 | `http-health-check` |
| [TLS 证书巡检](../skills/tls-cert-check/) | 批量巡检 HTTPS 证书：剩余天数、SAN 是否覆盖主机名、证书链 | `tls-cert-check` |
| [域名解析巡检](../skills/dns-check/) | 不依赖 dig 查多种 DNS 记录，并排对比多个解析器，验证解析是否生效 | `dns-check` |
| [轻量 HTTP 压测](../skills/http-bench-lite/) | 没装 ab/wrk 也能压：成功率、QPS 与延迟分位，并发与时长有硬上限 | `http-bench-lite` |
| [HAR 性能分析](../skills/har-analyze/) | 读懂 HAR：耗时与体积 Top N、阶段分解、按域名聚合、9 类问题 | `har-analyze` |
| [cron 表达式解释器](../skills/cron-explain/) | cron 表达式译成中文，按时区列出接下来 N 次运行，识别日/周陷阱 | `cron-explain` |

### 代码与仓库治理

12 个。提交、评审、分支、测试覆盖、技术债、GitHub 操作——仓库的长期健康度。

| 中文名 | 一句话 | slug |
|---|---|---|
| [迭代周报生成器](../skills/iteration-report/) | 从 Git 提交与工单生成可溯源的迭代周报，风险与遗留单列 | `iteration-report-git` |
| [Git 提交信息生成器](../skills/commit-message/) | 按暂存区 diff 生成 Conventional Commits 中英文候选 | `commit-message-cc` |
| [提交信息规范检查](../skills/git-commit-lint/) | 按 Conventional Commits 体检一段提交，可做 CI 门禁 | `git-commit-lint` |
| [PR 描述生成](../skills/pr-description/) | 从分支提交与 diff 生成 PR/MR 描述草稿，标出迁移与依赖风险 | `pr-description` |
| [仓库泄密自查](../skills/secrets-scan/) | 扫仓库与近期提交历史里硬编码的密钥，命中值脱敏并给轮换改法 | `secrets-scan` |
| [CODEOWNERS 建议](../skills/codeowners-suggest/) | 从 git 历史推导各目录实际维护者，生成带占比的 CODEOWNERS 草稿 | `codeowners-suggest` |
| [代码热点与知识集中度](../skills/git-hotspots/) | 用 git 历史找缺陷高发文件、只有一人在改的目录与隐性耦合 | `git-hotspots` |
| [git 分支清理助手](../skills/git-branch-cleanup/) | 只读分析分支，分三类并生成待人工审阅的删除脚本，不自动删除 | `git-branch-cleanup` |
| [测试覆盖缺口](../skills/test-coverage-gap/) | 该先给哪些文件补测试：无测试的源码按改动热度排序，叠加覆盖率 | `test-coverage-gap` |
| [flaky 测试识别](../skills/flaky-test-finder/) | 汇总多次 JUnit XML 报告，找出时过时挂的用例及其失败率与报错 | `flaky-test-finder` |
| [技术债标记盘点](../skills/todo-debt-scan/) | 汇总 TODO/FIXME，用 git blame 算作者与年龄，出优先清单 | `todo-debt-scan` |
| [GitHub 操作](../skills/github-cli-ops/) | 用 gh 命令行查 issue、PR 与 CI 日志，写操作先预览、确认再执行 | `github-cli-ops` |

### 接口与契约

8 个。接口的生成、对比、回归与兼容性把关。

| 中文名 | 一句话 | slug |
|---|---|---|
| [接口契约回归](../skills/api-contract-test/) | 跑一组接口用例：校验状态码、JSON 字段、响应头与耗时，可当门禁 | `api-contract-test` |
| [接口差分测试](../skills/api-diff/) | 同一批请求打到两个环境，逐字段对比 JSON 响应，做发布前后回归 | `api-diff-test` |
| [curl 转代码](../skills/curl-to-code/) | curl 译成 8 种语言的请求代码，凭据自动改读环境变量 | `curl-to-code` |
| [OpenAPI 破坏性变更检查](../skills/openapi-breaking-diff/) | 对比两个 OpenAPI 3.x 规范，变更分破坏性与非破坏性逐条列出 | `openapi-breaking-diff` |
| [接口文档生成](../skills/openapi-to-markdown/) | OpenAPI 3.x 转中文 Markdown 接口文档，$ref 自动展开 | `openapi-to-markdown` |
| [JSON Schema 推断](../skills/json-schema-infer/) | 几条样例 JSON 推断出 JSON Schema，识别必填、可选与可空 | `json-schema-infer` |
| [JWT 解码与体检](../skills/jwt-inspect/) | 解开 JWT 逐条解释，换算过期时间，顺带查 alg=none 等安全问题 | `jwt-inspect` |
| [建表 SQL 结构对比](../skills/sql-schema-diff/) | 对比两份建表 SQL，生成 ALTER TABLE 草稿，单列会锁表的高危项 | `sql-schema-diff` |

### 数据与文本处理

2 个。读懂正则；日志和数据对外分享前先脱敏。

| 中文名 | 一句话 | slug |
|---|---|---|
| [正则中文解释](../skills/regex-explain/) | 正则译成中文并逐 token 拆解，提示灾难性回溯等 8 类风险 | `regex-explain` |
| [日志与数据脱敏](../skills/sensitive-data-mask/) | 对外分享前脱敏：手机号、身份证、银行卡、密钥等，三种替换策略 | `sensitive-data-mask` |

### Agent 与技能开发

5 个。Agent 工程、技能编写与打分、批量发布到 SkillHub、构建 WorkBuddy 连接器。

| 中文名 | 一句话 | slug |
|---|---|---|
| [Agent 工程](../skills/agent-engineering-expert/) | Agent 工程总入口：触发面、上下文预算、工具定义、子代理编排等 | `agent-engineering-expert` |
| [技能编写](../skills/skill-author-expert/) | 技能从选题到上架的清单：frontmatter、触发面、slug 撞名、发布配额 | `skill-author-expert` |
| [技能体检](../skills/skill-lint/) | 从可发现性、结构、可执行性、合规、示例五个维度给 SKILL.md 打分 | `skill-lint-scorecard` |
| [SkillHub 发布助手](../skills/skillhub-publish-helper/) | 批量发布到 SkillHub：校验、剔除会被拒的文件、限速、记 skillId | `skillhub-publish-helper` |
| [连接器构建助手](../skills/build-workbuddy-connector/) | 按 WorkBuddy 开放平台规范构建连接器：规范速查、骨架生成、校验 | `build-workbuddy-connector` |

## 工程实践复刻系列

59 个。`ported/skills/` 下的中文复刻：来自成熟的外部开源项目，不是逐字翻译，每个都做了中文化与场景适配，逐个目录附 `ATTRIBUTION.md` 写明来源、许可证与改动。上游：[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 25、[mattpocock/skills](https://github.com/mattpocock/skills) 18、[obra/superpowers](https://github.com/obra/superpowers) 10、[muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) 5、[anthropics/skills](https://github.com/anthropics/skills) 1。

### 需求与方案

9 个。动手前把想法、需求和设计谈清楚；第一行是其中 25 个工程实践技能的路由表。

| 中文名 | 一句话 | slug |
|---|---|---|
| [工程实践技能系列·总入口](../ported/skills/engineering-skills-index-zh/) | 25 个工程实践技能的路由表：先判断阶段再选技能，附六条通用行为 | `engineering-skills-index-zh` |
| [需求头脑风暴与设计](../ported/skills/brainstorming-zh/) | 动手前把想法谈成设计：分级、逐条提问、方案对比、写 spec，批准再做 | `brainstorming-spec-zh` |
| [需求盘问官](../ported/skills/grill-me-zh/) | 按设计树分轮追问，每题附推荐答案，问清后落盘 decisions.md 再开工 | `grill-me-zh` |
| [需求访谈（一次一问）](../ported/skills/interview-me-zh/) | 动手前问出真实意图：一句话假设加置信度，一次一问，确认才停 | `interview-me-zh` |
| [创意打磨（发散→收敛→一页纸）](../ported/skills/idea-refine-zh/) | 粗糙点子磨成方案：HMW 重述、七种透镜、压力测试，出一页纸 | `idea-refine-zh` |
| [规格驱动开发（先 Spec 后代码）](../ported/skills/spec-driven-zh/) | 写代码前先写 spec：六要素模板，把模糊需求改写成成功标准 | `spec-driven-zh` |
| [需求→Spec→任务拆解](../ported/skills/spec-and-tickets-zh/) | 讨论整理成 Spec，再拆成带阻塞关系的垂直切片工单 | `spec-and-tickets-zh` |
| [决策问卷生成](../ported/skills/to-questionnaire-zh/) | 把自己答不了的决策变成问卷，交给掌握信息的人异步填写 | `to-questionnaire-zh` |
| [一次性原型（逻辑 / UI）](../ported/skills/prototype-zh/) | 一次性原型回答一个问题：逻辑走单文件 HTML，外观走多个 UI 变体 | `prototype-zh` |

### 文档研究与学习

5 个。写方案与决策文档、只查一手来源、把没讲明白的话重讲一遍、搭学习工作台。

| 中文名 | 一句话 | slug |
|---|---|---|
| [文档协作写作三阶段](../ported/skills/doc-coauthoring-zh/) | 和用户一起写方案与决策文档：转移上下文、逐节共创、零上下文读者验收 | `doc-coauthoring-zh` |
| [文档与 ADR](../ported/skills/docs-and-adr-zh/) | 记录决策而不只是代码：ADR 何时写与模板，注释只写 why | `docs-and-adr-zh` |
| [一手来源研究](../ported/skills/research-primary-zh/) | 只查官方文档、源码、规范等一手来源，每个主张附引用 | `research-primary-zh` |
| [没听懂，重讲一遍](../ported/skills/re-pitch-zh/) | 上一条没讲明白时重讲：先补背景，短句、一句一意，不加新信息 | `re-pitch-zh` |
| [学习工作台（教我一门技能）](../ported/skills/teach-workspace-zh/) | 把一个目录变成学习工作台：任务书、术语表、每课一个 HTML 小课 | `teach-workspace-zh` |

### 计划与执行

8 个。从 spec 到任务，再到逐步执行；超出一次会话的大事拆成决策工单。

| 中文名 | 一句话 | slug |
|---|---|---|
| [实施计划与任务拆解](../ported/skills/planning-tasks-zh/) | 从 spec 到可执行任务：依赖图、垂直切片，每个任务带验收与验证 | `planning-tasks-zh` |
| [编写实施计划](../ported/skills/writing-plans-zh/) | 把 spec 写成零上下文工程师能照做的计划，每步附代码与验证命令 | `writing-impl-plans-zh` |
| [执行实施计划](../ported/skills/executing-plans-zh/) | 把写好的实施计划执行到底：先审计划、逐任务验证、遇阻即停 | `executing-dev-plans-zh` |
| [增量实现（薄切片）](../ported/skills/incremental-implementation-zh/) | 功能切成可独立验证的薄片，按实现、测试、验证、提交循环推进 | `incremental-implementation-zh` |
| [源驱动开发（官方文档为准）](../ported/skills/source-driven-zh/) | 框架代码先查官方文档：认版本、按文档实现并引用，查不到标 UNVERIFIED | `source-driven-zh` |
| [导航图（大事拆决策工单）](../ported/skills/wayfinder-zh/) | 超出一次会话的大事画成地图：命名目的地，拆决策工单逐个解决 | `wayfinder-zh` |
| [工单分诊状态机](../ported/skills/triage-zh/) | Issue 与外部 PR 过状态机：分类、验证，写 Agent 可直接执行的简报 | `issue-triage-zh` |
| [人工步骤向导生成器](../ported/skills/wizard-zh/) | 把只有人能做的手工步骤做成分阶段确认的 bash 向导 | `wizard-zh` |

### 测试调试与验证

10 个。TDD、浏览器验证、完成前验证、对抗复审，以及几套调试与性能方法。

| 中文名 | 一句话 | slug |
|---|---|---|
| [测试驱动开发（红-绿-重构）](../ported/skills/tdd-zh/) | 先写失败的测试再写代码，修 bug 先复现；测状态不测交互、少 mock | `tdd-zh` |
| [接缝驱动 TDD](../ported/skills/tdd-seams-zh/) | 红绿循环手册：测试写在预先约定的接缝上，避开三大反模式 | `tdd-seams-zh` |
| [浏览器 DevTools 测试](../ported/skills/browser-testing-devtools-zh/) | 让 Agent 在真实浏览器里验证：UI、网络、性能排查与截图回归 | `browser-testing-devtools-zh` |
| [完成前验证门禁](../ported/skills/verification-before-completion-zh/) | 说「完成」「修好」之前，必须有本轮新跑出的证据；附五步门禁 | `pre-completion-verification-zh` |
| [约束驱动开发（CONSTRAINTS.md）](../ported/skills/constraints-md-zh/) | 质量标准写成能机械检查的 CONSTRAINTS.md：底线、棘轮、限期例外 | `constraints-md-zh` |
| [质疑驱动开发（对抗复审）](../ported/skills/doubt-driven-zh/) | 非平凡决策先交给冷上下文审稿者对抗性复审，三轮封顶 | `doubt-driven-zh` |
| [系统化排错与分诊](../ported/skills/debug-triage-zh/) | 出问题先停线保留证据，从复现到端到端验证六步分诊 | `debug-triage-zh` |
| [Bug 诊断法](../ported/skills/diagnosing-bugs-zh/) | 六阶段调试：先造能变红的反馈回路，列可证伪假设，先写回归测试 | `diagnosing-bugs-zh` |
| [系统化调试四阶段](../ported/skills/systematic-debugging-zh/) | 任何 Bug 先找根因再修：四阶段流程，三次失败即质疑架构 | `systematic-debugging-zh` |
| [性能优化（先测量再优化）](../ported/skills/performance-optimization-zh/) | 测量、定位、修、验证、守护：常见性能问题修法，中性改动一律回退 | `performance-optimization-zh` |

### 代码设计与评审

8 个。接口与模块设计、前端 UI、代码化简，以及发起评审与接收评审意见。

| 中文名 | 一句话 | slug |
|---|---|---|
| [API 与接口设计](../ported/skills/api-design-zh/) | 设计难以误用的稳定接口：契约先行、统一错误、只加不改、幂等键 | `api-design-zh` |
| [深模块设计（接口·接缝·可测性）](../ported/skills/deep-module-design-zh/) | 设计深模块：小接口大实现、接缝与适配器，设计两次再比较 | `deep-module-design-zh` |
| [架构加深体检（HTML 报告）](../ported/skills/architecture-deepening-zh/) | 扫代码库找浅模块变深的重构机会，输出 HTML 架构评审报告 | `architecture-deepening-zh` |
| [前端 UI 工程（生产级·无障碍）](../ported/skills/frontend-ui-zh/) | 生产级前端界面：组件架构、避开 AI 默认审美、WCAG 2.1 AA 无障碍 | `frontend-ui-zh` |
| [代码化简（行为不变）](../ported/skills/code-simplification-zh/) | 行为不变地让代码更好读：五原则，一次一改并跑测试 | `code-simplification-zh` |
| [五轴代码评审](../ported/skills/code-review-five-axis-zh/) | 正确性、可读性、架构、安全、性能五轴评审，意见分级 | `code-review-five-axis-zh` |
| [代码评审（双轴）](../ported/skills/code-review-zh/) | 规范与坏味道、是否实现需求两轴分开评审，脚本预扫密钥等 | `code-review-zh` |
| [接收代码评审意见](../ported/skills/receiving-code-review-zh/) | 把评审意见当技术输入：看不懂先问，该反驳用技术理由，逐条验证 | `code-review-response-zh` |

### Git 工作流

4 个。主干开发、工作树隔离、解冲突、分支收尾。

| 中文名 | 一句话 | slug |
|---|---|---|
| [Git 工作流与版本管理](../ported/skills/git-workflow-zh/) | 主干开发、短分支、原子提交、语义化版本与面向人的 changelog | `git-workflow-zh` |
| [Git 工作树隔离工作区](../ported/skills/using-git-worktrees-zh/) | 动手前确保在隔离工作区：建 worktree、装依赖、跑基线测试 | `git-worktree-workflow-zh` |
| [合并冲突解决](../ported/skills/merge-conflicts-zh/) | 五步解 merge/rebase 冲突：追双方意图，逐块保留不发明行为 | `merge-conflicts-zh` |
| [开发分支收尾](../ported/skills/finishing-a-development-branch-zh/) | 实现完成后先验证测试，再在本地合并、发 PR、原样保留中三选一 | `dev-branch-finishing-zh` |

### 上线运维与安全

5 个。CI/CD 门禁、渐进发布与回滚、下线迁移、可观测性、安全加固。

| 中文名 | 一句话 | slug |
|---|---|---|
| [CI/CD 与自动化门禁](../ported/skills/ci-cd-zh/) | 质量门禁自动化：lint 到 E2E 一个不跳，预览部署与分阶段发布 | `ci-cd-zh` |
| [上线发布（清单·灰度·回滚）](../ported/skills/shipping-launch-zh/) | 可逆、可观测、渐进地发布：发布前清单、灰度阈值、回滚条件 | `shipping-launch-zh` |
| [下线与迁移（扩展-收缩）](../ported/skills/deprecation-migration-zh/) | 安全下线老系统与旧接口：绞杀者模式、expand/contract 不停机改名 | `deprecation-migration-zh` |
| [可观测性与埋点](../ported/skills/observability-zh/) | 先写值班会问的问题再埋点：结构化日志、RED/USE 指标、症状告警 | `observability-zh` |
| [安全加固（威胁建模到 LLM 安全）](../ported/skills/security-hardening-zh/) | 先威胁建模再加固：OWASP、SSRF、依赖审计、LLM 输出当不可信输入 | `security-hardening-zh` |

### Agent 与上下文工程

10 个。上下文预算、退化与压缩、记忆、工具设计、给 Agent 写文档、子代理编排。

| 中文名 | 一句话 | slug |
|---|---|---|
| [上下文工程基础](../ported/skills/context-fundamentals-zh/) | 把上下文当有限的注意力预算：信息量优先、关键约束放首尾 | `context-fundamentals-zh` |
| [上下文工程（规则文件与预算）](../ported/skills/context-engineering-zh/) | 让 Agent 适时看到对的信息：五层上下文、规则文件模板、信任分级 | `context-engineering-zh` |
| [上下文退化诊断](../ported/skills/context-degradation-zh/) | 诊断上下文失效：中间迷失、投毒、干扰、混淆、冲突五种模式 | `context-degradation-zh` |
| [上下文压缩策略](../ported/skills/context-compression-zh/) | 长会话压缩不丢关键信息：按任务算 token，先保产物轨迹 | `context-compression-strategies-zh` |
| [Agent 记忆系统设计](../ported/skills/memory-systems-zh/) | 让 Agent 跨会话保持连续：记忆分层、按检索形状选框架 | `memory-systems-zh` |
| [面向 Agent 的工具设计](../ported/skills/tool-design-zh/) | 工具即契约：合并重叠工具、一致命名、面向恢复的错误信息 | `tool-design-zh` |
| [给 Agent 写文档（技能与规则文件）](../ported/skills/writing-for-agents-zh/) | 让技能与 AGENTS.md 每次都被正确读取：信息层级与渐进披露 | `writing-for-agents-zh` |
| [会话交接单](../ported/skills/handoff-doc-zh/) | 把当前对话压成下一个 Agent 或同事能直接接手的交接单 | `handoff-doc-zh` |
| [并行派发子代理](../ported/skills/dispatching-parallel-agents-zh/) | 互相独立的问题一次分派给多个子代理：切分、提示词、冲突检查 | `parallel-agent-dispatch-zh` |
| [子代理驱动开发](../ported/skills/subagent-driven-development-zh/) | 实施计划驱动子代理流水线：每任务新实现者、双判定评审、账本抗压缩 | `subagent-driven-development-zh` |
