"""skillkit 命令行入口。

这里只做三件事：拼 argparse、分发到子命令、把异常翻译成人话和退出码。
业务逻辑都在 skillkit/commands/ 下。
"""

from __future__ import print_function

import argparse
import sys
from typing import List, Optional

from . import __version__
from .commands import MODULES

EPILOG = """\
典型流程：
  skillkit new my-skill --dir skills      # 1. 生成骨架
  skillkit lint skills/my-skill           # 2. 边写边看格式与分数
  skillkit doctor skills/my-skill         # 3. 发布前体检：能不能发
  skillkit build skills/my-skill --out dist/skillhub   # 4. 生成发布副本
  skillkit budget --count 40 --used 0     # 5. 算发布节奏，别把配额一晚打满
  skillkit stats my-skill                 # 6. 上架后看真实指标

退出码：0 通过；1 有问题（FAIL / 低于门槛 / 查不到）；2 用法错误。
"""


def build_parser():
    # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser(
        prog="skillkit",
        description="技能作者的命令行工具箱：起草、体检、打包、排期、看数据。纯标准库，零依赖。",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version",
                        version="skillkit %s" % __version__)
    subparsers = parser.add_subparsers(dest="command", metavar="<子命令>")
    for module in MODULES:
        sub = module.add_parser(subparsers)
        sub.set_defaults(_run=module.run)
    return parser


def main(argv=None):
    # type: (Optional[List[str]]) -> int
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "_run", None):
        parser.print_help()
        return 2
    try:
        return int(args._run(args) or 0)
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except OSError as exc:
        print("文件操作失败: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
