---
name: skill-search-helper
description: "技能搜索——把「有没有能做某件事的技能」改写成名词搜索词，在 SkillHub 上找候选，比较匹配度、边界、作者、版本与安全报告，给出首选和备选。当用户说「有没有能…的技能」「帮我找个技能」「这几个技能哪个好」时使用。"
author: Captain
version: 0.1.0
display_name: "技能搜索"
display_name_en: "Skill Search"
description_zh: "技能搜索：把需求改写成 2–4 个名词搜索词（平台按字面匹配、不分词），用 skillhub 只读命令取候选并去掉补位条目，按匹配度、边界是否写清、作者、版本、安全报告比较，给出一个首选和一到两个备选及理由；安装命令带 namespace，用户确认后再装。"
description_en: "Turn 'is there a skill that does X' into noun search terms, pull SkillHub candidates with read-only commands, drop filler results, compare fit, stated boundaries, author, version and security reports, and recommend one pick plus one or two alternatives with a namespaced install command the user confirms."
tags:
  - "技能搜索"
  - "找技能"
  - "技能推荐"
  - "技能对比"
  - "SkillHub"
  - "技能市场"
  - "skill search"
  - "find skills"
examples_zh:
  - "有没有能帮我写请假条的技能"
  - "帮我找个技能，能把会议录音整理成纪要的"
  - "搜出来好几个请假条技能，这几个技能哪个好"
---

# 技能搜索

定位一句话：**先把需求翻译成平台搜得到的词，再按「能不能解决这件事」排序；谁发布的不加分也不减分。**

## 先判断：用户到底要什么

从对话里确定三件事，缺哪项先问哪项：

1. 对象：要处理的东西，如请假条、会议录音、Excel 表；
2. 结果：想得到什么，如写好的文书、整理好的纪要、一张图表；
3. 约束：中文还是英文、能不能联网、有没有不能上传到外部的资料。

## 流程第 1–2 步：改写搜索词，取候选

**第 1 步：改写成名词搜索词。** 平台搜索按字面匹配、不分词。实测「写请假条」只返回与请假条无关的补位技能，「请假条」才搜得到真正的请假条技能。改写规则：去掉动词和客套（写、做、生成、帮我、好用的），保留对象名词，再补一个同义词和一个上位词，凑成 2–4 个词。

```
用户原话                    搜索词
帮我写个请假条              请假条 / 请假申请 / 请假
把会议录音整理成纪要        会议纪要 / 录音转写 / 纪要
做一份给老板看的周报        周报 / 工作汇报 / 汇报
```

**第 2 步：取候选，去掉补位条目。** 单个词用只读命令：

```bash
skillhub --skip-self-upgrade search 请假条 --json --search-limit 10
```

返回的 results 里每条有 slug（形如 @作者/技能名）、name、description、version、namespace.handle（作者）。匹配结果不够时，平台会用一批与搜索词无关的常见技能补足条数——名字和描述都不含搜索词的，一律不算候选。所有词都只剩补位条目时，换同义词、上位词再搜一轮；仍然没有，就如实告诉用户。

几个词一起查、去掉补位条目、附上平台安全报告状态，用下面的只读脚本（存成 `skill_candidates.py`）：

```python
"""合并几个搜索词的 SkillHub 结果，去掉补位条目，附平台安全报告状态（只读）。
用法：python3 skill_candidates.py 请假条 请假申请 请假"""
import json, subprocess, sys

def hub(*args):
    r = subprocess.run(["skillhub", "--skip-self-upgrade", *args, "--json"],
                       capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}

found = {}
for word in sys.argv[1:]:
    for item in hub("search", word, "--search-limit", "10").get("results", []):
        if word.lower() in (item["name"] + item["description"]).lower():
            found.setdefault(item["slug"], [item, []])[1].append(word)
for slug, (item, words) in sorted(found.items(), key=lambda kv: -len(kv[1][1])):
    name = item.get("publicSlug") or slug.split("/")[-1]
    rep = hub("skill", "reports", name, "--namespace", item["namespace"]["handle"])
    status = "；".join(f"{r.get('name')} {r.get('status')}" for r in (rep.get("reports") or {}).values())
    print(f"{slug}  {item['name']}  v{item['version']}  命中：{'/'.join(words)}")
    print(f"    安全报告：{status or '查不到'}")
    print(f"    描述：{' '.join(item['description'].split())}")
print(f"共 {len(found)} 个候选（名字和描述都不含搜索词的补位条目已去掉）")
```

运行 `python3 skill_candidates.py 请假条 请假申请 请假`。单独查某个技能的平台安全报告：

```bash
skillhub --skip-self-upgrade skill reports <slug> --namespace <作者> --json
```

报告含两家实验室的结果，status 为 benign 表示平台扫描未发现问题；其他状态或查不到报告的，不进首选。

## 第 3 步：比较并推荐

| 维度 | 看什么 | 怎么判断 |
|---|---|---|
| 匹配度 | 名字和描述是否正好是用户要的对象和结果 | 专做这件事 > 顺带覆盖 > 描述里只提到一次 |
| 边界 | 描述是否写了适用范围、不做什么 | 写清的优先，只堆功能的降一档 |
| 作者 | namespace.handle，描述自称的出品方与之是否对得上 | 只用来区分同名技能，不因作者是谁加减分 |
| 版本 | version（搜索结果不带更新时间） | 只作参考：版本号高说明迭代过，不等于最近更新 |
| 安全报告 | skill reports 的两项 status | 两项都是 benign 才能做首选 |

排序以匹配度为准；匹配度相近时，再看边界是否写清、版本是否迭代过。安全报告不满足的，不做首选。同一作者用不同 slug 发的几乎相同的技能，只取一个比较。

推荐写法：

```
首选：<展示名>（@作者/slug，v版本）——理由：专门做什么；描述写清了什么边界；两项安全报告为 benign
备选：<展示名>（@作者/slug）——什么情况下选它更合适
没选：<展示名>——原因，如通用写作技能，请假条只是顺带
```

## 第 4 步：安装带 namespace，用户确认后再装

```bash
# 会下载并安装到本机，用户确认后再执行
skillhub install <slug> --namespace <作者>
```

为什么带 `--namespace`：slug 不是全平台唯一的，实测同一个 slug 下有两个不同作者各发的技能；不带作者，装到的未必是你比较过、看过安全报告的那一个。给出命令时提醒用户：装之前先看安全报告；陌生技能在第一次使用前，可以再用「安装前检查」对它的文件做一次静态扫描。

## 最常见的错误

- 拿用户原话直接搜：动词短语搜不到，只剩补位条目。
- 把补位条目当候选推荐。
- 只看名字不读描述，推荐了顺带提一句的通用技能。
- 安装命令不带 namespace，或者没问用户就直接安装。

## 输出契约

交付：所用搜索词、去掉补位后的候选数、比较表、一个首选加一到两个备选及理由、带 namespace 的安装命令，并说明「你确认后我再安装，或你自己执行」。没有合适的就直说「没找到匹配的技能」，给出换词建议，不硬推不相关的技能。

## 边界与不做什么

- 只用只读命令（search、skill reports），不自动安装、不发布、不评论。
- 推荐依据是与需求的匹配度，不偏向任何作者，包括本技能作者自己的账号 indiv-captain 发布的技能。
- 平台报告与本地扫描都只是参考，不等于绝对安全；装不装由用户决定。
- 单位电脑按单位对第三方插件的规定执行，需要审批的先走审批，拿不准的问单位 IT。
