# workbuddy-skills

面向腾讯 WorkBuddy / SkillHub 的开源中文 Agent 技能，全部以账号 `indiv-captain` 发布在 [skillhub.cn](https://skillhub.cn/)，截至 2026-09-26 线上 **200 个**（SkillHub 单账号上限），另有新写的技能在本仓库先行可用、排队上架：从检讨书、请假条、开题报告、背单词、租房、个税汇算这类日常事，到上线体检、日志排查、代码评审这类研发活。许可：文字部分（文档、`SKILL.md` 正文、模板）CC BY 4.0，代码 MIT，见 [LICENSE-CONTENT](LICENSE-CONTENT)；`ported/` 下的复刻技能沿用各自上游的许可证。用法：在 skillhub.cn 搜技能的中文名（比如「检讨书」），在技能页安装；或者用命令行 `skillhub install <slug> --namespace indiv-captain`。`--namespace` 不能省：有些 slug 和其他作者的技能同名（如 `code-review-zh`、`pr-description`、`secrets-scan`、`skillhub-publish-helper`），不带它可能装到别人的那个。

```bash
skillhub install reflection-letter --namespace indiv-captain   # 检讨书
skillhub install renting-guide --namespace indiv-captain       # 租房攻略
```

---

## 按场景找技能

最上面两组是 2026-09 新增的开学季与腾讯生态技能。其余 180 个技能分三块：**日常场景**（65 个）→ **开发者与运维**（56 个）→ **工程实践复刻系列**（59 个）。日常场景下面全部列出；后两块这里只列分组，逐条清单见 **[docs/SKILLS.md](docs/SKILLS.md)**。

每行是「中文名 | 一句话 | slug」。中文名就是 SkillHub 上的展示名，拿它去 skillhub.cn 搜；点开是仓库里的源目录。slug 用于命令行安装。日常场景 65 个里，除公文写作、PPT汇报演示、简历优化助手、职场防骗、理财入门、保单解读、个税申报、CSV 数据画像这 8 个，46 个是 2026-09-23 新上线的，另有 11 个是 2026-09-24 新上线的（含新分组「让 AI 助手更好用」的 4 个）。

### 开学季与秋招（2026-09 新增）

15 个：开学、竞选、奖助学金、秋招、考研保研、实践报告。都是写之前 SkillHub 全站搜不到的词，只帮你整理自己的真实经历，示例一律标虚构。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [国庆攻略](skills/national-day-travel/) | 黄金周错峰出行：出发返程时段、订票订房节奏、自驾与应急预案，附行程预算脚本 | [`national-day-travel`](https://skillhub.cn/skills/@indiv-captain/national-day-travel) |
| [实习报告](skills/internship-report/) | 实习报告四段结构，把真实工作记录写成段落，附周记模板与提交前自查脚本 | [`internship-report`](https://skillhub.cn/skills/@indiv-captain/internship-report) |
| [秋招](skills/autumn-campus-recruiting/) | 秋招全流程：投递记录、笔试面试、三方协议常识与防骗，附 offer 加权对比脚本 | 排队上架 |
| [考研报名](skills/kaoyan-registration/) | 考研报名流程与逐项核对表：报考点、学历校验、确认后能改什么（以当年公告为准） | 排队上架 |
| [保研](skills/postgrad-recommendation/) | 推免准备：夏令营/预推免/九推节奏、联系导师邮件、个人陈述与面试 | 排队上架 |
| [期中复习](skills/midterm-review/) | 按距考试 14/7/3/1 天排计划、课程分级与取舍，附每日复习分配脚本 | 排队上架 |
| [竞选稿](skills/campaign-speech/) | 班干部、学生会竞选稿：为什么是我、三件具体的事，1/2/3 分钟三档，附计时脚本 | 排队上架 |
| [奖学金申请](skills/scholarship-application/) | 奖学金申请书：六个维度盘点真实事实、STAR 写法、面试答辩题，附自查脚本 | 排队上架 |
| [助学金申请书](skills/financial-aid-application/) | 困难资助申请书：如实陈述不渲染、材料清单、隐私保护，附脱敏扫描脚本 | 排队上架 |
| [军训心得](skills/military-training-reflection/) | 从一个亲历瞬间写起的三段式军训心得，800/1500 字两档，附套话自查脚本 | 排队上架 |
| [学生会面试](skills/student-union-interview/) | 学生会、社团、班委面试：1 分钟自我介绍、20 道高频题思路、无领导小组套路 | 排队上架 |
| [新生自我介绍](skills/freshman-self-intro/) | 班级、宿舍、社团、导师、线上群五种场合，30 秒到 3 分钟三档模板 | 排队上架 |
| [班会策划](skills/class-meeting-planning/) | 主题班会 45 分钟标准流程、主持稿框架与互动形式，附三个完整方案 | 排队上架 |
| [社团招新](skills/club-recruitment/) | 招新推文、摆摊话术、报名表与 7 天留人计划，附报名表统计去重脚本 | 排队上架 |
| [社会实践报告](skills/social-practice-report/) | 暑期社会实践报告：选题分工、问卷访谈、只用真实数据、受访者隐私，附问卷统计脚本 | 排队上架 |

### 腾讯生态（2026-09 新增）

8 个：企业微信、腾讯会议、腾讯问卷、TAPD、腾讯云轻量服务器、腾讯位置服务、微信群、小程序。脚本只用 Python 标准库；凡是会发消息或改资源的，默认只预览；key 一律从环境变量读。接口细节以官方文档为准。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [企微机器人](skills/wecom-group-bot/) | 企业微信群机器人推送日报、告警、提醒：模板、errcode 解释，默认只预览、确认才发送 | 排队上架 |
| [腾讯会议纪要](skills/tencent-meeting-minutes/) | 把腾讯会议导出的转写文本整理成可发群的纪要：解析发言人，挑出决议与待办 | 排队上架 |
| [腾讯问卷](skills/tencent-survey-analysis/) | 腾讯问卷导出数据清洗与统计：自动识别题型，频数、量表均值、交叉表，附报告模板 | 排队上架 |
| [缺陷管理](skills/defect-management/) | TAPD 等工具的缺陷单模板、严重度×优先级、流转规则，附导出 CSV 的复盘统计脚本 | 排队上架 |
| [轻量服务器](skills/lighthouse-server/) | 腾讯云轻量服务器从零上手：安全基线、部署顺序、快照备份与巡检，附只读体检脚本 | 排队上架 |
| [地址解析](skills/address-geocoding/) | 中文地址批量解析：清洗规则、腾讯位置服务地理编码（key 读环境变量、默认预演）、配送半径 | 排队上架 |
| [微信群管理](skills/wechat-group-management/) | 微信群运营：群规、欢迎语、活动节奏、违规处理与群主交接，附本地聊天统计脚本 | 排队上架 |
| [小程序审核](skills/miniprogram-review/) | 小程序提审前七项自查、驳回原因到修改动作对照、申诉模板，附项目扫描脚本 | 排队上架 |

### 职场写作与沟通

25 个：公文、汇报、邮件、检讨与请假；求职、加薪与离职；招聘、入职与带人；会议、调研与各类文案；文风改写去AI味。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [公文写作](skills/gov-doc-expert/) | 通知、请示、报告、纪要、述职等公文：选文种、定格式、素材加工成稿 | [`gov-doc-expert`](https://skillhub.cn/skills/@indiv-captain/gov-doc-expert) |
| [PPT汇报演示](skills/presentation-expert/) | 整场汇报：先定受众要做的决定，搭故事线、选图表、写讲稿 | [`presentation-expert`](https://skillhub.cn/skills/@indiv-captain/presentation-expert) |
| [英文邮件](skills/english-email/) | 商务英文邮件：七种意图的结构与句式、三档语气，附中式英语自查 | [`english-email`](https://skillhub.cn/skills/@indiv-captain/english-email) |
| [检讨书](skills/reflection-letter/) | 检讨书与情况说明：按事实、责任、影响、整改四层写，附三套模板 | [`reflection-letter`](https://skillhub.cn/skills/@indiv-captain/reflection-letter) |
| [请假条](skills/leave-request-note/) | 请假条：学校、公司两套填空格式，各类假别的写法差异与常附材料 | [`leave-request-note`](https://skillhub.cn/skills/@indiv-captain/leave-request-note) |
| [简历优化助手](skills/resume-job-expert/) | 整条求职链路：按 JD 改简历、投递、各轮面试、offer 比较与谈薪 | [`resume-job-expert`](https://skillhub.cn/skills/@indiv-captain/resume-job-expert) |
| [职场防骗](skills/workplace-antiscam-expert/) | 识别求职与职场骗局：招聘收费、培训贷、刷单、冒充领导转账等 | [`workplace-antiscam-expert`](https://skillhub.cn/skills/@indiv-captain/workplace-antiscam-expert) |
| [加薪申请](skills/salary-raise-request/) | 准备加薪沟通：盘点可举证的成果、选时机、三段式谈，附申请模板 | [`salary-raise-request`](https://skillhub.cn/skills/@indiv-captain/salary-raise-request) |
| [离职谈话](skills/resignation-conversation/) | 离职谈话：员工怎么提、被挽留怎么回；管理者怎么谈、交接怎么排 | [`resignation-conversation`](https://skillhub.cn/skills/@indiv-captain/resignation-conversation) |
| [招聘 JD](skills/job-description-writer/) | 写招聘 JD：三段式结构、写清薪资区间，排查歧视性表述，附三份模板 | [`job-description-writer`](https://skillhub.cn/skills/@indiv-captain/job-description-writer) |
| [入职指南](skills/onboarding-guide/) | 给新同事写入职指南：按首日、首周、首月列清单，含导师机制与模板 | [`onboarding-guide`](https://skillhub.cn/skills/@indiv-captain/onboarding-guide) |
| [新人带教](skills/new-hire-mentoring/) | 带教新同事：30/60/90 天目标、每周一对一、由易到难排任务、给反馈 | [`new-hire-mentoring`](https://skillhub.cn/skills/@indiv-captain/new-hire-mentoring) |
| [KPI 制定](skills/kpi-design/) | 制定团队或岗位 KPI：从上级目标拆指标，过 SMART，定权重与口径 | [`kpi-design`](https://skillhub.cn/skills/@indiv-captain/kpi-design) |
| [团建方案](skills/team-building-plan/) | 团建方案：先定目的，按预算与人数选形式，附三份模板与避雷清单 | [`team-building-plan`](https://skillhub.cn/skills/@indiv-captain/team-building-plan) |
| [会议安排](skills/meeting-arrangement/) | 安排会议：先判断要不要开，再定目标、参会人与议程，附议程模板 | [`meeting-arrangement`](https://skillhub.cn/skills/@indiv-captain/meeting-arrangement) |
| [会议录音整理](skills/meeting-transcript-cleanup/) | 会议转写稿整理成纪要：按议题重组，抽出决议、待办与负责人 | [`meeting-transcript-cleanup`](https://skillhub.cn/skills/@indiv-captain/meeting-transcript-cleanup) |
| [长文总结](skills/long-doc-summary/) | 长文总结：按读者与用途出 100/300/1000 字三版，关键数字标出处 | [`long-doc-summary`](https://skillhub.cn/skills/@indiv-captain/long-doc-summary) |
| [访谈提纲](skills/interview-outline/) | 用户与专家访谈提纲：主线只问过去的具体行为，附追问句式与记录模板 | [`interview-outline`](https://skillhub.cn/skills/@indiv-captain/interview-outline) |
| [问卷设计](skills/questionnaire-design/) | 问卷设计：从调研目标推出题目，选题型、排题序，排查诱导与双重提问 | [`questionnaire-design`](https://skillhub.cn/skills/@indiv-captain/questionnaire-design) |
| [主持词](skills/event-host-script/) | 年会、婚礼、发布会等六类活动主持词：开场、串场、收尾与冷场话术 | [`event-host-script`](https://skillhub.cn/skills/@indiv-captain/event-host-script) |
| [广播稿](skills/radio-script/) | 校园、社区、企业广播稿：开场与串联词，书面稿改口语，附填空模板 | [`radio-script`](https://skillhub.cn/skills/@indiv-captain/radio-script) |
| [上新文案](skills/new-product-copy/) | 新品上市文案：参数转卖点，改写成详情页、推文与短视频口播脚本 | [`new-product-copy`](https://skillhub.cn/skills/@indiv-captain/new-product-copy) |
| [UI 文案](skills/ui-microcopy/) | 界面文案：按钮、空状态、错误提示、确认弹窗等的模板与中英对照 | [`ui-microcopy`](https://skillhub.cn/skills/@indiv-captain/ui-microcopy) |
| [图片描述](skills/image-alt-description/) | 给图片写描述：无障碍 alt 文本、商品图、社媒配文、图表文字化 | [`image-alt-description`](https://skillhub.cn/skills/@indiv-captain/image-alt-description) |
| [降AI味](skills/reduce-ai-tone/) | 12 条清单认出中文 AI 腔，按六步改写，附脚本统计套话与句长 | [`reduce-ai-tone`](https://skillhub.cn/skills/@indiv-captain/reduce-ai-tone) |

### 学习与考试

11 个：论文与学生写作、演讲与辩论、单词与日语、数学题、编程入门、驾考，以及给家长的孩子学习计划。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [开题报告](skills/thesis-opening-report/) | 开题报告六部分的填空模板与示例，附导师常打回的 8 种情况与改法 | [`thesis-opening-report`](https://skillhub.cn/skills/@indiv-captain/thesis-opening-report) |
| [观后感](skills/after-viewing-essay/) | 观后感：从打动你的一个细节写起、不复述剧情，附学生版与成人版模板 | [`after-viewing-essay`](https://skillhub.cn/skills/@indiv-captain/after-viewing-essay) |
| [辩论稿](skills/debate-speech/) | 辩论赛发言稿：一辩立论、攻辩问题链、自由辩分工、四辩结辩 | [`debate-speech`](https://skillhub.cn/skills/@indiv-captain/debate-speech) |
| [毕业致辞](skills/graduation-speech/) | 毕业致辞：学生、教师、家长三种身份，用故事、共同记忆与期许搭全篇 | [`graduation-speech`](https://skillhub.cn/skills/@indiv-captain/graduation-speech) |
| [背单词](skills/vocab-memorization-plan/) | 背单词计划：按目标和每天可用时间算新词量，按间隔复习排期 | [`vocab-memorization-plan`](https://skillhub.cn/skills/@indiv-captain/vocab-memorization-plan) |
| [日语学习](skills/japanese-learning-plan/) | 日语零基础到 N4/N3：首周拿下假名，沿语法主线推进，附两版日程 | [`japanese-learning-plan`](https://skillhub.cn/skills/@indiv-captain/japanese-learning-plan) |
| [数学题](skills/math-problem-tutor/) | 中小学数学题讲解：列已知与所求、分步推导、代回验算，不代做作业 | [`math-problem-tutor`](https://skillhub.cn/skills/@indiv-captain/math-problem-tutor) |
| [编程入门](skills/coding-for-beginners/) | 零基础编程入门：按目标选语言，前 30 天每日任务与每周一个小项目 | [`coding-for-beginners`](https://skillhub.cn/skills/@indiv-captain/coding-for-beginners) |
| [驾照考试](skills/driving-test-prep/) | 驾照四个科目的备考方法与考前一周计划，只教方法、不给题目答案 | [`driving-test-prep`](https://skillhub.cn/skills/@indiv-captain/driving-test-prep) |
| [阅读计划](skills/kids-reading-plan/) | 3–12 岁分三档的阅读计划：每日时长、共读比例、选书标准、记录表 | [`kids-reading-plan`](https://skillhub.cn/skills/@indiv-captain/kids-reading-plan) |
| [儿童编程](skills/kids-coding/) | 6–12 岁儿童编程：图形化还是 Python 起步，8 周计划，家长怎么陪 | [`kids-coding`](https://skillhub.cn/skills/@indiv-captain/kids-coding) |

### 家庭与生活

13 个：理财、保险与个税；租房、买车与购物；送礼与生日；孩子的屏幕时间、养狗、跑步与睡眠；晨间待办简报。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [理财入门](skills/financial-literacy-expert/) | 看懂年化、复利、费率与产品怎么赚怎么亏，识别保本稳赚话术 | [`financial-literacy-expert`](https://skillhub.cn/skills/@indiv-captain/financial-literacy-expert) |
| [保单解读](skills/insurance-policy-expert/) | 读懂手上的保单：免责条款、健康告知、理赔与拒赔、续保与退保 | [`insurance-policy-expert`](https://skillhub.cn/skills/@indiv-captain/insurance-policy-expert) |
| [个税申报](skills/tax-filing-expert/) | 个税年度汇算：办不办、专项附加扣除、年终奖计税、退税被驳回 | [`tax-filing-expert`](https://skillhub.cn/skills/@indiv-captain/tax-filing-expert) |
| [租房攻略](skills/renting-guide/) | 租房全流程清单：定预算、看房检查、签约核对、入住交接、退租拿押金 | [`renting-guide`](https://skillhub.cn/skills/@indiv-captain/renting-guide) |
| [买车](skills/car-buying-checklist/) | 买车决策清单：拆预算、定新车二手与油电，附试驾与合同交付核对项 | [`car-buying-checklist`](https://skillhub.cn/skills/@indiv-captain/car-buying-checklist) |
| [购物清单](skills/shopping-list-planner/) | 按场景生成可勾选的分类购物清单：按动线排序、设预算、防重复买 | [`shopping-list-planner`](https://skillhub.cn/skills/@indiv-captain/shopping-list-planner) |
| [礼物清单](skills/gift-list/) | 按对象与预算定礼物方向（只给品类），附卡片文案与避雷清单 | [`gift-list`](https://skillhub.cn/skills/@indiv-captain/gift-list) |
| [生日策划](skills/birthday-party-planner/) | 生日策划：按寿星与预算定主题场地，三段时间线，附三份现成方案 | [`birthday-party-planner`](https://skillhub.cn/skills/@indiv-captain/birthday-party-planner) |
| [手机管理](skills/kids-screen-time/) | 给家长的孩子屏幕规则：和孩子一起写约定，附冲突时的说法与复盘 | [`kids-screen-time`](https://skillhub.cn/skills/@indiv-captain/kids-screen-time) |
| [养狗](skills/dog-care-basics/) | 新手养狗：接狗准备、第一周安排、三项基础训练、疫苗驱虫常识 | [`dog-care-basics`](https://skillhub.cn/skills/@indiv-captain/dog-care-basics) |
| [跑步入门](skills/running-for-beginners/) | 零基础跑步 8 周计划：从跑 1 分钟走 2 分钟起步，到连续慢跑 30 分钟 | [`running-for-beginners`](https://skillhub.cn/skills/@indiv-captain/running-for-beginners) |
| [睡眠计划](skills/sleep-plan/) | 两周改善睡眠的作息计划：先钉住起床时间，附睡眠日志，不做诊断 | [`sleep-plan`](https://skillhub.cn/skills/@indiv-captain/sleep-plan) |
| [晨间简报](skills/morning-briefing/) | 把待办、日程、消息按优先级整理成五段式简报，分三种长度 | [`morning-briefing`](https://skillhub.cn/skills/@indiv-captain/morning-briefing) |

### 数据与办公自动化

12 个：报表、取数 SQL、一次性脚本与办公自动化；Excel、Word、PPT 这类文档处理；视频抽帧与音频剪辑；以及 CSV、JSON、Markdown 这类格式活。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [报表制作](skills/report-making/) | 做业务报表：先问读者要做的决定，写清指标口径，再搭表选图 | [`report-making`](https://skillhub.cn/skills/@indiv-captain/report-making) |
| [SQL 生成](skills/sql-generation-helper/) | 把取数需求写成只读 SQL：先确认表结构与口径，每条附说明与坑 | [`sql-generation-helper`](https://skillhub.cn/skills/@indiv-captain/sql-generation-helper) |
| [Python 脚本](skills/python-script-writer/) | 写一次性 Python 脚本：先问清输入输出，给可运行骨架与三个模板 | [`python-script-writer`](https://skillhub.cn/skills/@indiv-captain/python-script-writer) |
| [自动化办公](skills/office-automation-scripts/) | 先算自动化能不能回本，再在公式、宏、Python 间选工具，附模板 | [`office-automation-scripts`](https://skillhub.cn/skills/@indiv-captain/office-automation-scripts) |
| [CSV 数据画像](skills/csv-profile/) | CSV/TSV 体检：逐列类型、空值率、分位数，汇总重复行与疑似个人信息 | [`csv-profile`](https://skillhub.cn/skills/@indiv-captain/csv-profile) |
| [JSON 格式化](skills/json-formatting/) | JSON 美化、压缩与报错定位，必填字段粗校验，与 YAML、CSV 互转 | [`json-formatting`](https://skillhub.cn/skills/@indiv-captain/json-formatting) |
| [Markdown 转换](skills/markdown-conversion/) | pandoc 互转 Markdown、Word、HTML、PDF，含中文排版设置 | [`markdown-conversion`](https://skillhub.cn/skills/@indiv-captain/markdown-conversion) |
| [Excel 处理](skills/excel-processing/) | 用 openpyxl 批量建表、筛选、写公式、合并 xlsx，附 8 个坑修法 | [`excel-processing`](https://skillhub.cn/skills/@indiv-captain/excel-processing) |
| [Word 排版](skills/word-formatting/) | 先样式后内容排版 Word：编号、题注、页码、目录，附三套常见规格 | [`word-formatting`](https://skillhub.cn/skills/@indiv-captain/word-formatting) |
| [PPT 制作](skills/pptx-making/) | 写故事线与结论式标题，按内容选版式配图表，附大纲模板与自检清单 | [`pptx-making`](https://skillhub.cn/skills/@indiv-captain/pptx-making) |
| [视频抽帧](skills/video-frame-extract/) | 用 ffmpeg 按时间点、间隔或关键帧截图抽帧，拼缩略图、转 GIF | [`video-frame-extract`](https://skillhub.cn/skills/@indiv-captain/video-frame-extract) |
| [音频剪辑](skills/audio-editing/) | 用 ffmpeg 裁剪拼接音频、转格式调音量、去静音、提取视频音轨 | [`audio-editing`](https://skillhub.cn/skills/@indiv-captain/audio-editing) |

### 让 AI 助手更好用

4 个：把踩过的坑记下来复用、按关键词搜技能、装前先扫风险、任务收尾主动提醒下一步。

| 中文名 | 一句话 | SkillHub 页面（可收藏 / 安装） |
|---|---|---|
| [踩坑记录](skills/lessons-learned-log/) | 把出错、返工按现象、根因、做法记成条目，开工前按关键词检索 | [`lessons-learned-log`](https://skillhub.cn/skills/@indiv-captain/lessons-learned-log) |
| [技能搜索](skills/skill-search-helper/) | 把需求改写成搜索词找候选技能，按匹配度等比较，给首选与备选 | [`skill-search-helper`](https://skillhub.cn/skills/@indiv-captain/skill-search-helper) |
| [安装前检查](skills/skill-preinstall-check/) | 装技能前静态扫描六类危险动作，按高中低列出风险信号，不作安全认证 | [`skill-preinstall-check`](https://skillhub.cn/skills/@indiv-captain/skill-preinstall-check) |
| [主动助手](skills/proactive-assistant/) | 任务收尾固定汇报四段与风险，主动提醒截止与矛盾，对外动作先征求同意 | [`proactive-assistant`](https://skillhub.cn/skills/@indiv-captain/proactive-assistant) |

### 开发者与运维（分组索引）

56 个，都在 `skills/` 下，逐条的中文名、一句话、slug 见 [docs/SKILLS.md](docs/SKILLS.md#开发者与运维)。带脚本的那些不装 Agent 也能当命令行工具直接跑，见下文「命令行 30 秒上手」。

| 分组 | 个数 | 包含 |
|---|---|---|
| [研发总入口与方案评审](docs/SKILLS.md#研发总入口与方案评审) | 2 | 研发全能助手、技术方案评审官 |
| [上线与发布检查](docs/SKILLS.md#上线与发布检查) | 14 | 上线体检、上线检查清单、Changelog 生成器、数据库迁移风险、K8s 配置检查、Compose 配置体检、nginx 配置体检、.env 一致性检查、多环境配置对比、多语言文案键检查、依赖漏洞体检、依赖过期检查、开源协议合规检查、CI 配置审查 |
| [线上排查与可观测](docs/SKILLS.md#线上排查与可观测) | 13 | 线上排查简报、日志突变检测、日志时间线重建、日志模板聚类、访问日志统计、慢查询分析、Prometheus 规则体检、HTTP 健康巡检、TLS 证书巡检、域名解析巡检、轻量 HTTP 压测、HAR 性能分析、cron 表达式解释器 |
| [代码与仓库治理](docs/SKILLS.md#代码与仓库治理) | 12 | 迭代周报生成器、Git 提交信息生成器、提交信息规范检查、PR 描述生成、仓库泄密自查、CODEOWNERS 建议、代码热点与知识集中度、git 分支清理助手、测试覆盖缺口、flaky 测试识别、技术债标记盘点、GitHub 操作 |
| [接口与契约](docs/SKILLS.md#接口与契约) | 8 | 接口契约回归、接口差分测试、curl 转代码、OpenAPI 破坏性变更检查、接口文档生成、JSON Schema 推断、JWT 解码与体检、建表 SQL 结构对比 |
| [数据与文本处理](docs/SKILLS.md#数据与文本处理) | 2 | 正则中文解释、日志与数据脱敏 |
| [Agent 与技能开发](docs/SKILLS.md#agent-与技能开发) | 5 | Agent 工程、技能编写、技能体检、SkillHub 发布助手、连接器构建助手 |

### 工程实践复刻系列（分组索引）

59 个，都在 `ported/skills/` 下：来自成熟的外部开源项目，不是逐字翻译，每个都做了中文化与场景适配，逐个目录附 `ATTRIBUTION.md` 写明来源、许可证与改动。逐条清单见 [docs/SKILLS.md](docs/SKILLS.md#工程实践复刻系列)。

| 分组 | 个数 | 包含 |
|---|---|---|
| [需求与方案](docs/SKILLS.md#需求与方案) | 9 | 工程实践技能系列·总入口、需求头脑风暴与设计、需求盘问官、需求访谈（一次一问）、创意打磨（发散→收敛→一页纸）、规格驱动开发（先 Spec 后代码）、需求→Spec→任务拆解、决策问卷生成、一次性原型（逻辑 / UI） |
| [文档研究与学习](docs/SKILLS.md#文档研究与学习) | 5 | 文档协作写作三阶段、文档与 ADR、一手来源研究、没听懂，重讲一遍、学习工作台（教我一门技能） |
| [计划与执行](docs/SKILLS.md#计划与执行) | 8 | 实施计划与任务拆解、编写实施计划、执行实施计划、增量实现（薄切片）、源驱动开发（官方文档为准）、导航图（大事拆决策工单）、工单分诊状态机、人工步骤向导生成器 |
| [测试调试与验证](docs/SKILLS.md#测试调试与验证) | 10 | 测试驱动开发（红-绿-重构）、接缝驱动 TDD、浏览器 DevTools 测试、完成前验证门禁、约束驱动开发（CONSTRAINTS.md）、质疑驱动开发（对抗复审）、系统化排错与分诊、Bug 诊断法、系统化调试四阶段、性能优化（先测量再优化） |
| [代码设计与评审](docs/SKILLS.md#代码设计与评审) | 8 | API 与接口设计、深模块设计（接口·接缝·可测性）、架构加深体检（HTML 报告）、前端 UI 工程（生产级·无障碍）、代码化简（行为不变）、五轴代码评审、代码评审（双轴）、接收代码评审意见 |
| [Git 工作流](docs/SKILLS.md#git-工作流) | 4 | Git 工作流与版本管理、Git 工作树隔离工作区、合并冲突解决、开发分支收尾 |
| [上线运维与安全](docs/SKILLS.md#上线运维与安全) | 5 | CI/CD 与自动化门禁、上线发布（清单·灰度·回滚）、下线与迁移（扩展-收缩）、可观测性与埋点、安全加固（威胁建模到 LLM 安全） |
| [Agent 与上下文工程](docs/SKILLS.md#agent-与上下文工程) | 10 | 上下文工程基础、上下文工程（规则文件与预算）、上下文退化诊断、上下文压缩策略、Agent 记忆系统设计、面向 Agent 的工具设计、给 Agent 写文档（技能与规则文件）、会话交接单、并行派发子代理、子代理驱动开发 |

---

## 怎么用

### A. WorkBuddy / SkillHub

两条路，都不需要你自己打包：

1. **SkillHub**（[skillhub.cn](https://skillhub.cn/)）：180 个技能都在 `indiv-captain` 名下，技能页有「安装到本地 Agent」按钮；
   装了官方 CLI 也可以 `skillhub install <slug> --namespace indiv-captain`（为什么要带 `--namespace` 见开头）。
   slug 与目录名不完全一致（例如 `release-checklist` 的线上 slug 是 `release-checklist-git`），
   对照见 [docs/SKILLS.md](docs/SKILLS.md)：中文名链接到源目录，最后一列是 slug。
2. **本地目录**：把 `skills/<name>/` 整个目录放进 WorkBuddy 的技能目录。

如果你要把自己改造过的版本发到 WorkBuddy 开放平台，注意平台解析器对 frontmatter 有额外必填字段
（`version` / `display_name` / `display_name_en` / `description_zh` / `description_en`），
逐条实测记录在 [docs/platform-notes.md](docs/platform-notes.md)，打包用 `python3 tools/pack.py`。

### B. 纯命令行，不装任何 Agent

**这是最被低估的一条路。**180 个里有 54 个自带可执行脚本，其中 40 个只要有 `python3` 就能跑
（标准库，不用 pip），可以直接当 CI 步骤、cron 任务或者临时排查工具用：

```bash
python3 skills/<技能名>/scripts/<脚本>.py --help
```

大多数脚本都支持 `--json`（机器可读）和非零退出码（CI 门禁）。三个例外要说明：
`openapi-breaking-diff`、`openapi-to-markdown`、`release-readiness-check` 在**输入是 YAML 时**需要 PyYAML，
输入 JSON 时不需要；`iteration-report`、`release-checklist` 有 PyYAML 就用、没有就退回内置的极简解析器。

### C. Claude Code / OpenClaw 等支持 `SKILL.md` 的 Agent

技能遵循 [Agent Skills 开放标准](https://docs.openclaw.ai/tools/skills)（`SKILL.md`）。把技能目录软链或复制进 Agent 的技能目录即可，Agent 会按 `description` 自动触发：

```bash
# Claude Code
ln -s "$PWD/skills/release-readiness-check" ~/.claude/skills/release-readiness-check

# OpenClaw
ln -s "$PWD/skills/release-readiness-check" ~/.agents/skills/release-readiness-check
```

想一次装一整组，照着 [docs/SKILLS.md](docs/SKILLS.md) 的表格挑目录批量软链就行。

### 仓库结构

```
skills/             原创技能：139 个目录，其中 121 个在线上
ported/skills/      中文复刻：60 个目录，其中 59 个在线上；逐个附 ATTRIBUTION.md，保留原许可证
ported/connectors/  CLI-Anything 连接器（mermaid、drawio）
skillkit/           技能作者的命令行工具箱：起草、体检、打包、排期、看数据
docs/               技能索引、系列文章、平台实测记录、指标口径
tools/              打包、校验、发布、指标抓取脚本
```

---

## 命令行 30 秒上手（研发类技能）

不用装 Agent，不用配环境，clone 下来就能跑。下面三条命令**都是实跑输出**（绝对路径较长，用 `…` 缩短）。

```bash
git clone https://github.com/po-et/workbuddy-skills.git && cd workbuddy-skills
```

### 1. 上线体检：这次发布能不能上？

一条命令把 Dockerfile、K8s 清单、SQL 迁移、OpenAPI 兼容、`.env` 配置五项一起查完，给一个三态结论。

```bash
python3 skills/release-readiness-check/scripts/release_check.py ../your-service --strict
```

```text
上线体检 · …/demo-service
  Dockerfile 体检         high 1 / warn 2 / info 5
  K8s 清单体检            high 0 / warn 5 / info 7
  SQL 迁移风险            high 0 / warn 0 / info 1
  OpenAPI 破坏性变更      不适用：没有找到 openapi*/swagger* 规范文件，本项不适用
  .env 一致性             high 2 / warn 0 / info 4

合计：high 3 / warn 7 / info 17；无法判断 0 项
门禁：不建议上线
报告：…/demo-service/release-report.md
```

`--strict` 下退出码为 `1`，可以直接接在 CI 里当发布门禁。报告里每条都带文件、行号和改法：

```text
- **[HIGH]** `DF006` · `Dockerfile:L5` — ENV 中疑似把敏感值写进镜像：API_TOKEN
  - → 改法：镜像层会永久保留该值；改用运行时注入（-e / secrets）或 BuildKit 的 --mount=type=secret
- **[HIGH]** `missing` · `.env.production` — .env.production 缺少示例中登记的 DB_PASSWORD
```

注意「无法判断」不等于「通过」：子脚本跑挂了、旧规范是空的，都会拦住门禁而不是放行。

### 2. curl 转代码：抓包完直接出代码

浏览器 DevTools 里 Copy as cURL，粘进来，出 8 种语言的请求代码，**凭据自动改读环境变量**。

```bash
python3 skills/curl-to-code/scripts/curl_to_code.py \
  "curl -X POST https://api.example.com/v2/issues \
   -H 'Authorization: Bearer abc123' -H 'Content-Type: application/json' \
   -d '{\"title\":\"支付超时\",\"severity\":\"P1\"}'"
```

````text
# POST https://api.example.com/v2/issues
· 请求头 2 个，请求体 json，不跟随重定向

## python-requests
```python
import os
import requests

url = "https://api.example.com/v2/issues"
headers = {
    "Authorization": "Bearer " + os.environ["API_TOKEN"],
    "Content-Type": "application/json",
}
payload = {
    "title": "支付超时",
    "severity": "P1",
}

resp = requests.post(url, headers=headers, json=payload, timeout=30, allow_redirects=False)
resp.raise_for_status()
```

## 环境变量（原值未写入代码）
  Authorization        → $API_TOKEN          原值 ***（6 字符）
````

`--all` 出全部 8 种语言（requests / urllib / fetch / axios / net-http / HttpClient / PHP curl / 可读 curl）。

### 3. 访问日志统计：昨晚到底谁在拖后腿

```bash
python3 skills/access-log-stats/scripts/access_log_stats.py access.log --group-ids --top 6
```

```text
共 4000 行（无法解析 0）；状态码：2xx 3723，3xx 65，4xx 32，5xx 180
高峰时段：17/Sep/2026:21（1840 次）

## 请求量 Top 6
        次数     占比   5xx    错误率     p50     p95     p99    >慢  接口
      1416  35.4%    93  6.57%     141     272     740     0  GET /api/v2/orders/:id
       810  20.2%     0   0.0%      47      86      89     0  GET /api/v2/users/:id/profile
       603  15.1%    40  6.63%    1076    1894    5096   327  GET /api/v2/search
       469  11.7%    47 10.02%     394    1214    1999    28  GET /api/v2/checkout
       371   9.3%     0   0.0%      10      19      20     0  GET /static/app.js
       331   8.3%     0   0.0%       3       5       5     0  GET /health
```

`--group-ids` 把路径里的数字和 UUID 归并成 `:id`，否则按接口聚合会被 ID 打散。支持标准输入，
`zcat access.log.*.gz | python3 …/access_log_stats.py -` 也行。

---

## 研发类技能：为什么是这些

AI 编程工具已经解决了「写代码」。但一个研发团队里，真正吃时间又没人愿意干的，是写代码之外的部分：

| 活 | 现状 | 每周耗时（估） |
|---|---|---|
| 迭代周报 / 向上汇报 | 手工拼 git log 和工单 | 1-2 小时 |
| 上线检查清单 | 每次重写，或者干脆不写 | 0.5-1 小时 |
| 线上问题排查取证 | 人肉在日志/监控/变更间跳 | 每次事故 15 分钟起 |
| 需求转技术方案 | 从零写 | 2-4 小时 |

这些活有个共同点：**流程固定、数据分散、产出有标准格式**。正好是 Agent 的主场。

而且它们是一个体系，不是一堆独立工具——一个技能的产出可以直接当下一个的输入：

```
iteration-report ──迭代区间──> release-readiness-check ──高风险项──> incident-brief
   本期交付了什么                  上线前查什么              出事时先查什么
```

三者共享同一套输出契约：结论可溯源、数据缺口单列、判断性内容显式标记。
这是「技能体系」与「技能合集」的区别，展开见 [docs/skills-strategy.md](docs/skills-strategy.md)。

---

## 设计原则

这几条主要针对研发类技能（尤其是带脚本的那些），也是它们和「又一个 prompt 合集」的区别：

1. **零依赖** —— 能用标准库就不引第三方；不要 API Key、不要登录态、不联内网。带脚本的 54 个里，40 个只需要 `python3`。
2. **一条命令出结果** —— 不做需要来回对话才能用的技能。一条命令进去，一份结构化报告出来。
3. **可作 CI 门禁** —— 检查类技能都支持 `--json` 与非零退出码，能直接卡在合并/发布前。
4. **中文优先** —— 描述、输出、报告全中文，术语保留英文原词（`P99`、`breaking change`、`bus factor` 不硬译）。
5. **可追溯，不编造** —— 每条结论挂得上原始数据（commit hash、文件行号、日志行）；数据缺失就写「数据缺失」，
   缺口单列一节。排查类技能只给排序过的候选 + 反证，**不替人下根因结论**。
6. **脚本做事实，模型做判断** —— 统计、采集、渲染全部脚本化。既可复现，也省 token。
7. **复刻必署名** —— 只搬 MIT / Apache-2.0，逐个附 `ATTRIBUTION.md`，写明来源、许可证、改了什么。

---

## 安全与合规

- 技能**不包含任何内网地址、凭证、生产数据**。凭证一律从环境变量读，配置里只写变量名。
- 内部系统对接走 `file` provider 或独立私有适配器包，不入本仓库。
- `incident-brief`、`access-log-stats`、`log-*` 系列会读日志，使用云端模型前先跑 `sensitive-data-mask` 脱敏。
- `http-bench-lite` 对非本地目标必须显式确认；`git-branch-cleanup` 只生成删除脚本，不自动删任何东西。
- 安装任何第三方技能前先读代码。**技能就是可执行代码。**

---

## 相关文档

- **[技能索引 docs/SKILLS.md](docs/SKILLS.md)** —— 线上 180 个的完整清单：分组、中文名、一句话、slug
- [skillkit](skillkit/README.md) —— 技能作者的命令行工具箱：`new` / `lint` / `build` / `doctor` / `budget` / `stats` / `pitfalls`
- [系列文章 docs/articles/](docs/articles/) —— 生态观察、使用案例与 SkillHub 平台实测（发布配额、下载量、搜索排名）
- [生态缺口分析](docs/ecosystem-gap-analysis.md) —— 什么值得搬、什么不值得，带证据
- [SkillHub 增长打法](docs/skillhub-growth.md) —— 平台机制实测与发布节奏
- [指标口径与快照](docs/metrics/README.md) —— 能拿到哪些数、拿不到哪些数，以及为什么
- [平台实测记录](docs/platform-notes.md) —— 开放平台 / SkillHub 的字段要求与上传限制
- [Skills 策略](docs/skills-strategy.md) —— 为什么不做「技能合集」而做「技能体系」

关于下载量：截至 2026-09-23 的快照（[`docs/metrics/status-ns-2026-09-23.json`](docs/metrics/status-ns-2026-09-23.json)，按 `indiv-captain` 命名空间读取），
168 个 slug（2026-09-23 前上线的那批，尚无 2026-09-24 新增 12 个的下载数据）**累计下载 3229 次**，收藏、评论、安装量全部为 0。按我们的实测，下载增量主要来自平台抓取（全员基线）与榜单曝光，
而不是技能内容本身（见 [下载量机制](docs/metrics/2026-09-21-下载量机制.md)、[曝光假说检验](docs/metrics/2026-09-21-曝光假说检验.md)），
所以**不能用来比较技能之间的真实需求差异**。

---

## 贡献

欢迎提技能。提交前请读 [CONTRIBUTING.md](CONTRIBUTING.md)，几条硬性要求：

- 目录名 == `SKILL.md` 里的 `name`；`description` 要同时覆盖「做什么」和「什么时候用」（这是触发机制）
- 正文 < 5000 tokens，更长的内容拆到 `references/` 按需加载
- 逻辑优先写成 `scripts/` 下的脚本，不要写成长篇提示词
- 依赖写进 `metadata.openclaw.requires.bins`
- 不得包含任何内网地址、凭证、token、生产数据、真实用户信息
- 移植他人技能必须附 `ATTRIBUTION.md`，且只搬 MIT / Apache-2.0

发布前可以用本仓库自己的技能自检：`python3 skills/skill-lint/scripts/skill_lint.py <技能目录>`。

## 协议

- 原创部分：代码 [MIT](LICENSE)，文档 [CC BY 4.0](LICENSE-CONTENT)
- `ported/skills/` 下各技能：沿用上游许可证（MIT 59 个、Apache-2.0 1 个），各目录自带 `ATTRIBUTION.md`
- `ported/hookify-workbuddy/`、`ported/connectors/`：沿用原项目 Apache-2.0，各目录自带 LICENSE 与 ATTRIBUTION.md

## 其它

- `buddy-apps/devops-buddy/` —— 「研发效能 Buddy」应用配置包（Buddy 应用需企业认证，个人开发者不能创建）。
  校验：`python3 tools/check_buddy_app.py buddy-apps/devops-buddy`；调研见 [docs/buddy-app-plan.md](docs/buddy-app-plan.md)
- 个人开发者能走的全部提交/曝光渠道与当前状态：[docs/channels.md](docs/channels.md)
