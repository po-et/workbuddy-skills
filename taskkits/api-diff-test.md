# 接口差分：先发现回归，再验证修复

适合核对两个 HTTP 环境的同一批响应。此包包含接口差分技能 **0.1.1**、原始脚本、合成订单与验证入口。

## 跑一个完整案例

先解压并进入此目录。需要 **Python 3.9+**；全部使用标准库，无需安装依赖、注册账号或克隆整个仓库。

```sh
python3 start.py --demo --out-dir ./result
```

Windows 若没有 `python3` 命令，可将它替换为 `py -3`。本包只做过发布记录中列明环境的执行验证。

演示启动两台本机回环 HTTP 服务，只向 `127.0.0.1` 发送合成订单 GET 请求，不连接外部端点、不读取凭据。系统须允许创建本地监听端口；被沙箱禁止时会明确失败。

打开 `result/demo/regressed.md`，应发现：金额、商品数量、布尔类型、缺失字段四类差异。`repaired.md` 应显示修复后的响应一致。`result/verification.json` 仅在这些预期和源文件未被修改均得到核对后标记 `demo_verified: true`。

## 用自己的接口

先准备脱敏的 `cases.json`（参考 `skill/references/cases.example.json`），并核对两个端点的执行范围。已启动的本地服务可这样比较：

```sh
python3 skill/scripts/api_diff.py --a http://127.0.0.1:8001 --b http://127.0.0.1:8002 --cases cases.json --md own-diff.md --out own-diff.json
```

原脚本的完整边界与外部访问参数见 [skill/SKILL.md](skill/SKILL.md)。外部环境或写方法需已获相应授权，再明确使用原脚本对应参数。凭据只从 `API_DIFF_HEADERS` 环境变量读取；分享输出前检查业务敏感字段。

原脚本退出码：`0` 响应一致且均为 2xx；`1` 差异或请求失败；`2` 输入、忽略规则或范围无效。差异是否符合业务预期需要你判断。

## 给 Agent 使用

支持访问本地文件的 WorkBuddy 或其他 Agent，可读取 `skill/SKILL.md`，先执行上面的合成案例，再处理你授权的输入。可直接使用脚本，无需 Agent 或 SkillHub。

`--out-dir` 必须是不存在的新目录，空目录也会被拒绝。再次运行请换成 `./result-2`，不会覆盖旧结果。

## 结果与反馈

入口保留原脚本 stdout、stderr 和退出码；原始 `verification.json`、差分 JSON/Markdown 在 `result/demo/`。包来源与逐文件 SHA256 见 `kit-manifest.json`；作者与许可见 [ATTRIBUTION.md](ATTRIBUTION.md)。

若完成或遇到失败，可自愿提交[技能使用反馈](https://github.com/po-et/workbuddy-skills/issues/new?template=task-kit-feedback.md)，注明技能版本、环境、任务是否完成及可公开的最小输入。也可复制 `FEEDBACK.md` 的内容。没有自动上报或遥测；不要上传凭据、个人或保密材料。维护者演示不代表你的真实环境已验证。
