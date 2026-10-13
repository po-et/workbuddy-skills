# 交接盘点示例

输入：一个本地仓库，跟踪了 `README.md`、`pyproject.toml`、`tests/test_order.py`，但本规则没有找到 CI 路径。

```bash
python3 "<skill-dir>/scripts/repo_inventory.py" \
  --repo "/path/to/example-project" \
  --out-dir "/path/to/reports/example-project"
```

期望输出：报告中 `signals.readme.count` 为 1、`signals.tests.count` 为 1、`signals.ci.count` 为 0；这些文件在字节与条数上限内时具有 `hashed` 证据。具体 HEAD 和哈希取自输入仓库，示例不提供虚构值。

可用交付文字：

“盘点完成，报告位于给出的绝对路径。检测到 `tests/test_order.py`，本轮未运行测试；未发现本规则覆盖的被跟踪 CI 配置，需确认是否由外部系统维护。先确认测试入口能否运行，再决定是否补充仓库内 CI 说明。”

若 README 被修改或删除，`git.worktree.dirty` 应为 `true`；删除的 README 仍是跟踪路径，证据状态为 `missing`。不要把报告生成成功写成“仓库干净”或“交接已验收”。
