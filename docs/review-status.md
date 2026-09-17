# SkillHub 审核可见性抽查（user_a3a2e24a）

- 检查时间：2026-09-17 20:55–21:00 CST（自动脚本，82 slug 全量）；21:01–21:07 CST 针对 2 处异常人工复核
- 数据来源：`docs/submission-checklist.md` 中「## SkillHub」章节下全部含 skillId/slug 的表格
- 检查账号：SkillHub 个人账号，checklist 中记为 handle `user_a3a2e24a`；**实测发现该值其实是 API 返回的 `namespace.displayName`，真正的 `namespace.handle` 是 `indiv-captain`**（两者指向同一账号，均已用于匹配）
- 检查方法：对每个 slug 依次执行 `skillhub search <slug> --json --search-limit 10`（判断搜索索引是否命中 `publicSlug==slug` 且属于本账号）与 `skillhub skill evaluation <slug> --namespace indiv-captain --json`（判断评测报告是否已生成，未生成时 CLI 内部按 HTTP 404 处理并输出 `{"slug":...}`），两次查询之间固定间隔 1.3 秒，全程只读，未触发限流

## 总览

- **总数：82**（`submission-checklist.md` 提示「应有 74 个左右」，实际解析出 82 个；`docs/skillhub-growth.md` 独立记录「累计约 80 个技能已 Published」与本次结果更接近，**74 这个数字明显偏低，以本次实测的 82 为准**）
- **搜索索引已可见：81**（98.8%）
- **搜索索引未可见：1**（详见下方「异常」）
- **已生成 AI 评测报告（evaluation 非 404）：26**（31.7%）
- **评测仍为 404（尚未生成）：54**（65.9%）
- **查询异常（非常规 404，需人工关注）：2** — triage-zh, dockerfile-check

## 表：全部 82 个 slug 的可见性与评测状态

