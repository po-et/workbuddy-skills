# 用 WorkBuddy 完成一个能核对的任务

选择一个你确实要交付的结果，先用合成输入复跑，再替换成你有权使用的数据。这里的案例由维护者在本机执行，不能作为真实客户或 WorkBuddy 对话成功的证明。

## 1. 安装到正确位置

已有 SkillHub CLI 时，安装命令同时指定作者和 WorkBuddy 技能目录：

```bash
# 工程验收
skillhub install api-diff-test --namespace indiv-captain --dir "$HOME/.workbuddy/skills"

# 办公报表，两项技能一起用
skillhub install excel-processing --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
skillhub install report-making --namespace indiv-captain --dir "$HOME/.workbuddy/skills"

# 录屏复盘
skillhub install video-frame-extract --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
```

CLI 与目录依据 [SkillHub 官方安装说明](https://skillhub.cn/install/skillhub.md)。默认安装根目录是 `./skills`，必须改成当前 Agent 的目录；其他 Agent 请按官方说明替换。本轮隔离安装实际生成 `@indiv-captain/api-diff-test/` 子目录，六个文件与 0.1.1 上传副本相同；本机以 CLI 打印位置为准。安装后重启 WorkBuddy，在新任务中显式调用技能，核对实际读取的版本；安装检查本身不证明客户端已调用。已有同名目录时先核对作者与版本，不直接加 `--force` 覆盖。

WorkBuddy 自带市场也能在「专家·技能·连接器 → 技能」中安装，见[官方技能说明](https://open.workbuddy.cn/docs/skill)。SkillHub 发布与 WorkBuddy 开放平台审核是两个独立流程，搜索不到本作者的技能时可按上述命令安装；不要把同名技能当作本仓库版本。

## 2. 选一份完整交付

| 工作 | 先复跑什么 | 需要的环境 | 检查什么 |
|---|---|---|---|
| 接口迁移差分 | [本地双服务示例](../skills/api-diff/) | Python 3；只访问示例本机服务 | 失败被发现、修正后通过、忽略路径可见；错误响应不能算通过 |
| Excel → 业务报表 | [合并到报告完整示例](../examples/office-report/) | Python 3、已有 openpyxl | 列顺序对齐、来源行、缺失保留、汇总核对、异常原因待查 |
| 录屏 → 复盘画面 | [抽帧操作与示例](../skills/video-frame-extract/SKILL.md) | Python 3、ffmpeg、ffprobe | 画面时间点、联系表、原视频未改；画面不等于音频转写 |

本仓库命令在仓库根目录运行。使用 SkillHub 安装包时，入口目录是 `~/.workbuddy/skills/@indiv-captain/<slug>/`；接口在平台的 slug 是 `api-diff-test`，仓库源目录是 `skills/api-diff`。办公完整示例属于仓库案例，两个技能包各自包含对应工具。

直接复制给 WorkBuddy 的任务见[试用任务](try-a-skill.md)。如果依赖缺失，先按技能说明补齐；不要把脚本不能启动解释为任务已经完成。

## 3. 记录实际完成和再次使用

通过[使用反馈](https://github.com/po-et/workbuddy-skills/issues/new?template=skill-feedback.md)留下一条可核对的记录：实际 slug 与版本、最小公开输入、结果文件或失败步骤、是否完成了任务，以及第二次是否仍需要它。实际测量过用时再写用时。

安装、读取技能、下载包、维护者演示和独立用户完成任务分别记录。我们不把下载计数预先当作用户数，也不把本机演示当作真实 WorkBuddy 操作经历。
