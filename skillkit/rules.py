"""规则表与平台常量 —— 全工具唯一的真相源。

这里的每一条都尽量标注了出处与置信度：
  * 「实测」= 我们自己上传/发布时被平台拒过或接受过，有报错原文；
  * 「文档」= 平台公开文档写明；
  * 「推测」= 从观测现象反推，尚未被平台确认，**需确认**。

改规则只改这个文件。子命令不要内联魔法数字或正则。
"""

import re

# ---------------------------------------------------------------- 基础格式

#: slug / name 的合法形态：小写 kebab-case
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
#: 语义化版本 x.y.z（平台只认三段式，不接受 1.0 或 1.0.0-beta）
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

SLUG_MIN_LEN = 2
SLUG_MAX_LEN = 128

# ---------------------------------------------------------------- 字段要求

#: 开放平台解析器强制必填（缺任意一个直接解析失败）。
#: 来源：2026-09-15 上传实测报错原文 + /docs/skill 官方文档。
REQUIRED_FIELDS = (
    ("description", "官方文档必填，解析器强制"),
    ("version", "官方文档必填，解析器强制；重传必须递增"),
    ("description_zh", "官方文档必填，解析器强制"),
    ("description_en", "官方文档必填，解析器强制"),
    ("display_name", "文档未记载，但解析器强制：「缺少 Skill 中文展示名」"),
    ("display_name_en", "文档未记载，但解析器强制：「缺少 Skill 英文展示名」"),
)

#: 官方文档写必填、但实测解析器没拦的字段 —— 只给 WARN。
SOFT_REQUIRED_FIELDS = (
    ("author", "官方文档必填；实测解析器未强制，建议填开发者昵称"),
)

#: SkillHub（skillhub.cn）发布副本的必填 frontmatter 字段。
SKILLHUB_REQUIRED = ("slug", "version", "displayName")
#: SkillHub 建议字段（缺失只给 WARN）。
SKILLHUB_RECOMMENDED = ("summary", "license", "homepage")

#: description 长度上限（实测解析器报「description 超过 1024 字符」）。
DESCRIPTION_MAX = 1024
#: summary 长度上限（SkillHub 摘要；超长本工具自动截断）。
SUMMARY_MAX = 200
#: examples_zh / examples_en 每种语言最多 3 条（实测报错：「examples_zh 最多 3 个示例，当前 4 个」）。
EXAMPLES_MAX = 3
EXAMPLE_FIELDS = ("examples_zh", "examples_en")

# ---------------------------------------------------------------- 打包与文件

#: 不允许出现在包里的目录/文件名。
JUNK_NAMES = frozenset(
    {".git", ".DS_Store", "__pycache__", "node_modules", ".venv", "__MACOSX"}
)
#: 复制发布副本时直接忽略的通配符。
COPY_IGNORE_GLOBS = ("__pycache__", ".DS_Store", "*.pyc", "*.pyo", "*.pyd")

#: SkillHub 上传拒收无扩展名文件（实测 400「不允许的文件类型: LICENSE」）。
#: 这几个是最常见的肇事者，build 时直接删掉，许可证信息改走 frontmatter 的 license 字段。
EXTENSIONLESS_DROP = ("LICENSE", "NOTICE", "ATTRIBUTION", "COPYING")

#: 技能 zip 上限 3MB；连接器/专家 20MB（开放平台页面实测）。
SKILL_ZIP_MAX = 3 * 1024 * 1024
CONNECTOR_ZIP_MAX = 20 * 1024 * 1024

#: 疑似密钥 / 内网信息的模式。命中即 FAIL —— 发上去就是公开的。
SECRET_PATTERNS = (
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"sk-[A-Za-z0-9]{20,}", "API key"),
    (r"skh_[0-9a-f]{40,}", "SkillHub token"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"AKIA[0-9A-Z]{16}", "AWS key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY", "私钥"),
    (r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b", "私有 IP"),
    (r"\.(?:corp|internal|intranet)\.", "内网域名"),
)
SECRET_RE = tuple((re.compile(p), label) for p, label in SECRET_PATTERNS)

#: 打分时用的密钥模式，刻意比 SECRET_PATTERNS 窄：只认凭据本身。
#: 正文里举例写 10.0.0.1 / example.internal. 很常见，那是 WARN 级的打包问题，
#: 不该按「泄密」从质量分里扣 10 分。
SCORE_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}"
    r"|skh_[0-9a-f]{40,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)

#: 中日韩统一表意文字，用来判断描述/示例里的中文关键词。
CJK_RE = re.compile(r"[一-鿿]")

# ---------------------------------------------------------------- 打分维度

#: 五个维度，各 20 分，总分 100。与 skills/skill-lint 的口径保持一致。
SCORE_DIMENSIONS = ("可发现性", "结构", "可执行性", "合规", "示例")

