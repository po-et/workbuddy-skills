# 纪要标注输入契约

编译器接受原转写文本和 UTF-8 JSON 标注，输出可用纪要及待办文件。标注可由助手或人整理；脚本不生成或判断自然语言含义。首次用附带 `assets/sample-notes.json` 对照原稿即可，不需要额外安装。

## 顶层

```json
{
  "schema_version": "1",
  "meeting": {"title": "项目周会", "date": null},
  "decisions": [],
  "actions": [],
  "open_questions": []
}
```

所有顶层字段必填，数组可以为空；不接受未知字段或重复 JSON 键。`meeting.date` 是用户报告的 YYYY-MM-DD 会议日期或 null，不从文件时间、今天或截止日期反推会议日期。未知日期不会阻止生成文件。

## 每条事项及出处

三种数组中的每条都有 `id`、`text`、`state`、`sources`，可选 `review_note` 为整理者说明。ID 在全包内唯一，文本非空。`state`：

- 决议、待办：`confirmed`（输入明确记录确认）、`proposed`（建议）、`conditional`（有条件）、`cancelled`（已取消）、`disputed`（有分歧）。
- 未决问题：只用 `open`。

```json
{
  "id": "D1",
  "text": "保留差异清单。",
  "state": "confirmed",
  "sources": [{"start_line": 3, "end_line": 4, "quote": "林晓 00:00:05\n就这么定：保留差异清单。"}]
}
```

`sources` 至少一项。行号从 1 开始，为含首尾的整数范围，空行也计数；多行 `quote` 以 LF（`\n`）连接，必须与全部所选行逐字相同，不能省略条件、删除说话人或润色原话。CRLF 输入按行读取时不把 CR 放入 quote，输入 SHA 仍对原始字节计算。

对同一事项，收集前后相关发言、反对、条件、更正和撤回，多个片段分多处 sources。不要求片段连续，但不能只拿早先的表态遗漏后续撤回；脚本只能校验已提供片段，不能发现没有标注的后文。`text` 是改写，脚本不验证其语义，也不从沉默、角色头衔或权限推断确认。

## 待办额外必填字段

| 字段 | 值与限制 |
|---|---|
| `owner` | 原文明写的负责人文本或 null；匿名编号可原样保留并标身份待确认，不能猜成姓名 |
| `owner_source` | owner 为 null 时为 null；否则是相同出处结构，必须包含 owner 原文且处于该事项 sources 行号范围内 |
| `due_text` | 截止原话或 null，例如「明天」「2026-10-16」；必须在 due_source 原文出现 |
| `due_date` | YYYY-MM-DD 或 null；只有 due_source 原文按此格式明确写出的日期才可填 |
| `due_source` | 两个截止字段均为 null 时为 null；否则是原文出处，须处于该事项 sources 范围内 |

```json
{
  "id": "A1", "text": "补充样本。", "state": "confirmed",
  "owner": null, "owner_source": null,
  "due_text": "明天", "due_date": null,
  "sources": [{"start_line": 7, "end_line": 8, "quote": "发言人1 00:00:35\n我来补一份样本，明天再讨论。"}],
  "due_source": {"start_line": 7, "end_line": 8, "quote": "发言人1 00:00:35\n我来补一份样本，明天再讨论。"}
}
```

未报负责人用 null →「待认领」。截止未知用 null →「待确认」。相对期限保留 due_text，due_date 为 null；编译器不换算，即使给了会议日期也一样。若已由用户解释相对期限，可另在正文清楚标注用户解释和原始表达，本契约不伪装为原文中的绝对日期。

## 校验状态与限制

- `anchors_validated`：引用、行号和输入格式通过检查；不代表人类审批、会议语义核验或发送授权。
- `needs_review`：存在负责人、截止信息缺口；标为 confirmed 的引用含字面条件/建议/否定词；同一引用出现多个日期；或标注有条件/建议/分歧。
- 每条保留输入 `state`，另列 `review_flags`。已确认决议列表仅收未触发提示的 confirmed 决议；取消、条件、建议及带提示的记录仍完整保留在另外的节中。

字面提示可能误报，例如「不反对」或两个日期分别用于不同事项；需要结合上下文核对。没有命中也可能存在未列入词表的表达或后续撤回。脚本不号称 NLP 判定、承诺识别、身份推断或截止解析。

原转写、标注 JSON 的 SHA-256 都保留在 minutes.json。CSV 所有用户文本单元格做公式前缀防护，Markdown 转义 HTML/链接/表格符号；JSON 保存原文，不作为代码运行。报告是来源于标注的交付，不意味着全体参会人认可。

生成成功包括带核对项的稿件，退出 0；无效输入或无法写文件退出 2，验证失败不创建报告目录；手动中断退出 130。输出目录须不存在，原输入和已有报告均不覆盖。
