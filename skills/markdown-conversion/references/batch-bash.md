# 批量转换：bash 版骨架（没有 Python 时用）

优先用 `python3 {baseDir}/scripts/md_batch.py`：它多了超时、重试、写临时文件再改名、`--dry-run` 和中断保护。下面是它的前身，逻辑相同（对每个 .md 执行同一条 pandoc 命令，保持目录结构，文件名有空格也不怕，失败不静默），适合只有 bash 的环境。macOS 自带的 bash 也能跑，Windows 用 Git Bash 或 WSL。

```bash
#!/usr/bin/env bash
# 用法：bash md2docx.sh 源目录 输出目录；ref.docx 放在运行目录
set -u
src=${1:-docs}; out=${2:-build}; fail=0
mkdir -p "$out"; : >"$out/errors.log"
while IFS= read -r -d '' f; do
  rel=${f#"$src"/}; dst="$out/${rel%.md}.docx"
  mkdir -p "$(dirname "$dst")"; echo "== $rel" >>"$out/errors.log"
  if pandoc "$f" -o "$dst" --resource-path="$(dirname "$f")" --reference-doc=ref.docx 2>>"$out/errors.log"
  then echo "OK   $rel"; else echo "FAIL $rel"; fail=$((fail + 1)); fi
done < <(find "$src" -name '*.md' -print0)
echo "失败 $fail 个，警告与报错见 $out/errors.log"; exit $((fail > 0))
```

和 Python 版的差别：

| | bash 版 | md_batch.py |
|---|---|---|
| 单个文件卡死 | 一直等 | `--timeout` 秒后结束，记为 TIMEOUT |
| 失败重试 | 不重试 | `--retries` 次（默认 1，最多 2） |
| 半截文件 | 失败时可能留下 | 先写临时文件，成功才改名 |
| 没有 ref.docx | pandoc 报错 | 自动改用 pandoc 默认样式，并在日志里写明 |
| 先看会转哪些文件 | 无 | `--dry-run`，不需要 pandoc |
| Ctrl+C | 立即退出 | 已完成的保留，日志照常写出，退出码 130 |
