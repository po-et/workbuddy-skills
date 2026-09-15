# 贡献指南

## 提交新技能前

1. 目录名 == `SKILL.md` 里的 `name`，小写，连字符分隔，≤64 字符
2. `description` ≤1024 字符，**祈使语态**，同时覆盖「做什么」和「什么时候用」
   - 这是技能的触发机制。所有 when-to-use 信息放 description，不要放正文
   - 正文是触发后才加载的，那时候写"什么时候用"已经晚了
   - 中文触发词要写全（用户实际会怎么说）
3. 正文 < 5000 tokens。更长的内容拆到 `references/`，按需加载
4. 逻辑优先写成 `scripts/` 下的脚本，不要写成长篇提示词
   - 脚本可复现、可测试、省额度
5. 声明依赖：`metadata.openclaw.requires.bins`
6. **要上开放平台的技能，frontmatter 还必须有**：`version`、`display_name`、`display_name_en`、`description_zh`、`description_en`（平台解析器硬性要求，实测见 docs/platform-notes.md）

## 硬性红线

- 不得包含任何内网地址、凭证、token、生产数据、真实用户信息
- 凭证只从环境变量读，配置文件里只写**环境变量名**
- 不得包含 `.git/`、`LICENSE`、`.DS_Store` 等非必要文件（SkillHub 会拒）

## 移植他人技能

允许，但必须：

1. 确认原项目协议允许再分发（MIT / Apache-2.0 / CC BY 可以）
2. 在 `SKILL.md` 底部加「出处」小节：原项目链接、原作者、原协议
3. 保留原 LICENSE 文件内容到该技能目录
4. **必须有实质改进**才提交 —— 中文化、适配 WorkBuddy、修 bug、补脚本
   - 只改个名字就重新上架的，不收

## 自检

```bash
python3 -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('skills/**/*.py', recursive=True)]"
```

提交前至少在一个真实仓库上跑通一次，把输出贴进 PR。

## 向 ported/ 贡献移植项目

`ported/` 只收"WorkBuddy 生态没有、外部已成熟"的项目。提交前对照 [docs/ecosystem-gap-analysis.md](docs/ecosystem-gap-analysis.md) 的判定表，先证明缺口存在。

每个移植目录必须有：

| 文件 | 要求 |
|---|---|
| `LICENSE` | 原项目协议全文，不得改协议 |
| `NOTICE` | Apache-2.0 项目必须；写原版权方与本派生作品版权 |
| `ATTRIBUTION.md` | 原项目链接、原作者、原协议、**逐条改动清单与原因**、实测记录、待确认项 |
| 测试 | 能离线跑的自动化测试；不能在目标客户端内验证的部分在 ATTRIBUTION 里明写 |

文件头标注"修改自 X（协议）"。CLI-Anything 类按其 `registry.json` 的 `contributors` 逐人署名，并引用其技术报告。

不收：只改名重新上架、无测试、无改动清单、协议不允许再分发（如 source-available）的项目。
