"""skillkit 的子命令。

每个模块暴露两个函数：

    add_parser(subparsers) -> argparse.ArgumentParser   注册参数与中文 --help
    run(args) -> int                                     执行，返回退出码

cli.py 只负责把它们串起来，不掺业务逻辑。
"""

from . import budget, build, doctor, lint, new, pitfalls, stats  # noqa: F401

#: 注册顺序 = `skillkit --help` 里的展示顺序，按技能作者的工作流排。
MODULES = (new, lint, build, doctor, budget, stats, pitfalls)
