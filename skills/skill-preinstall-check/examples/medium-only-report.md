# 示例：只有中、低风险信号时的检查报告

**示例**（样例目录是为演示构造的，扫描输出是 `scripts/skill_scan.py` 的实际运行结果）

## 对话

用户：「帮我检查一下这个技能目录，脚本里有没有偷偷联网或删文件。在 ~/待检查/weather-lite。」

助手先通读 SKILL.md，回答第 2 步的三个问题：

- 它让助手做什么？运行 `python3 weather.py 城市名` 查当天天气。
- 有没有要求自动执行、跳过确认？没有。
- 有没有要求对用户隐瞒？没有。

再运行 `python3 scripts/skill_scan.py ~/待检查/weather-lite`，退出码 0：

```text
[中] 网络请求 | weather.py:1 | import json, os, sys, urllib.parse, urllib.request
[中] 读取环境变量 | weather.py:3 | key = os.environ.get("WEATHER_KEY", "")
[中] 网络请求 | weather.py:4 | city = urllib.parse.quote(sys.argv[1] if len(sys.argv) > 1 else "北京")
[中] 网络请求 | weather.py:6 | with urllib.request.urlopen(url, timeout=10) as resp:
[低] 出现网址 | SKILL.md:8 | 查询时运行 python3 weather.py 城市名；接口文档见 https://api.example.com/docs 。
[低] 出现网址 | weather.py:5 | url = "https://api.example.com/v1/weather?city=%s&key=%s" % (city, key)

扫描 2 个文件；风险信号（按行计）：高 0，中 4，低 2
关键词静态扫描只能提示风险信号，不是安全认证；没有信号也不等于安全。
```

然后逐条打开 weather.py 看上下文：第 1、4 行只是导入模块和给城市名编码，第 6 行请求的就是第 5 行拼出来的天气接口；第 3 行只读一个名为 WEATHER_KEY 的变量，SKILL.md 的 description 写明了要用户自己配置它。脚本里没有删除文件或写文件的语句。

## 交付

> **检查范围**：weather-lite，用户本地文件，无版本号；2 个文件；已通读 SKILL.md 并做脚本扫描；不是 SkillHub 来源，没有平台报告。
>
> **结论**：只有中、低风险信号，已逐条核对：6 条可以解释，0 条无法解释。是否安装由你决定。
>
> | 级别 | 位置 | 原文 | 判断 |
> |---|---|---|---|
> | 中 | weather.py:1 | `import … urllib.request` | 可以解释：查天气需要联网 |
> | 中 | weather.py:3 | `os.environ.get("WEATHER_KEY", "")` | 可以解释：只读说明里写明的一个接口密钥，没有遍历全部环境变量 |
> | 中 | weather.py:4 | `urllib.parse.quote(…)` | 可以解释：给城市名编码，不发请求 |
> | 中 | weather.py:6 | `urllib.request.urlopen(url, timeout=10)` | 可以解释：请求第 5 行的天气接口，域名与功能一致 |
> | 低 | SKILL.md:8 | 接口文档网址 | 可以解释：文档链接 |
> | 低 | weather.py:5 | 天气接口网址 | 可以解释：密钥只发给这个天气接口，没有发往别处 |
>
> **未检查**：无。
>
> **复跑**：`python3 scripts/skill_scan.py ~/待检查/weather-lite`，退出码 0。
>
> 提醒：这份结论只说明没有发现无法解释的信号，不代表安全；技能更新后要重新检查。
