# WorkBuddy 实测：两份报价，缺项不能填成零

2026-10-15，由维护者的 Codex 代理操作真实 WorkBuddy **5.8.2 / Space-Bunny** 客户端，显式读取本地 `skills/car-buying-checklist/SKILL.md` 与输入契约，运行两次报价核对。两次脚本均退出 0，留下六份真实输出。本目录逐字复制客户端产物与两份合成输入，未重新编写结果。

这验证了维护者侧 AI 在客户端显式调用本地技能的交付；不是独立用户案例，也未验证 SkillHub 安装后的自动发现、真实商家报价、用户采纳或节省金额。

## 先看两次结果

| 录入范围 | A | B：另收费用未知 | B：费用补齐 |
|---|---|---|---|
| 本金 | 100000 | 100000 | 100000 |
| 总还款额 | 112000 | 110500 | 110500 |
| 总还款额之外的另收费用 | 3000 | null，待补 | 6000 |
| 已知还款差额 | 12000 | 10500 | 10500 |
| 完整录入范围贷款费用 | 15000 | null；已知小计 10500 | 16500 |
| B − A | — | 不可列完整差额 | 1500 |

完整录入范围贷款费用 = 总还款额 − 本金 + 另收费用。缺项保留 null；已知小计不能当完整成本。补齐后的 1500 只是这组输入在该范围的差额，不是融资推荐。

| 实际客户端产物 | 可读报告 | 表格复核 | 完整结构 |
|---|---|---|---|
| 第一次：费用缺项 | [Markdown](outputs/missing-fee/comparison.md) | [CSV](outputs/missing-fee/comparison.csv) | [JSON](outputs/missing-fee/comparison.json) |
| 第二次：补齐费用 | [Markdown](outputs/complete-fee/comparison.md) | [CSV](outputs/complete-fee/comparison.csv) | [JSON](outputs/complete-fee/comparison.json) |

原始输入：[缺项版本](inputs/two-quotes-missing-fee.json)、[补齐版本](inputs/two-quotes-complete.json)。全部金额均为合成数据，没有真实商家、车型或个人信息；其中税费和保险的 0 也是明确给定的演示值，不表示实际政策或报价。

## 安装或本地复跑

已有 SkillHub CLI 时，按[官方安装说明](https://skillhub.cn/install/skillhub.md)安装并核对作者、版本和实际安装位置；已存在目录时不要直接强制覆盖：

```bash
skillhub install car-buying-checklist --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
```

本次实测使用本地仓库 v0.1.2，该版本现已在 SkillHub 公开上线，[11 份发布文件哈希与两项扫描状态](../../docs/metrics/car-release-verified-2026-10-15.json)已读回。安装命令本身不证明客户端已经读取技能或自动触发成功。

已取得本仓库后，在仓库根目录运行；Python 3 标准库，无需联网或额外依赖：

```bash
mkdir -p out
python3 skills/car-buying-checklist/scripts/compare_quotes.py --input examples/car-quotes/inputs/two-quotes-missing-fee.json --out-dir out/car-quotes-missing
python3 skills/car-buying-checklist/scripts/compare_quotes.py --input examples/car-quotes/inputs/two-quotes-complete.json --out-dir out/car-quotes-complete
```

两个输出目录都必须不存在；已跑过请换新目录，脚本不会覆盖输入或已有报告。每个目录生成 `comparison.md`、`comparison.csv`、`comparison.json`。其他字段、单位及完整性规则见[输入与输出契约](../../skills/car-buying-checklist/references/quote-contract.md)。

## 可复制给 WorkBuddy 的任务

把 `<仓库绝对路径>` 换成自己的实际目录，输出目录使用新名字：

```text
请在 <仓库绝对路径> 中完成一次两份报价核对验收。先显式读取 skills/car-buying-checklist/SKILL.md 和 references/quote-contract.md（后者在同一技能目录内）。仅使用公开合成输入，不联网、不安装依赖、不读取其他个人目录或凭据，不修改源码或原始输入。

在仓库根目录确认 out 父目录存在，然后分别运行：
python3 skills/car-buying-checklist/scripts/compare_quotes.py --input examples/car-quotes/inputs/two-quotes-missing-fee.json --out-dir out/my-car-quotes-missing
python3 skills/car-buying-checklist/scripts/compare_quotes.py --input examples/car-quotes/inputs/two-quotes-complete.json --out-dir out/my-car-quotes-complete

输出目录必须是不存在的新目录，已有结果不要覆盖。读取两轮实际生成的 JSON/Markdown/CSV：第一轮 A 费用15000，B 费用null、已知小计10500、complete=false，贷款费用不能比较；第二轮 B费用16500，B减A为1500。两轮年度能耗均为1755，差额0。

保留缺项、逐字段来源、输入SHA256及计算式；核对原始输入和源码未变。只按实际文件报告结果，不把维护者合成验收写成真实客户使用、融资建议或节省金额。
```

## 核验依据与反馈

[verification.json](verification.json) 保留客户端版本、执行身份、11 份源码未变记录、两份输入 SHA256、六份产物 SHA256，以及根代理独立重跑后逐字一致的核验结果。此文件与私有验收记录逐字一致；公开内容仅含合成结果、相对路径、哈希与允许公开的客户端观察，没有原始界面会话 URL 或凭据。

原记录中 `input_relative` 指向仓库技能目录内的原始样例；本目录 `inputs/` 是这两份原件的逐字副本。`files[].path` 相对于本目录的 `outputs/`。六份输出里 `input_sha256` 与两处输入副本一致，可自行复核。

[技能源码](../../skills/car-buying-checklist/) · [比较脚本](../../skills/car-buying-checklist/scripts/compare_quotes.py) · [完整实测文章](../../docs/articles/10-WorkBuddy实测-两份报价核对.md) · [提交试用反馈](https://github.com/po-et/workbuddy-skills/issues/new/choose)

反馈只需说明实际使用版本、合成或已脱敏的输入、期望结果与实际结果；请勿上传真实合同、联系方式、账号凭据或其他个人信息。当前还没有独立用户任务完成或重复使用记录。
