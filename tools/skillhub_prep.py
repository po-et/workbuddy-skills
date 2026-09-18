#!/usr/bin/env python3
"""生成 SkillHub（skillhub.cn）发布副本。

SkillHub 的 SKILL.md frontmatter 必填 slug / version / displayName，建议 summary / description /
tags / license / homepage（来源：skillhub.cn/tutorials 与 skillhub.cn/ai/release.md）。
开放平台版本用的是 name / display_name / description_zh 等字段，两套字段并存未验证是否互相干扰，
所以不改 skills/ 源文件，而是生成一份带 SkillHub 字段的副本到 dist/skillhub/<slug>/。

用法：python3 tools/skillhub_prep.py --out dist/skillhub [skill-name ...]
之后：skillhub publish dist/skillhub/<slug> --host https://api.skillhub.cn --dry-run
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOMEPAGE = "https://github.com/po-et/workbuddy-skills"
LICENSE = "MIT"

# slug 全网唯一，带用途后缀降低 409 冲突概率；冲突时改这里即可
SLUGS = {
    "iteration-report": "iteration-report-git",
    "release-checklist": "release-checklist-git",
    "incident-brief": "incident-brief-sre",
    "build-workbuddy-connector": "build-workbuddy-connector",
    "commit-message": "commit-message-cc",
    "changelog": "changelog-keep",
    "dep-vuln-check": "dep-vuln-check-osv",
    "log-anomaly": "log-anomaly-3sigma",
    "dev-workflow-pro": "dev-workflow-pro",
    "grill-me-zh": "grill-me-zh",
    "diagnosing-bugs-zh": "diagnosing-bugs-zh",
    "merge-conflicts-zh": "merge-conflicts-zh",
    "spec-and-tickets-zh": "spec-and-tickets-zh",
    "code-review-zh": "code-review-zh",
    "license-check": "license-check-offline",
    "api-diff": "api-diff-test",
    "ci-config-review": "ci-config-review",
    "tech-design-review": "tech-design-review",
    "code-simplification-zh": "code-simplification-zh",
    "deprecation-migration-zh": "deprecation-migration-zh",
    "api-design-zh": "api-design-zh",
    "docs-and-adr-zh": "docs-and-adr-zh",
    "ci-cd-zh": "ci-cd-zh",
    "git-workflow-zh": "git-workflow-zh",
    "incremental-implementation-zh": "incremental-implementation-zh",
    "planning-tasks-zh": "planning-tasks-zh",
    "prometheus-rule-check": "prometheus-rule-check",
    "log-timeline": "log-timeline",
    "sensitive-data-mask": "sensitive-data-mask",
    "csv-profile": "csv-profile",
    "json-diff": "json-diff",
    "regex-explain": "regex-explain",
    "har-analyze": "har-analyze",
    "curl-to-code": "curl-to-code",
    "dep-outdated-check": "dep-outdated-check",
    "codeowners-suggest": "codeowners-suggest",
    "json-schema-infer": "json-schema-infer",
    "git-hotspots": "git-hotspots",
    "access-log-stats": "access-log-stats",
    "log-pattern-cluster": "log-pattern-cluster",
    "http-health-check": "http-health-check",
    "git-branch-cleanup": "git-branch-cleanup",
    "todo-debt-scan": "todo-debt-scan",
    "pr-description": "pr-description",
    "k8s-manifest-check": "k8s-manifest-check",
    "flaky-test-finder": "flaky-test-finder",
    "env-sync-check": "env-sync-check",
    "openapi-breaking-diff": "openapi-breaking-diff",
    "cron-explain": "cron-explain",
    "sql-migration-check": "sql-migration-check",
    "dockerfile-check": "dockerfile-check",
    "doc-coauthoring-zh": "doc-coauthoring-zh",
    "memory-systems-zh": "memory-systems-zh",
    "tool-design-zh": "tool-design-zh",
    "context-compression-zh": "context-compression-strategies-zh",
    "context-degradation-zh": "context-degradation-zh",
    "context-fundamentals-zh": "context-fundamentals-zh",
    "architecture-deepening-zh": "architecture-deepening-zh",
    "tdd-seams-zh": "tdd-seams-zh",
    "prototype-zh": "prototype-zh",
    "re-pitch-zh": "re-pitch-zh",
    "to-questionnaire-zh": "to-questionnaire-zh",
    "domain-modeling-zh": "domain-modeling-zh",
    "triage-zh": "issue-triage-zh",
    "writing-for-agents-zh": "writing-for-agents-zh",
    "research-primary-zh": "research-primary-zh",
    "wizard-zh": "wizard-zh",
    "handoff-doc-zh": "handoff-doc-zh",
    "wayfinder-zh": "wayfinder-zh",
    "deep-module-design-zh": "deep-module-design-zh",
    "teach-workspace-zh": "teach-workspace-zh",
    "skill-lint": "skill-lint-scorecard",
    "skillhub-publish-helper": "skillhub-publish-helper",
    "interview-me-zh": "interview-me-zh",
    "release-readiness-check": "release-readiness-check",
    "secrets-scan": "secrets-scan",
    "config-env-diff": "config-env-diff",
    "i18n-missing-keys": "i18n-missing-keys",
    "test-coverage-gap": "test-coverage-gap",
    "brainstorming-zh": "brainstorming-spec-zh",
    "systematic-debugging-zh": "systematic-debugging-zh",
    "writing-plans-zh": "writing-impl-plans-zh",
    "executing-plans-zh": "executing-dev-plans-zh",
    "verification-before-completion-zh": "pre-completion-verification-zh",
    "subagent-driven-development-zh": "subagent-driven-development-zh",
    "dispatching-parallel-agents-zh": "parallel-agent-dispatch-zh",
    "using-git-worktrees-zh": "git-worktree-workflow-zh",
    "receiving-code-review-zh": "code-review-response-zh",
    "finishing-a-development-branch-zh": "dev-branch-finishing-zh",
    "sql-slow-query-digest": "sql-slow-query-digest",
    "api-contract-test": "api-contract-test",
    "git-commit-lint": "git-commit-lint",
    "openapi-to-markdown": "openapi-to-markdown",
    "docker-compose-check": "docker-compose-check",
    "nginx-config-check": "nginx-config-check",
    "tls-cert-check": "tls-cert-check",
    "sql-schema-diff": "sql-schema-diff",
    "jwt-inspect": "jwt-inspect",
    "http-bench-lite": "http-bench-lite",
    "dns-check": "dns-check",
}
# 源目录：默认 skills/<name>，复刻的在 ported/skills/<name>
def source_dir(name: str) -> Path:
    for base in (ROOT / "skills", ROOT / "ported" / "skills"):
        if (base / name / "SKILL.md").exists():
            return base / name
    sys.exit(f"找不到技能目录: {name}")
TAGS = {
    "iteration-report": ["周报", "迭代汇报", "Git", "研发效能"],
    "release-checklist": ["上线检查", "发布评审", "回滚", "研发效能"],
    "incident-brief": ["故障排查", "SRE", "复盘", "研发效能"],
    "build-workbuddy-connector": ["连接器", "WorkBuddy", "脚手架", "开发者工具"],
    "commit-message": ["commit", "提交信息", "Conventional Commits", "git", "commit message", "提交规范", "研发效能"],
    "changelog": ["changelog", "发布说明", "release notes", "更新日志", "版本说明", "git", "研发效能"],
    "dep-vuln-check": ["漏洞", "CVE", "依赖安全", "OSV", "供应链安全", "npm audit", "pip-audit", "SCA", "安全审计"],
    "log-anomaly": ["日志分析", "异常检测", "突变", "错误率", "故障定位", "时间序列", "SRE", "监控"],
    "dev-workflow-pro": ["研发效能", "周报", "上线", "故障排查", "commit", "changelog", "代码评审", "需求", "spec", "拆任务", "冲突", "漏洞", "复盘", "DevOps"],
    "grill-me-zh": ["需求澄清", "盘问", "grill", "方案评审", "决策", "设计", "追问", "需求分析"],
    "diagnosing-bugs-zh": ["debug", "调试", "bug", "诊断", "复现", "性能回退", "排查", "回归测试"],
    "merge-conflicts-zh": ["git", "合并冲突", "merge", "rebase", "cherry-pick", "conflict", "冲突解决"],
    "spec-and-tickets-zh": ["需求文档", "spec", "PRD", "拆任务", "工单", "用户故事", "排期", "issue", "任务拆解"],
    "code-review-zh": ["代码评审", "code review", "PR", "代码审查", "坏味道", "code smell", "重构", "合并前检查"],
    "license-check": ["开源协议", "license", "许可证", "合规", "GPL", "AGPL", "SSPL", "NOTICE", "依赖审计"],
    "api-diff": ["接口测试", "回归测试", "api diff", "差分测试", "环境对比", "发布验证", "灰度", "接口对比"],
    "ci-config-review": ["CI", "GitHub Actions", "GitLab CI", "流水线", "workflow", "安全审查", "供应链安全", "DevOps"],
    "tech-design-review": ["技术方案", "架构评审", "设计评审", "方案评审", "架构设计", "SRE", "QA", "安全评审"],
    "code-simplification-zh": ["重构", "代码化简", "可读性", "代码整洁", "refactor", "简化代码", "clean code", "代码质量"],
    "deprecation-migration-zh": ["迁移", "下线", "废弃", "数据库迁移", "expand contract", "不停机", "灰度", "绞杀者模式", "deprecation"],
    "api-design-zh": ["API 设计", "接口设计", "REST", "幂等", "接口规范", "分页", "错误码", "向后兼容", "OpenAPI"],
    "docs-and-adr-zh": ["ADR", "架构决策", "技术文档", "README", "注释规范", "文档", "documentation", "决策记录"],
    "ci-cd-zh": ["CI/CD", "GitHub Actions", "流水线", "自动化", "质量门禁", "部署", "特性开关", "回滚", "DevOps"],
    "git-workflow-zh": ["git", "分支策略", "主干开发", "原子提交", "语义化版本", "semver", "tag", "changelog", "worktree"],
    "incremental-implementation-zh": ["增量开发", "垂直切片", "小步提交", "特性开关", "实现", "迭代", "敏捷", "范围纪律"],
    "planning-tasks-zh": ["任务拆解", "实施计划", "依赖图", "排期", "估算", "检查点", "任务清单", "plan", "todo"],
    "prometheus-rule-check": ["Prometheus", "告警规则", "录制规则", "PromQL", "告警风暴", "监控治理", "lint", "SRE"],
    "log-timeline": ["日志时间线", "故障复盘", "多文件日志", "时间戳归一", "时区对齐", "事件密度", "错误爆发", "SRE"],
    "sensitive-data-mask": ["脱敏", "日志脱敏", "PII", "个人信息", "打码", "密钥清理", "对外分享", "合规"],
    "csv-profile": ["CSV", "数据画像", "数据质量", "空值率", "类型推断", "重复行", "TSV", "数据清洗"],
    "json-diff": ["JSON", "配置对比", "配置漂移", "环境差异", "diff", "接口回归", "脱敏", "CI 门禁"],
    "regex-explain": ["正则", "regex", "中文解释", "ReDoS", "灾难性回溯", "正则测试", "VERBOSE", "调试"],
    "har-analyze": ["HAR", "前端性能", "首屏优化", "瀑布流", "DevTools", "缓存头", "gzip 压缩", "SRE"],
    "curl-to-code": ["curl", "代码生成", "接口联调", "requests", "fetch", "抓包转代码", "环境变量", "研发效能"],
    "dep-outdated-check": ["依赖升级", "过期依赖", "npm outdated", "pip", "go mod", "供应链", "技术债", "版本管理"],
    "codeowners-suggest": ["CODEOWNERS", "代码归属", "评审人", "git", "GitHub", "GitLab", "团队协作", "code review"],
    "json-schema-infer": ["JSON Schema", "接口契约", "API 文档", "数据校验", "JSONL", "逆向", "schema 生成"],
    "git-hotspots": ["代码热点", "git", "bus factor", "技术债", "重构", "耦合", "知识集中", "代码质量"],
    "access-log-stats": ["访问日志", "Nginx", "access.log", "P99", "性能分析", "错误率", "QPS", "日志分析"],
    "log-pattern-cluster": ["日志分析", "日志聚类", "日志降噪", "故障排查", "ERROR", "模板", "SRE", "可观测性"],
    "http-health-check": ["健康检查", "巡检", "冒烟测试", "HTTPS 证书", "可用性", "监控", "SRE", "发布检查"],
    "git-branch-cleanup": ["git", "分支清理", "已合并分支", "陈旧分支", "仓库治理", "branch", "远端分支"],
    "todo-debt-scan": ["技术债", "TODO", "FIXME", "代码健康", "重构", "git blame", "代码审计", "周报"],
    "pr-description": ["PR 描述", "Merge Request", "代码评审", "git", "变更说明", "GitHub", "GitLab", "PR 模板"],
    "k8s-manifest-check": ["Kubernetes", "K8s", "YAML", "Deployment", "安全基线", "资源限制", "探针", "生产就绪", "lint"],
    "flaky-test-finder": ["flaky", "不稳定测试", "CI 随机失败", "JUnit", "测试报告", "pytest", "Jest", "测试质量"],
    "env-sync-check": [".env", "环境变量", "配置管理", "dotenv", "部署检查", "密钥泄露", "CI", "新人上手"],
    "openapi-breaking-diff": ["OpenAPI", "Swagger", "API 兼容", "breaking change", "接口变更", "API diff", "CI", "契约"],
    "cron-explain": ["cron", "crontab", "定时任务", "调度", "时区", "CronJob", "运维", "表达式"],
    "sql-migration-check": ["SQL", "数据库迁移", "migration", "DDL", "锁表", "MySQL", "PostgreSQL", "上线检查", "DBA"],
    "dockerfile-check": ["Dockerfile", "Docker", "镜像", "容器", "最佳实践", "lint", "体检", "CI", "安全"],
    "doc-coauthoring-zh": ["写文档", "技术方案", "PRD", "设计文档", "提案", "RFC", "决策文档", "协作写作"],
    "memory-systems-zh": ["记忆系统", "长期记忆", "跨会话", "知识图谱", "向量检索", "Mem0", "Graphiti", "Agent 记忆"],
    "tool-design-zh": ["工具设计", "MCP", "tool description", "function calling", "Agent 工具", "schema", "错误信息", "命名规范"],
    "context-compression-zh": ["上下文压缩", "摘要", "compaction", "长会话", "交接", "token 优化", "评估", "Agent"],
    "context-degradation-zh": ["上下文退化", "中间迷失", "上下文投毒", "RAG", "长对话", "Agent 变笨", "注意力", "调试"],
    "context-fundamentals-zh": ["上下文工程", "注意力预算", "系统提示词", "渐进式披露", "中间迷失", "token 预算", "prompt", "Agent 设计"],
    "architecture-deepening-zh": ["架构评审", "重构", "深模块", "浅模块", "HTML 报告", "可测试性", "代码库体检", "Mermaid"],
    "tdd-seams-zh": ["TDD", "测试驱动", "红绿循环", "接缝", "mock", "集成测试", "单元测试", "测试反模式"],
    "prototype-zh": ["原型", "demo", "状态机", "UI 方案", "单文件 HTML", "快速验证", "设计问题"],
    "re-pitch-zh": ["没听懂", "重新解释", "大白话", "简化", "沟通", "术语", "说人话"],
    "to-questionnaire-zh": ["问卷", "访谈提纲", "需求澄清", "异步协作", "决策", "调研", "问题清单"],
    "domain-modeling-zh": ["领域建模", "术语表", "CONTEXT.md", "ADR", "统一语言", "限界上下文", "DDD", "架构决策"],
    "triage-zh": ["工单分诊", "issue", "PR", "triage", "Agent 简报", "wontfix", "GitHub", "Jira", "维护者"],
    "writing-for-agents-zh": ["SKILL.md", "技能写作", "AGENTS.md", "CLAUDE.md", "规则文件", "提示词", "技能开发", "文档"],
    "research-primary-zh": ["调研", "研究", "文档核查", "一手来源", "引用", "research", "资料"],
    "wizard-zh": ["向导", "脚本", "bash", "环境配置", "密钥", "CI secrets", "onboarding", "迁移"],
    "handoff-doc-zh": ["交接", "会话交接", "上下文", "总结", "handoff", "接手", "进度"],
    "wayfinder-zh": ["规划", "决策", "大项目", "工单", "路线图", "迷雾", "跨会话", "planning"],
    "deep-module-design-zh": ["模块设计", "接口设计", "架构", "可测试性", "深模块", "seam", "重构", "代码设计"],
    "teach-workspace-zh": ["学习", "教学", "课程", "教我", "自学", "学习计划", "知识管理", "教育", "teach"],
    "skill-lint": ["SKILL.md", "技能质量", "打分", "lint", "技能开发", "可发现性", "发布前检查", "skill creator"],
    "skillhub-publish-helper": ["SkillHub", "发布", "publish", "CLI", "批量发布", "技能发布", "skillhub publish", "上架"],
    "interview-me-zh": ["需求访谈", "意图澄清", "需求分析", "访谈", "interview", "产品需求", "一次一问"],
    "release-readiness-check": ["上线检查", "上线体检", "发布门禁", "release readiness", "Dockerfile", "Kubernetes", "SQL 迁移", "OpenAPI", ".env"],
    "secrets-scan": ["密钥扫描", "泄密自查", "secret scanning", "硬编码密钥", "token 泄露", "提交历史", "安全审计", "CI 门禁"],
    "config-env-diff": ["配置对比", "多环境", "配置漂移", "env diff", "YAML", "properties", "上线核对", "配置管理"],
    "i18n-missing-keys": ["国际化", "i18n", "多语言", "缺失 key", "locales", "占位符", "翻译检查", "前端"],
    "test-coverage-gap": ["测试覆盖", "coverage", "测试缺口", "补测试", "Cobertura", "lcov", "测试债", "质量门禁"],
    "brainstorming-zh": ["头脑风暴", "需求澄清", "方案设计", "spec", "设计文档", "探针", "YAGNI", "动手前对齐"],
    "systematic-debugging-zh": ["系统化调试", "根因分析", "debug", "复现", "假设验证", "纵深防御", "抖动测试", "排查"],
    "writing-plans-zh": ["实施计划", "任务拆解", "plan", "TDD", "文件结构", "占位符", "验收标准", "交接执行"],
    "executing-plans-zh": ["执行计划", "逐任务实现", "检查点", "验证步骤", "遇阻即停", "待办", "落地", "研发效能"],
    "verification-before-completion-zh": ["完成前验证", "证据优先", "测试通过", "提交前检查", "自检门禁", "红绿往返", "回归测试", "质量门禁"],
    "subagent-driven-development-zh": ["子代理", "Agent 编排", "任务评审", "修复循环", "进度账本", "选模型", "上下文压缩", "并发调度"],
    "dispatching-parallel-agents-zh": ["并行代理", "子代理派发", "并发排查", "问题域切分", "提示词设计", "结果合并", "冲突检查", "Agent 编排"],
    "using-git-worktrees-zh": ["git worktree", "工作树", "隔离工作区", "分支保护", "基线测试", "gitignore", "子模块", "并行开发"],
    "receiving-code-review-zh": ["代码评审", "评审意见", "code review", "技术反驳", "YAGNI", "PR 评论", "逐条修复", "澄清提问"],
    "finishing-a-development-branch-zh": ["分支收尾", "合并", "Pull Request", "工作树清理", "基线分支", "上线落地", "git", "发布"],
    "sql-slow-query-digest": ["慢查询", "慢SQL", "MySQL", "PostgreSQL", "索引优化", "数据库排查", "SQL指纹", "pt-query-digest"],
    "api-contract-test": ["接口测试", "契约测试", "API回归", "冒烟测试", "JSON断言", "CI门禁", "接口验收", "HTTP"],
    "git-commit-lint": ["提交规范", "Conventional Commits", "commitlint", "git", "commit-msg", "CI门禁", "代码规范", "提交历史"],
    "openapi-to-markdown": ["OpenAPI", "Swagger", "接口文档", "API文档", "Markdown", "文档生成", "前后端对接", "文档同步"],
    "docker-compose-check": ["容器编排", "compose", "Docker", "上线检查", "容器安全", "健康检查", "资源限制", "DevOps"],
    "nginx-config-check": ["nginx", "反向代理", "配置审查", "TLS", "安全响应头", "性能优化", "上线检查", "SRE"],
    "tls-cert-check": ["TLS", "证书到期", "HTTPS", "SSL", "巡检", "SAN", "证书链", "SRE"],
    "sql-schema-diff": ["表结构", "schema diff", "DDL", "迁移", "MySQL", "PostgreSQL", "锁表", "数据库"],
    "jwt-inspect": ["JWT", "令牌解码", "鉴权排查", "401 排错", "过期时间", "HS256 验签", "安全体检", "Bearer"],
    "http-bench-lite": ["压测", "QPS", "p99", "延迟分位", "接口自测", "性能基线", "ab", "wrk"],
    "dns-check": ["DNS", "域名解析", "解析生效", "TTL", "CNAME", "MX", "SPF", "切换验证"],
}


def split_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        sys.exit("SKILL.md 没有 frontmatter")
    return m.group(1), m.group(2)


def get(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    if v[:1] in "\"'" and v[-1:] == v[:1]:
        v = v[1:-1]
    return v


def yaml_list(key: str, items):
    return key + ":\n" + "".join(f"  - {i}\n" for i in items)


def parse_tags(fm: str) -> list:
    """从原 frontmatter 解析已有 tags：块形式（tags:\n  - x）或单行形式（tags: [a, b]）。"""
    m = re.search(r"^tags:[ \t]*\n((?:[ \t]*-[ \t]*.+\n?)+)", fm, re.M)
    if m:
        items = []
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line.startswith("-"):
                continue
            v = line[1:].strip()
            if v[:1] in "\"'" and v[-1:] == v[:1] and len(v) >= 2:
                v = v[1:-1]
            if v:
                items.append(v)
        return items
    m = re.search(r"^tags:[ \t]*\[(.*)\][ \t]*$", fm, re.M)
    if m:
        items = []
        for part in m.group(1).split(","):
            v = part.strip()
            if v[:1] in "\"'" and v[-1:] == v[:1] and len(v) >= 2:
                v = v[1:-1]
            if v:
                items.append(v)
        return items
    return []


def strip_tags(fm: str) -> str:
    """去掉原 frontmatter 里已有的 tags 字段（块形式或单行形式），避免与 SkillHub 头部的 tags 重复。"""
    fm = re.sub(r"^tags:[ \t]*\n(?:[ \t]*-[ \t]*.+\n?)+", "", fm, flags=re.M)
    fm = re.sub(r"^tags:.*\n?", "", fm, flags=re.M)
    return fm


def prep(name: str, out: Path) -> Path:
    src = source_dir(name)
    fm, body = split_frontmatter((src / "SKILL.md").read_text("utf-8"))
    slug = SLUGS.get(name, name)
    summary = get(fm, "description_zh") or get(fm, "description")
    if len(summary) > 200:
        summary = summary[:197] + "…"
    tags = TAGS[name] if name in TAGS else parse_tags(fm)
    head = "\n".join([
        f"slug: {slug}",
        f'displayName: "{get(fm, "display_name") or name}"',
        f"version: {get(fm, 'version') or '1.0.0'}",
        f'summary: "{summary}"',
        f"license: {LICENSE}",
        f"homepage: {HOMEPAGE}",
        yaml_list("tags", tags).rstrip(),
    ])
    dst = out / slug
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc"))
    fm_rest = re.sub(r"^version:.*\n?", "", fm, flags=re.M)  # 避免与 SkillHub 头部的 version 重复
    fm_rest = strip_tags(fm_rest)  # 避免与 SkillHub 头部的 tags 重复
    (dst / "SKILL.md").write_text(f"---\n{head}\n{fm_rest}\n---\n{body}", "utf-8")
    # SkillHub 上传拒绝无扩展名文件（实测 400「不允许的文件类型: LICENSE」），许可证只写 frontmatter 的 license 字段
    for junk in ("LICENSE", "NOTICE", "ATTRIBUTION"):
        if (dst / junk).exists():
            (dst / junk).unlink()
    return dst


def check(dst: Path) -> list:
    fm, _ = split_frontmatter((dst / "SKILL.md").read_text("utf-8"))
    errs = []
    slug = get(fm, "slug")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) or not 2 <= len(slug) <= 128:
        errs.append(f"slug 不是 kebab-case 或长度越界: {slug!r}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", get(fm, "version")):
        errs.append(f"version 不是 SemVer: {get(fm, 'version')!r}")
    if not get(fm, "displayName"):
        errs.append("缺 displayName")
    for k in ("summary", "license", "homepage"):
        if not get(fm, k):
            errs.append(f"建议字段缺失: {k}")
    return errs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/skillhub")
    ap.add_argument("names", nargs="*", default=list(SLUGS))
    a = ap.parse_args()
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for n in a.names:
        d = prep(n, out)
        errs = check(d)
        bad += bool(errs)
        print(("FAIL " if errs else "OK   ") + str(d.relative_to(ROOT) if d.is_relative_to(ROOT) else d))
        for e in errs:
            print("     -", e)
    sys.exit(1 if bad else 0)
