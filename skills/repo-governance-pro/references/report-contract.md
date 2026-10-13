# 报告契约

`schema_version: 1`。文件名固定为 `inventory.json` 与 `inventory.md`；输出目录必须在输入仓库外。报告不包含仓库绝对路径，终端会返回报告绝对路径。

| 字段 | 含义 |
|---|---|
| `git.head` | 当前 commit 对象 ID；空仓库为 `null` |
| `git.branch` / `git.detached` | 分支名或 detached 状态；不包含作者或远端 |
| `git.worktree` | staged/unstaged/conflict/未跟踪路径数量、是否脏；跟踪改动路径最多 50 项 |
| `tracked` | 索引中的唯一跟踪路径数量、普通文件/符号链接/子模块计数、目录和扩展名分布 |
| `signals` | 按路径规则发现的 README、AGENTS、测试、构建、CI、依赖清单，类别路径最多 50 项 |
| `evidence` | 有界候选文件的路径、分类、Git 模式、状态、当前文件大小及 SHA-256（可读取时） |
| `limits` | 全局证据项数、单文件字节上限及省略数；截断是范围限制，不是缺失证明 |
| `snapshot` | 采集前后 HEAD、branch、跟踪索引与工作区状态是否相同；变动时标注不一致 |

路径分类只检查名称：README/AGENTS 的 Markdown、文本或 reStructuredText 文件；`test`/`tests`/`__tests__` 等目录和惯例测试文件；Makefile、Dockerfile、pom.xml 等构建文件；GitHub/GitLab/Azure/Jenkins 等 CI 文件；package.json、pyproject.toml、go.mod、Cargo.toml 等依赖清单。测试路径可能是数据或文档，构建文件可能无效。没有命中仅表示本规则未发现，不能推出整个仓库没有对应能力。

证据状态包括 `hashed`、`missing`、`symlink_skipped`、`submodule_skipped`、`too_large`、`not_regular`、`unreadable`、`safe_open_unavailable`、`changed_while_reading`。只读取普通跟踪文件；Git 冲突的多 stage 仍计为一个路径，证据哈希来自当前文件而非某一 stage。

Git 与文件读取不是原子事务。开始/结束比对不能发现发生后又恢复的变化；已脏文件继续修改也可能不改变 Git 状态。`snapshot.checks` 列出实际比对项目，读取中发现文件变化会标记不一致，但不能证明所有文件内容在整个采集期间不变。有界哈希和 `snapshot.consistent` 都不等于备份一致性证明。若需要可复现的发布验收，请使用明确 commit 的独立 checkout 并另行执行必要测试。

路径含换行或制表符时，以 JSON 字符串转义呈现；Markdown 表格会额外转义管道符和 HTML 字符，避免破坏表格或注入 HTML。用户给出的相对输出目录按当前运行目录解释，最终位置仍检查不得落入仓库。