#: description 里出现这些词，说明作者写了「什么时候用」。
TRIGGER_WORDS = ("当用户", "用于", "适用", "使用", "Use when", "when the user", "触发", "时使用")

#: 正文应覆盖的四类小节，以及各自的近义标题。
SECTION_HINTS = {
    "何时用": ["何时", "什么时候", "适用", "When to Use", "用于"],
    "流程": ["流程", "步骤", "第 1 步", "第1步", "Process", "Step"],
    "产出": ["输出契约", "输出", "产出", "交付", "Output", "验收", "Verification"],
    "边界": ["禁止", "红线", "红灯", "不做", "不用", "Red Flags", "Common Mistakes", "常见问题"],
}

DESC_LEN_OK = (80, 600)       # description 舒适区间（字符）
BODY_LEN_OK = (1500, 12000)   # 正文舒适区间（字符）
TAGS_GOOD = 6                 # tags 达到这个数量给满分
TAGS_OK = 3

# ---------------------------------------------------------------- 发布配额

#: 以下四个默认值里，CAP 与 WINDOW 是**推测值，需确认**（平台不返回配额字段）。
BUDGET_CAP_DEFAULT = 100        # 滚动窗口内成功发布次数上限（推测）
BUDGET_WINDOW_HOURS = 24        # 滚动窗口长度，小时（推测）
BUDGET_INTERVAL_SECONDS = 75    # 单次发布间隔，实测够用
BUDGET_RESERVE_DEFAULT = 10     # 给重试与失败留的余量
BUDGET_BATCH_SIZE = 25          # 单批上限
BUDGET_BATCH_GAP_MINUTES = 60   # 批间隔
BUDGET_BACKOFF_MINUTES = (10, 20, 40)  # 限流后依次等待的分钟数，对同一项重试

# ---------------------------------------------------------------- 指标接口

STATS_HOST_DEFAULT = "https://api.skillhub.cn"
STATS_USER_AGENT = "skillkit/{version} (+read-only)"
STATS_SLEEP_MIN = 1.3           # 相邻请求最小间隔，低于此值实测容易触发读限频
STATS_EVAL_DIMENSIONS = ("adaptability", "convention", "effectiveness", "reliability", "trust")

# ---------------------------------------------------------------- 坑点表

