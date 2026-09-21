"""让 `python3 -m skillkit` 等价于 `skillkit`（不装包也能直接跑）。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