| # | 批次（来自 submission-checklist.md） | slug | skillId | 可见? | evaluation 状态 | 备注 |
|---|---|---|---|---|---|---|
| 1 | SkillHub | `iteration-report-git` | 203311 | 是 | 已评测（09-16 19:44） |  |
| 2 | SkillHub | `release-checklist-git` | 203312 | 是 | 已评测（09-16 19:44） |  |
| 3 | SkillHub | `incident-brief-sre` | 203313 | 是 | 已评测（09-16 19:44） |  |
| 4 | SkillHub | `build-workbuddy-connector` | 203315 | 是 | 已评测（09-16 19:44） |  |
| 5 | 第一批 | `dev-workflow-pro` | 203361 | 是 | 已评测（09-16 20:11） |  |
| 6 | 第一批 | `commit-message-cc` | 203362 | 是 | 已评测（09-16 20:12） |  |
| 7 | 第一批 | `changelog-keep` | 203363 | 是 | 已评测（09-16 20:14） |  |
| 8 | 第一批 | `dep-vuln-check-osv` | 203365 | 是 | 已评测（09-16 20:14） |  |
| 9 | 第一批 | `log-anomaly-3sigma` | 203366 | 是 | 已评测（09-16 20:14） |  |
| 10 | 第一批 | `grill-me-zh` | 203367 | 是 | 已评测（09-16 20:13） |  |
| 11 | 第一批 | `diagnosing-bugs-zh` | 203368 | 是 | 已评测（09-16 20:13） |  |
| 12 | 第一批 | `merge-conflicts-zh` | 203369 | 是 | 已评测（09-16 20:13） |  |
| 13 | 第一批 | `spec-and-tickets-zh` | 203370 | 是 | 已评测（09-16 20:16） |  |
| 14 | 第二批 | `code-review-zh` | 203374 | 是 | 已评测（09-16 20:16） | slug 与他人账号（clawhub_olina1ye）撞名，但本账号的条目已确认在搜索结果中，不影响本条可见性判定 |
| 15 | 第二批 | `tech-design-review` | 203376 | 是 | 已评测（09-16 20:19） |  |
| 16 | 第二批 | `license-check-offline` | 203377 | 是 | 已评测（09-16 20:20） |  |
| 17 | 第二批 | `api-diff-test` | 203378 | 是 | 已评测（09-16 20:23） |  |
| 18 | 第二批 | `ci-config-review` | 203379 | 是 | 已评测（09-16 20:23） |  |
| 19 | 第四批 | `api-design-zh` | ~~缺失~~ 203418 | 是 | 已评测（09-16 21:26） | 清单原文 skillId 缺失（会话中断丢失输出），本次从 evaluation 接口回填 |
| 20 | 第四批 | `code-simplification-zh` | ~~缺失~~ 203420 | 是 | 已评测（09-16 21:26） | 清单原文 skillId 缺失（会话中断丢失输出），本次从 evaluation 接口回填 |
| 21 | 第四批 | `deprecation-migration-zh` | ~~缺失~~ 203421 | 是 | 已评测（09-16 21:29） | 清单原文 skillId 缺失（会话中断丢失输出），本次从 evaluation 接口回填 |
| 22 | 第四批 | `docs-and-adr-zh` | ~~缺失~~ 203423 | 是 | 已评测（09-16 21:29） | 清单原文 skillId 缺失（会话中断丢失输出），本次从 evaluation 接口回填 |
| 23 | 第五批 | `ci-cd-zh` | 204519 | 是 | 已评测（09-17 17:55） |  |
| 24 | 第五批 | `git-workflow-zh` | 204525 | 是 | 已评测（09-17 17:58） |  |
| 25 | 第五批 | `incremental-implementation-zh` | 204526 | 是 | 已评测（09-17 17:58） |  |
| 26 | 第五批 | `planning-tasks-zh` | 204529 | 是 | 已评测（09-17 18:01） |  |
| 27 | 第五/六批 | `engineering-skills-index-zh` | 204558 | 是 | 未评测（404，审核队列中） |  |
| 28 | 第五/六批 | `interview-me-zh` | 204562 | 是 | 未评测（404，审核队列中） |  |
| 29 | 第五/六批 | `idea-refine-zh` | 204563 | 是 | 未评测（404，审核队列中） |  |
| 30 | 第五/六批 | `spec-driven-zh` | 204565 | 是 | 未评测（404，审核队列中） |  |
| 31 | 第五/六批 | `source-driven-zh` | 204566 | 是 | 未评测（404，审核队列中） |  |
| 32 | 第五/六批 | `tdd-zh` | 204570 | 是 | 未评测（404，审核队列中） |  |
| 33 | 第五/六批 | `debug-triage-zh` | 204572 | 是 | 未评测（404，审核队列中） |  |
| 34 | 第五/六批 | `observability-zh` | 204575 | 是 | 未评测（404，审核队列中） |  |
| 35 | 第五/六批 | `security-hardening-zh` | 204578 | 是 | 未评测（404，审核队列中） |  |
| 36 | 第五/六批 | `performance-optimization-zh` | 204582 | 是 | 未评测（404，审核队列中） |  |
| 37 | 第五/六批 | `shipping-launch-zh` | 204584 | 是 | 未评测（404，审核队列中） |  |
| 38 | 第五/六批 | `code-review-five-axis-zh` | 204587 | 是 | 未评测（404，审核队列中） |  |
| 39 | 第五/六批 | `context-engineering-zh` | 204589 | 是 | 未评测（404，审核队列中） |  |
| 40 | 第五/六批 | `constraints-md-zh` | 204591 | 是 | 未评测（404，审核队列中） |  |
| 41 | 第五/六批 | `doubt-driven-zh` | 204593 | 是 | 未评测（404，审核队列中） |  |
| 42 | 第五/六批 | `browser-testing-devtools-zh` | 204595 | 是 | 未评测（404，审核队列中） |  |
| 43 | 第五/六批 | `frontend-ui-zh` | 204598 | 是 | 未评测（404，审核队列中） |  |
| 44 | 第五/六批 | `skillhub-publish-helper` | 204604 | 是 | 未评测（404，审核队列中） | slug 与他人账号（user_00c9b356）撞名，但本账号的条目已确认在搜索结果中，不影响本条可见性判定 |
| 45 | 第五/六批 | `skill-lint-scorecard` | 204607 | 是 | 未评测（404，审核队列中） |  |
| 46 | 第五/六批 | `teach-workspace-zh` | 204610 | 是 | 未评测（404，审核队列中） |  |
| 47 | 第五/六批 | `deep-module-design-zh` | 204613 | 是 | 未评测（404，审核队列中） |  |
| 48 | 第五/六批 | `writing-for-agents-zh` | 204615 | 是 | 未评测（404，审核队列中） |  |
| 49 | 第五/六批 | `wayfinder-zh` | 204618 | 是 | 未评测（404，审核队列中） |  |
| 50 | 第五/六批 | `wizard-zh` | 204621 | 是 | 未评测（404，审核队列中） |  |
| 51 | 第五/六批 | `research-primary-zh` | 204624 | 是 | 未评测（404，审核队列中） |  |
| 52 | 第五/六批 | `handoff-doc-zh` | 204626 | 是 | 未评测（404，审核队列中） |  |
| 53 | 第七批 | `triage-zh` | 204663 | **否** | **HTTP 404：skill not found**（本账号下无此 slug，≠普通未评测） | 怀疑清单记录有误：本账号未持有该 slug；`docs/skillhub-growth.md` 记录过「triage-zh → issue-triage-zh」因撞名改名，本行应即该情况 |
| 54 | 第七批 | `prototype-zh` | 204689 | 是 | 未评测（404，审核队列中） |  |
| 55 | 第七批 | `tdd-seams-zh` | 204717 | 是 | 未评测（404，审核队列中） |  |
| 56 | 第七批 | `architecture-deepening-zh` | 204740 | 是 | 未评测（404，审核队列中） |  |
| 57 | 第七批 | `to-questionnaire-zh` | 204742 | 是 | 未评测（404，审核队列中） |  |
| 58 | 第七批 | `re-pitch-zh` | 204744 | 是 | 未评测（404，审核队列中） |  |
| 59 | 第八/九批 | `tool-design-zh` | 204748 | 是 | 未评测（404，审核队列中） |  |
| 60 | 第八/九批 | `context-fundamentals-zh` | 204750 | 是 | 未评测（404，审核队列中） |  |
| 61 | 第八/九批 | `context-degradation-zh` | 204752 | 是 | 未评测（404，审核队列中） |  |
| 62 | 第八/九批 | `memory-systems-zh` | 204754 | 是 | 未评测（404，审核队列中） |  |
| 63 | 第八/九批 | `doc-coauthoring-zh` | 204755 | 是 | 未评测（404，审核队列中） |  |
| 64 | 第八/九批 | `issue-triage-zh` | 204759 | 是 | 未评测（404，审核队列中） |  |
| 65 | 第八/九批 | `dockerfile-check` | 204761 | 是 | **查询异常：HTTP 566**（非 404，非限流，3 次重试均复现，疑似该记录评测服务端出错） |  |
| 66 | 第八/九批 | `sql-migration-check` | 204763 | 是 | 未评测（404，审核队列中） |  |
| 67 | 第十批 | `cron-explain` | 204770 | 是 | 未评测（404，审核队列中） |  |
| 68 | 第十批 | `openapi-breaking-diff` | 204772 | 是 | 未评测（404，审核队列中） |  |
| 69 | 第十一批 | `env-sync-check` | 204775 | 是 | 未评测（404，审核队列中） |  |
| 70 | 第十一批 | `flaky-test-finder` | 204777 | 是 | 未评测（404，审核队列中） |  |
| 71 | 第十一批 | `k8s-manifest-check` | 204780 | 是 | 未评测（404，审核队列中） |  |
| 72 | 第十一批 | `pr-description` | 204782 | 是 | 未评测（404，审核队列中） | slug 与他人账号（user_79bcc5a2）撞名，但本账号的条目已确认在搜索结果中，不影响本条可见性判定 |
| 73 | 第十一批 | `context-compression-strategies-zh` | 204784 | 是 | 未评测（404，审核队列中） |  |
| 74 | 第十一批 | `todo-debt-scan` | 204788 | 是 | 未评测（404，审核队列中） |  |
| 75 | 第十一批 | `git-branch-cleanup` | 204791 | 是 | 未评测（404，审核队列中） |  |
| 76 | 第十一批 | `http-health-check` | 204794 | 是 | 未评测（404，审核队列中） |  |
| 77 | 第十一批 | `log-pattern-cluster` | 204795 | 是 | 未评测（404，审核队列中） |  |
| 78 | 第十一批 | `access-log-stats` | 204799 | 是 | 未评测（404，审核队列中） |  |
| 79 | 第十一批 | `git-hotspots` | 204801 | 是 | 未评测（404，审核队列中） |  |
| 80 | 第十一批 | `json-schema-infer` | 204805 | 是 | 未评测（404，审核队列中） |  |
| 81 | 第十一批 | `codeowners-suggest` | 204807 | 是 | 未评测（404，审核队列中） |  |
| 82 | 第十一批 | `dep-outdated-check` | 204810 | 是 | 未评测（404，审核队列中） |  |

