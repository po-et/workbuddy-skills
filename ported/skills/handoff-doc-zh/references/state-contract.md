# 状态输入契约 v1

UTF-8 JSON 对象，禁止重复字段、NaN 和 Infinity。所有顶层字段必填，未知字段报错，避免拼写错误变成悄悄丢失的状态。

| 字段 | 类型与含义 |
|---|---|
| `schema_version` | 整数 `1` |
| `title`, `goal` | 非空字符串；任务名、当前目标 |
| `reported_status` | `in_progress` / `blocked` / `completed`，由输入提供 |
| `decisions` | 数组；每项 `decision`, `reason`, `source` 三个非空字符串 |
| `open_items` | 数组；每项唯一 `id`, `action`, `acceptance`；可选 `owner`，未给不猜 |
| `next_item_id` | 未完项的 ID；没有未完项时为 `null` |
| `artifacts` | 数组；每项 `path`, `role`；可选预期 `sha256`（64 位十六进制） |
| `verifications` | 数组；每项 `command`, `reported_result`, `reported_status`；可选 `observed_at`, `evidence_path` |
| `unknowns`, `suggested_skills` | 字符串数组，可为空 |

`artifact.path` 是 `--root` 下的相对路径；禁止绝对路径与 `..`。不会读取链接、目录或根目录外文件。`evidence_path` 应对应 artifacts 中的一项，不会通过执行命令补证据。

验证状态只认 `passed` / `failed` / `not_run`。已运行验证若缺观察时间或证据文件，报告记录不完整。时间需为带时区的 ISO 8601，例如 `2026-10-12T09:00:00+08:00`，禁止未来时间。记录时间和文件哈希不能证实命令真的执行过，报告始终标明它们来自输入。

错误字段只打印字段名与错误类型，避免回显原始材料。脚本不保证发现所有敏感信息；请只输入已脱敏的状态摘要，不输入日志全文或个人信息。

输出 `record_integrity` 为 `consistent` 或 `needs_review`，不是业务质量或完成度评分。未完项可以正常交接。只有“状态称 completed 却仍有未完项”等冲突需要复核。
