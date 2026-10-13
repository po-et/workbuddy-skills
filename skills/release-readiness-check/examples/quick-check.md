# 五分钟试用（合成样例）

建一个空测试目录，加入以下两个文件；这是演示输入，未连接任何真实项目或生产环境。

`Dockerfile`：

```dockerfile
FROM python:3.12-slim
USER 1000
```

`.dockerignore`：

```txt
.git
```

运行：

```bash
python3 "<skill-dir>/scripts/release_check.py" "/path/to/synthetic-project" --json --strict
```

预期：Dockerfile 项 `ok`，其他项 `na`，收据包含两个输入与六个脚本；本轮未发现 high，生产资格仍 `unknown`。真实结果以执行输出为准。

在 Dockerfile 添加 `ENV API_TOKEN=synthetic-value-123` 再跑：预期出现 DF006 high，strict 返回 `1`。此值是合成字符串，不使用真实凭据。

加入 `openapi.json`：

```json
{"openapi":"3.0.3","paths":{"/health":{"get":{}}}}
```

未提供基线时重跑：预期 `openapi` 为 `unknown / no-baseline`，strict 返回 `1`。这证明缺证据不会被当成静态通过。

每次使用默认新临时目录，或选择全新 `--out` 路径；旧报告不会被覆盖。样例通过不能证明业务发布安全。