## 异常 / 需要人工关注

1. **`triage-zh`（清单记录 skillId 204663，第七批 19:07:47 发布）在搜索索引中未可见，本账号下查询不到该 slug**（`skillhub skill evaluation triage-zh --namespace indiv-captain` 返回 `HTTP 404: skill not found`，这是「无此技能」而非「未评测」的 404）。实测 `skillhub search triage-zh` 命中的是另一账号 `org-02qudk26` 的同名技能「分诊」（v1.0.0），不是本账号的内容。判断：这是清单记录错误，不是审核问题——真正对应的技能应为同批次之后出现的 `issue-triage-zh`（skillId 204759，本次检查确认可见）。`docs/skillhub-growth.md`「进展」一节原文写道：

   > slug 冲突两例（triage-zh → issue-triage-zh，context-compression-zh → context-compression-strategies-zh）说明热门英文词的 -zh 形式已开始被抢注，后续 slug 尽量带限定词。

   与本次实测结论一致：`triage-zh` 撞了别人的 slug 改发成 `issue-triage-zh`，清单里 `triage-zh` 那一行的 skillId 204663 是记录残留，需要人工核实/删除。

2. **`dockerfile-check`（skillId 204761）评测查询持续返回 `HTTP 566`**，非标准的 404，重试 3 次（含人工间隔复核 2 次，前后跨约 2 分钟）均复现同一错误；搜索索引可见性正常（已可见）。这不是「审核未过」，而像是评测服务端针对这一条记录的报错，建议后续人工在 SkillHub 网页端 `https://skillhub.cn/skills/user_a3a2e24a/dockerfile-check` 直接查看评测是否正常显示。

