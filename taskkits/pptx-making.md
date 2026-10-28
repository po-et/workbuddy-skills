# PPT 体检：找到小字号，保留未知项

适合交付前检查 `.pptx` 的标题与文字样式。此包包含 PPT 制作技能 **0.1.3**、只读检查脚本与两份四页合成 PPT。

新版修正自动缩小判定：100% 字号和默认字号比例不会被报成缩小；整数 `62500` 与百分比 `62.500%` 都识别为 62.5%。只减行距不能据此判定字号缩小；不支持或无效的比例保留待核对提示。说明见 [自动缩小边界](skill/examples/autofit-boundaries.md)。

## 跑一个完整案例

先解压并进入此目录。需要 **Python 3.9+**；全部使用标准库，无需安装演示软件、依赖、注册账号或克隆整个仓库。

```sh
python3 start.py --demo --out-dir ./result
```

Windows 若没有 `python3` 命令，可替换为 `py -3`。本包只做过发布记录中列明环境的执行验证。

查看 `result/before.txt`：段落默认样式和列表样式中各有一处 **8 磅**小字，原检查脚本应返回 `3`。`result/after.txt` 中两处修正为 24 磅，原脚本应返回 `0`，仍须保留 **1 处字号未知**。显式指定为 24 磅的文字不应被父级 8 磅样式误判。

入口独立核对四页、八个文字片段、七个已确定字号、一个未知字号、两处修复和原脚本退出码，再标记 `demo_verified: true`。这条入口完成整个合成演示时返回 `0`；每次原检查的 `3/0` 保留在 `verification.json`。

## 检查自己的 PPT

```sh
python3 start.py --input ./my-deck.pptx --out-dir ./my-result
```

打开 `my-result/input.txt`；`input.json` 提供可复核的字号来源与定位。入口返回原脚本退出码：`0` 检查范围内未发现问题；`3` 已发现问题；`2` 文件无法读取。`verification.json` 保留真实退出码与输入哈希，不声称已经完成视觉验收。

本工具不修改 PPT，不解析母版、版式与主题继承；未知字号不等于合格。它不检查实际字体替换、文字重叠或裁切，仍需在演示软件中逐页预览。原技能说明见 [skill/SKILL.md](skill/SKILL.md)。

## 给 Agent 使用

支持访问本地文件的 WorkBuddy 或其他 Agent，可读取 `skill/SKILL.md`，先跑合成案例，再处理你的 `.pptx`。可直接使用脚本，无需 Agent 或 SkillHub。全过程离线，无需网络。

`--out-dir` 必须是不存在的新目录，空目录也会被拒绝。再次运行请换成 `./result-2`，不会覆盖输入或旧结果。

## 结果与反馈

入口保留原脚本的人类可读和 JSON 标准输出、stderr 与退出码。包来源与逐文件 SHA256 见 `kit-manifest.json`；作者与许可见 [ATTRIBUTION.md](ATTRIBUTION.md)。

若完成或遇到失败，可自愿提交[技能使用反馈](https://github.com/po-et/workbuddy-skills/issues/new?template=task-kit-feedback.md)，注明版本、环境、任务是否完成及可公开的最小输入。也可复制 `FEEDBACK.md`。没有自动上报或遥测；不要上传个人或保密材料。维护者演示不代表你的 PPT 已完成视觉验收。
