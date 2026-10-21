# 两份报价：缺项保留，费用算清

适合把两份已取得的报价整理为可核对表格。此包包含买车清单技能 **0.1.2**、原始离线脚本与两组合成报价。

## 跑一个完整案例

先解压并进入此目录。需要 **Python 3.9+**；全部使用标准库，无需安装依赖、注册账号或克隆整个仓库。

```sh
python3 start.py --demo --out-dir ./result
```

Windows 若没有 `python3` 命令，可替换为 `py -3`。本包只做过发布记录中列明环境的执行验证。

查看 `result/missing-fee/comparison.md`：B 的另收费用未知，应保留 `null`，贷款完整费用和差额不得当作已知。再查看 `result/complete-fee/comparison.md`：补齐费用后，合成案例 B 比 A 的录入贷款费用多 **1500 元**。入口会独立核对这些结果、真实脚本退出码和输入未变，再标记 `demo_verified: true`。

## 换成自己的报价

复制 `skill/examples/two-quotes-missing-fee.json` 为 `my-quotes.json`，只填实际取得的金额；未知项保留 `null`。字段契约见 [skill/references/quote-contract.md](skill/references/quote-contract.md)。

```sh
python3 start.py --input ./my-quotes.json --out-dir ./my-result
```

结果在 `my-result/comparison/comparison.md`、`.csv`、`.json`。`my-result/verification.json` 记录原脚本退出码与输入哈希，不会把你的输入标记为合成案例验收通过。无效输入会保留错误并返回原脚本非零退出码。

脚本仅整理录入范围和缺项，不核验报价真实性、不查税费政策、不计算 APR、不排序或推荐车型。合成报价不代表任何地区政策、真实商家或车型。

## 给 Agent 使用

支持访问本地文件的 WorkBuddy 或其他 Agent，可读取 `skill/SKILL.md`，先跑合成案例，再核对你提供的脱敏报价。可直接使用脚本，无需 Agent 或 SkillHub。全过程离线，无需网络。

`--out-dir` 必须是不存在的新目录，空目录也会被拒绝。再次运行请换成 `./result-2`，不会覆盖输入或旧结果。

## 结果与反馈

入口保留原脚本 stdout、stderr、退出码，另输出 `verification.json`；原始技能文件完整保留。来源与逐文件 SHA256 见 `kit-manifest.json`；作者与许可见 [ATTRIBUTION.md](ATTRIBUTION.md)。

若完成或遇到失败，可自愿提交[技能使用反馈](https://github.com/po-et/workbuddy-skills/issues/new?template=task-kit-feedback.md)，注明版本、环境、任务是否完成及可公开的最小输入。也可复制 `FEEDBACK.md`。没有自动上报或遥测；不要上传真实联系人、个人或保密材料。维护者演示不代表你的报价已被独立核实。