#: 每条：id / 现象 / 规则 / 证据 / 置信度（实测 | 文档 | 推测）/ skillkit 的处理方式。
#: README「这个工具替你避开的坑」一节与 `skillkit pitfalls` 都读这张表。
PITFALLS = (
    {
        "id": "extensionless-file",
        "现象": "上传 400：不允许的文件类型: LICENSE",
        "规则": "SkillHub 拒收无扩展名文件；许可证只能写在 frontmatter 的 license 字段里",
        "证据": "2026-09-17 上传实测报错原文",
        "置信度": "实测",
        "skillkit": "build 自动删除 LICENSE/NOTICE/ATTRIBUTION/COPYING；lint 对其它无扩展名文件给 WARN",
    },
    {
        "id": "parser-required-fields",
        "现象": "解析失败：缺少 Skill 中/英文展示名、中/英文描述、版本号",
        "规则": "display_name / display_name_en 官方文档没写，解析器强制；"
                "description / description_zh / description_en / version 也必填",
        "证据": "2026-09-15 上传实测逐条报错",
        "置信度": "实测",
        "skillkit": "new 模板预置全部字段；lint 缺任一项判 FAIL",
    },
    {
        "id": "strict-yaml-colon",
        "现象": "mapping values are not allowed in this context",
        "规则": "平台用严格 YAML 解析器：未加引号的标量里出现「: 」直接解析失败，必须整体加双引号",
        "证据": "2026-09-16 专家包 agent frontmatter 实测",
        "置信度": "实测",
        "skillkit": "lint 逐行扫描并指出行号",
    },
    {
        "id": "version-must-increase",
        "现象": "包内版本号 \"0.1.0\" 必须大于当前最新版本 \"0.1.0\"",
        "规则": "一次成功解析就会在服务端创建草稿并占用 name；重传必须先递增 version，草稿版本也算数",
        "证据": "2026-09-15 第三次上传实测",
        "置信度": "实测",
        "skillkit": "lint 恒定给一条提醒 WARN；doctor 在结论里重复一次",
    },
    {
        "id": "examples-max-3",
        "现象": "examples_zh 最多 3 个示例，当前 4 个",
        "规则": "examples_zh / examples_en 每种语言最多 3 条；字段本身可选，但会显示为「试试这样问我」",
        "证据": "2026-09-15 第二次上传实测",
        "置信度": "实测",
        "skillkit": "lint 超过 3 条判 FAIL，缺失给 WARN",
    },
    {
        "id": "semver-three-parts",
        "现象": "version 校验不过",
        "规则": "只接受三段式 x.y.z",
        "证据": "官方文档 + 上传实测",
        "置信度": "文档",
        "skillkit": "lint / build 都用同一个 SemVer 正则校验",
    },
    {
        "id": "slug-global-unique",
        "现象": "发布报 409 slug 冲突",
        "规则": "SkillHub 的 slug 全网唯一，先到先得；冲突时只能换名重发，重试没用",
        "证据": "2026-09-17 批量发布实测",
        "置信度": "实测",
        "skillkit": "build 支持 --slug / --map 换名；建议带用途后缀降低撞车概率",
    },
    {
        "id": "publish-quota-rolling",
        "现象": "发布频率过高；换未改动的对照技能也拦",
        "规则": "发布限额不是按自然日重置。09-17 约第 100 次成功发布后全面拦截，"
                "+1h、+14.5h（跨本地日与 UTC 日）再试仍拦，同期读接口正常",
        "证据": "2026-09-17/18 实测；「滚动 24 小时窗口、上限约 100 次」是最符合的解释",
        "置信度": "推测（需确认）",
        "skillkit": "budget 用 --cap/--window 建模，两个默认值都标注为推测值",
    },
    {
        "id": "failed-requests-cost-quota",
        "现象": "本地没校验就发，失败几次后配额见底",
        "规则": "失败的发布请求一样消耗配额 —— 不要拿线上额度当 linter",
        "证据": "2026-09-17 实测",
        "置信度": "实测",
        "skillkit": "doctor 就是为这条存在的：先本地跑完再进发布队列",
    },
    {
        "id": "throttle-retry-same-item",
        "现象": "被限流后跳过去发下一个，额度更快见底",
        "规则": "遇「发布频率过高」对同一项等 10/20/40 分钟重试；连续三次被限判定配额耗尽，停止本轮",
        "证据": "2026-09-17 实测节奏",
        "置信度": "实测",
        "skillkit": "budget 生成的 bash 模板内置这套退避，且不跳项",
    },
    {
        "id": "cli-filters-stats",
        "现象": "skillhub search / skill reports 看不到下载量",
        "规则": "downloads/installs/stars 本来就在响应体里，是 CLI 打印前把字段筛掉了；"
                "直接 GET /api/v1/skills/{slug} 就能拿到（该接口对 CLI 本身也是匿名可读）",
        "证据": "读已安装 CLI 源码 skills_store_cli.py 确认（2026-09-18）",
        "置信度": "实测",
        "skillkit": "stats 直接走详情接口，不加任何鉴权头",
    },
    {
        "id": "no-views-metric",
        "现象": "想看浏览量，找不到",
        "规则": "浏览量/PV 平台不提供：三个只读接口、rankings 字段表、网页详情页都没有这个字段；"
                "stars 是收藏计数，不是 1-5 星评分",
        "证据": "2026-09-18 接口 + 网页双向核对",
        "置信度": "实测",
        "skillkit": "stats 只报接口真的返回的字段，不编派生指标",
    },
    {
        "id": "downloads-is-agent-invocation",
        "现象": "上架很久也没量，新技能 4 天却进前百",
        "规则": "downloads 极可能约等于「Agent 自动调用次数」，而不是「有人点了下载」；"
                "决定量级的是描述触发面有多宽，不是上架时长（前 100 样本 r=0.06）",
        "证据": "2026-09-21 排行榜前 100 分析 + 官方 Q&A 第 12 条措辞",
        "置信度": "推测（需确认）",
        "skillkit": "lint 的「可发现性」维度就在量这件事：description 是否写清触发时机与同义词",
    },
    {
        "id": "trigger-surface-ethics",
        "现象": "为了流量把接不住的场景也写进触发面",
        "规则": "触发面里的每一类场景，正文必须有对应处理方法；写不出方法的场景不许写进去",
        "证据": "自设伦理边界（docs/metrics/2026-09-21-下载量机制.md）",
        "置信度": "自设规则",
        "skillkit": "lint 会检查示例与 description 关键词是否对得上，对不上要么改描述要么补正文",
    },
    {
        "id": "clawhub-rejects-bytecode",
        "现象": "ClawHub 发布被拒",
        "规则": "ClawHub 直接拒收 .pyc/.pyo/.pyd（安全扫描器暂时解析不了字节码）；"
                "但它接受无扩展名文件 —— 和 SkillHub 正好相反",
        "证据": "docs/clawhub-notes.md（2026-09-18）",
        "置信度": "文档 + 实测",
        "skillkit": "build 复制副本时统一清掉 __pycache__ 与字节码文件",
    },
)