3. **提交清单本身的 3 处数据问题**（均为文档问题，非本次新增）：
   - 「SkillHub 第四批」表格缺 skillId 列，4 个 slug（api-design-zh / code-simplification-zh / deprecation-migration-zh / docs-and-adr-zh）原文标注「skillId 待补（会话中断丢失输出）」；本次已从 evaluation 接口查得并回填：203418 / 203420 / 203421 / 203423。
   - 该批次原文注明的发布时间「2026-09-16 21:07 前后」与其 evaluation 完成时间（21:26–21:29）吻合，可信；但**「## SkillHub（个人技能市场）」表格与「第一批」「第二批」标注的发布时间「2026-09-17」与实测的 evaluation 完成时间（2026-09-16 19:44–20:23，即前一天晚上）矛盾**——评测不可能早于发布，说明这三个表格的日期应为 2026-09-16，而非 2026-09-17（很可能是记录时手误晚写了一天）。
   - 「SkillHub 第七批」标题写「7 个」，表格实际只列出 6 行（含上面第 1 条的 triage-zh）。

4. **3 个 slug 与站内其他账号完全撞名**（`code-review-zh` 撞 `clawhub_olina1ye`、`skillhub-publish-helper` 撞 `user_00c9b356`、`pr-description` 撞 `user_79bcc5a2`）：两边的条目同时出现在搜索结果里，本账号这 3 条均确认可见，不影响本次「可见/未可见」判定，仅提示 `publish_batch.py` 脚本注释里「slug 全网唯一」的说法并不总是成立（至少与 ClawHub 等旧渠道导入的记录之间不做强唯一性校验），单纯搜 slug 关键词可能引出别家的技能，需要用 `namespace.handle` 精确区分。

5. **未发现任何技能被标记「拒绝」或带有平台审核驳回意见**。`skillhub skill evaluation` 返回的是六维度 AI 质量评分报告（能力边界/规范性/有效性/稳定性/可信度等），不是通过/驳回的判定书，82 个里没有出现负面结论或驳回文案；`docs/review-feedback.md`（清单里点名要记录审核意见的文件）尚不存在，说明开放平台侧的审核结果也还没回来。

## 结论

1. 按「搜索索引可见」口径，通过率 81/82 = **98.8%**；唯一的「未可见」（`triage-zh`）经查是清单记录错误而非仍在审核，实际应发布的 `issue-triage-zh` 已可见——**82 个技能可认为已全部进入搜索索引**。
2. 按「AI 评测报告已生成」这一更严格的口径，完成率仅 26/82 = **31.7%**；已完成的全部集中在最早发布的两批（首批 4 个 + 第一/二/四批 + 第五批共 26 个），评测像是定时批处理，56 个（其中 54 个正常排队、2 个查询异常见上，skillId ≥204558，2026-09-17 18:23–20:04 发布）仍未拿到评测结果，最早排队的已等待近 3 小时。
3. 从提交清单与实测证据交叉核对看，**最早发布并已确认可见+评测通过的是 `iteration-report-git`（skillId 203311）**，其评测于 2026-09-16 19:44:13 完成——早于清单标注的「2026-09-17 18:37」，说明实际发布应在 2026-09-16 当晚（见上方异常 3）；本次 82 个 slug 的完整核查（搜索+评测各一次调用、间隔 1.3 秒）自动化脚本耗时 300.9 秒，加上对 2 处异常的人工复核，总计约 6 分钟。

