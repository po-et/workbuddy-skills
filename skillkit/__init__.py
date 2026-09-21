"""skillkit —— 技能作者的命令行工具箱（纯 Python 标准库，零第三方依赖）。

覆盖一个技能从「起草」到「上架」的完整链路：

    new     从模板生成骨架（frontmatter 字段齐全，坑点写在注释里）
    lint    格式校验 + 五维质量打分 + 逐条改进建议
    build   生成发布副本，自动处理已知的拒收规则
    budget  发布配额与节奏规划
    stats   查询已上架技能的真实指标（downloads/stars/评测分）
    doctor  一次跑完 lint + build 试运行，给「能不能发」的结论
    pitfalls 打印内置的平台规律表（区分实测与推测）

设计约束：
  * 只用标准库，Python 3.9+，跨平台；
  * 规则表集中在 skillkit/rules.py，是全工具唯一的真相源；
  * frontmatter 的读写集中在 skillkit/frontmatter.py，子命令不各写一份正则。
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
