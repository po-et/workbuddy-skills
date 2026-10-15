# 晨报生成成功，原始待办也要保留

这是维护者侧的**本地脚本回归案例**。全部输入为合成数据，没有 WorkBuddy 客户端执行、真人试用、真实日程或用户增长证据。

晨报只选出今天需要看的事项。把晨报写回原始待办，会让没有出现在今日摘要里的未来任务丢失；成功退出不等于原件得到保护。

## 三行输入，一处路径差异

[原始合成输入](todo.synthetic.txt)固定把 `2026-10-15` 当作今天：

```txt
- 完成合成日报 截止:2026-10-15 !
- 准备合成下月计划 截止:2026-11-01
- 10:00-11:00 合成项目会议
```

11 月 1 日的任务不会进入这份今日晨报。这符合摘要的选择范围，但它仍应留在原始待办里。三次执行分别使用新的临时合成副本，避免前一次覆盖影响后一次结果。

| 执行 | 输出位置 | 退出码 | 输入哈希不变 | 输入仍有 11 月 1 日事项 |
|---|---|---:|---|---|
| 旧版 0.1.1 | 与待办输入同一路径 | 0 | 否 | 否 |
| 新版 0.1.2 | 与待办输入同一路径 | 2 | 是 | 是 |
| 新版 0.1.2 | 独立的新文件 | 0 | 是 | 是 |

旧版测试只在临时目录中处理这三行合成数据：返回 0 后，待办被替换为经过筛选的晨报，未来事项随之从原始文件消失。新版拒绝同源输出，返回 2 并在标准输出中保留可查看的晨报；另存到新文件时返回 0，原始待办保持不变。

正常新输出的实际文件见 [brief.md](brief.md)。摘要本身依然没有 11 月 1 日事项；修复解决的是原始输入被覆盖的问题，没有把今日摘要改成全部待办清单。

## 安全复跑新版

已安装 SkillHub CLI 时，可安装本作者的[晨间简报](https://skillhub.cn/skills/@indiv-captain/morning-briefing)，核对实际版本为 0.1.2。保留已有本地修改，避免强制覆盖：

```bash
skillhub install morning-briefing --namespace indiv-captain --dir "$HOME/.workbuddy/skills"
```

[公开版本与五份包文件核验](../../docs/metrics/morning-release-verified-2026-10-15.json)已完成；安装及下载不等于客户端完成任务。

在仓库根目录运行，输出文件名须尚不存在：

```bash
mkdir -p out
python3 skills/morning-briefing/scripts/brief.py examples/morning-preservation/todo.synthetic.txt 2026-10-15 --out out/morning-preservation-20261015.md
```

预期退出码为 0。输出包含当天日报与 10:00–11:00 会议，原始合成输入仍保留 11 月 1 日事项。如果这个输出文件已经存在，请换一个新名字，脚本会拒绝覆盖。

可单独核对公开输入的 SHA256：

```bash
python3 -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('examples/morning-preservation/todo.synthetic.txt').read_bytes()).hexdigest())"
```

预期为 `1ea8c2088c8ce151e2033e215eaf3711d5710113a6243b8d50dd8d0190ed1a3d`。

## 记录与边界

[verification.json](verification.json)记录三次实际退出码、执行前后的输入哈希、未来事项是否保留及新输出哈希。旧版来源是提交 `437f2f5` 中的 `skills/morning-briefing/scripts/brief.py`，仅临时提取执行，没有把旧脚本复制到本案例。

| 脚本 | SHA256 |
|---|---|
| 旧版 0.1.1 | `4b7e0980cc2aca94646fb0dcbbba2913d478160ca6572cd4758c1be2b0ad9d5c` |
| 新版 0.1.2 | `eeba3243e4348a8b6d9b3a235766cc2eb859d2115ca49a3b9fe205e8e59ca08c` |

新版源码在三次测试前后哈希一致。旧版只作用于临时合成副本，公开输入与正常输出是本次执行的实际字节。这个案例验证的是所列路径与输入条件，不能代替其他路径别名、链接、并发或文件系统条件的独立测试。
