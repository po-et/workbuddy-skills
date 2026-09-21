"""skillkit 的测试。

跑法（在仓库根目录）::

    python3 -m unittest skillkit.tests.test_cli -v
    python3 -m unittest discover -s skillkit/tests -t .

不联网：唯一涉及网络的 `stats` 在测试里把 http_get_json 换成假函数，
并额外断言真实的 urlopen 一次都没被调用过。
"""
