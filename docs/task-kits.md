# 下载一个任务，先得到自己的结果

> PPT 入口更新到 `task-kits-v0.1.1`，内含 PPT 技能 0.1.3，修正自动缩小误报与百分比写法漏报。[新版发布验收](metrics/task-kits-verified-2026-10-28.json)包含五份公开文件哈希与 PPT 公开下载包的实际执行。接口与报价入口保留 0.1.0；[原版发布验收记录](metrics/task-kits-verified-2026-10-21.json)。任务包版本与内含技能源版本分别标注。

选一个任务包，解压到新目录，进入**包内含 `start.py` 的目录**。可以直接用 Python，也可由支持本地文件与命令的 WorkBuddy 或其他 AI 助手执行。每包自带完整技能、脚本和合成样例，不需要克隆整个仓库、SkillHub 账号或 `pip` 安装；需要本机已有 **Python 3.9+**。包不会自动安装到任何 Agent 的技能目录。

| 你要完成的事 | 下载任务包 | 内含技能版本 | 示例要核对的结果 |
|---|---|---|---|
| 两套接口找出业务变化 | [接口差分任务包](https://github.com/po-et/workbuddy-skills/releases/download/task-kits-v0.1.0/api-diff-test-task-kit-0.1.0.zip) | `api-diff-test` 0.1.1 | 回归样例发现四处差异，修正样例一致；保留差异及退出码 |
| 两份报价核对缺项和差额 | [报价核对任务包](https://github.com/po-et/workbuddy-skills/releases/download/task-kits-v0.1.0/car-buying-checklist-task-kit-0.1.0.zip) | `car-buying-checklist` 0.1.2 | 缺项不能填零；补齐后录入范围费用为 15000 / 16500，差额 1500 |
| 已有 PPT 检查小字号 | [PPT 检查任务包 0.1.1](https://github.com/po-et/workbuddy-skills/releases/download/task-kits-v0.1.1/pptx-making-task-kit-0.1.1.zip) | `pptx-making` 0.1.3 | 原件两处小字号；修正版检查范围内无问题，两份仍各有一处字号未知；100% 不报自动缩小 |

**任务包版本不等于技能版本。** 包内 `START-HERE.md` 说明当前包的运行和输出方式；`skill/SKILL.md` 是原技能入口。接口演示会启动本机 HTTP 服务并向回环地址发 GET 请求，需要本机允许绑定端口；报价和 PPT 运行不发网络请求。全部示例都是合成输入。

## 解压后，只跑这一条

在包内含 `START-HERE.md`、`start.py`、`skill/` 的目录执行：

```bash
python3 start.py --demo --out-dir ./result
```

`result` 必须尚不存在；再次运行换一个输出目录。先看自己的本次输出，再与包内说明的预期结果比较，不把预生成示例当作本次结果。

也可以直接复制给 WorkBuddy 或其他能读取本地文件并执行命令的 Agent：

> 我已打开解压后的任务包目录。先读 START-HERE.md 和 skill/SKILL.md，再实际运行 python3 start.py --demo --out-dir ./result。已有 result 就停止并说明，不覆盖原件、脚本或旧结果，不安装依赖、不改配置。打开本次结果，列出交付文件、真实退出码、通过项与仍需确认的项。若缺少 Python、文件或端口权限，报告实际错误，不能手写一份成功结果。

这条路径是显式读取包内技能，不代表市场自动发现或已经安装技能。

## 换成自己的输入

报价包先按 `skill/references/quote-contract.md` 准备 JSON，未知字段保持 `null`；PPT 包直接提供已有 `.pptx`。以下命令分别在对应包的根目录执行，输入路径替换成自己的文件：

```bash
# 报价核对包
python3 start.py --input ./quotes.json --out-dir ./my-result

# PPT 检查包
python3 start.py --input ./slides.pptx --out-dir ./my-result
```

不要共用已有输出目录。报价结果只是所录入范围的计算，不替代选车或融资判断；PPT 检查保留未知项，不代替演示软件里的逐页查看。

接口包的真实双环境用法见包内 `skill/SKILL.md`，底层入口为 `skill/scripts/api_diff.py`，参数帮助可运行：

```bash
python3 skill/scripts/api_diff.py --help
```

接入自己有权测试的地址和用例前，核对目标、请求方法、忽略字段及输出路径。演示只用本机合成服务；不把演示通过当作整个系统迁移通过。若以后希望在新任务中长期调用原技能，可按[安装说明](start-here.md)指定作者 `indiv-captain` 与实际 Agent 目录，已有目录先核对，不强制覆盖。

## 对照下载文件的 SHA256

下载后，在 ZIP 所在目录用 Python 标准库计算哈希。例如：

```bash
python3 -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' pptx-making-task-kit-0.1.1.zip
```

将结果与该版本 Release 页面（[PPT 新版 0.1.1](https://github.com/po-et/workbuddy-skills/releases/tag/task-kits-v0.1.1)、[接口和报价入口 0.1.0](https://github.com/po-et/workbuddy-skills/releases/tag/task-kits-v0.1.0)）公布的**同名资产 SHA256**逐字对照，别拿任务包版本或文件名代替哈希。包内文件来源和许可证以包内清单为准。哈希一致说明文件与所公布副本一致，不证明独立用户使用或实际业务正确。

## 完成后，反馈完全自愿

可以提交[任务包使用反馈](https://github.com/po-et/workbuddy-skills/issues/new?template=task-kit-feedback.md)，只写：**包名和版本、想完成的任务、实际完成或卡住的结果、是否已在另一个任务中再次使用**。环境、脱敏输出摘要或截图按需补充；不要求提交业务原件、个人信息或凭据。仅计划再用，不能写成已经复用。

不提交也可以继续下载和运行。这里不自动上传输入或运行记录；下载次数、维护者验包、自愿任务反馈分别记录。
