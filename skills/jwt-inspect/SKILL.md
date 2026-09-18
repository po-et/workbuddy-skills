---
name: jwt-inspect
description: JWT 解码与调试、看懂 token 里装了什么、令牌过期了吗、exp/nbf/iat 换算成人话、Bearer 鉴权失败排查、401 排错、HS256 验签、检查 alg 是否为 none、令牌有效期是不是太长。当用户说「帮我解一下这个 JWT」「这个 token 过期没、还剩多久」「接口一直 401 是不是令牌问题」「这串 Authorization 头里是什么」「帮我验一下签名对不对」「这个令牌安全吗」时使用。附纯标准库脚本 scripts/jwt_inspect.py：base64url 解码 header 与 payload（不校验也能看），逐条解释 iss/sub/aud/exp/nbf/iat/jti，按 --tz 算过期与生效状态，安全体检（alg=none、密钥明文上命令行、有效期超 30 天、缺 exp/aud、载荷含敏感字段），可选 --verify 用环境变量 JWT_SECRET 做 HS256/384/512 验签，RS/ES 给出 openssl 命令；支持 --json，异常退出码 1。
author: Captain
version: 0.1.0
display_name: "JWT 解码与体检"
display_name_en: "JWT Inspect"
description_zh: "一条命令解开 JWT：header/payload 全展开并逐条解释，exp/nbf 换算成「还剩多久/过期多久」，顺带做安全体检（alg=none、超长有效期、缺 exp、载荷装敏感信息）；可用环境变量 JWT_SECRET 做 HS 系列验签。纯 Python 标准库。"
description_en: "Decode a JWT in one command — header and payload expanded with per-claim explanations, exp/nbf turned into human time-left, plus a security review (alg=none, over-long lifetime, missing exp, sensitive data in the payload); optional HS256/384/512 verification using the JWT_SECRET env var. Pure Python stdlib."
examples_zh:
  - "帮我解一下这个 JWT，看看过期没、还剩多久"
  - "接口一直 401，这枚令牌的 exp 和 aud 有问题吗"
  - "用 JWT_SECRET 验一下这个 token 的 HS256 签名对不对"
examples_en:
  - "Decode this JWT and tell me whether it has expired"
  - "My API returns 401 — are this token's exp and aud wrong?"
  - "Verify this token's HS256 signature with JWT_SECRET"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔑" } }
---

# JWT 解码与体检

把一串看不懂的 `eyJhbGciOi...` 摊开成人话：谁签的、给谁的、什么时候过期、现在还能不能用、有没有安全隐患。排查 401 / 鉴权串不通 / 令牌"莫名失效"时的第一把工具。

## 何时用

- 联调时接口返回 401 或 403，需要先确认「是令牌过期了，还是 aud/iss 对不上」。
- 拿到一串 Bearer 令牌，想知道里面有哪些字段、业务方塞了什么自定义声明。
- 评审别人的鉴权设计：有效期多长、有没有 exp/aud/jti、有没有把手机号密码塞进 payload。
- 怀疑签发端配置错了算法（`alg` 被写成 `none`，或 HS 与 RS 混用）。

## 用法

```bash
python3 scripts/jwt_inspect.py eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...      # 位置参数
echo "$TOKEN" | python3 scripts/jwt_inspect.py                              # 管道
python3 scripts/jwt_inspect.py --header "Authorization: Bearer eyJhbGci..." # 整行头，自动剥前缀
python3 scripts/jwt_inspect.py "$TOKEN" --tz Asia/Shanghai                  # 按指定时区显示时间
JWT_SECRET='你的密钥' python3 scripts/jwt_inspect.py "$TOKEN" --verify       # HS256/384/512 验签
python3 scripts/jwt_inspect.py "$TOKEN" --json > token.json                 # 机器可读
```

## 流程

1. **先解码再下结论**：任何人拿到令牌都能读 payload（只是 base64，不是加密），所以解码本身不需要密钥，直接跑脚本把字段摊给用户看。
2. **对时间**：看「时间状态」一段。已过期 / 未到生效时间会直接写明差了多久；跨地区排查时加 `--tz Asia/Shanghai` 或 `--tz UTC`，不要拿本机时区去猜服务端。
3. **对身份**：`iss` 是不是你对接的签发方、`aud` 是不是当前这个服务、`sub` 是不是预期用户。401 里有一半是 aud/iss 配错，而不是过期。
4. **验签**（可选）：HS 系列把密钥放进环境变量 `JWT_SECRET` 再加 `--verify`；签名不匹配说明密钥不对、令牌被改过，或签发方换了算法。RS/ES 系列脚本会打印一段可直接复制的 `openssl dgst -verify` 命令，配公钥自行校验。
5. **体检**：把「安全体检」里的严重/高项反馈给签发方；这部分只看令牌自身，不需要访问任何服务。

## 输出与退出码

- 文本模式分段输出：段长度、Header、Payload、逐条声明解释、时间状态、安全体检、签名校验、结论。
- `--json` 输出 `ok` / `header` / `payload` / `claims`（含中文 meaning 与格式化时间）/ `time_status`（`expired`、`expires_in_sec`、`expires_in_human`、`lifetime_sec`）/ `warnings`（level 分 严重 高 中 低）/ `verify`，可直接喂给流水线或告警。
- 退出码 0 = 可用；1 = 已过期、未到生效时间、验签失败、存在严重安全问题（如 `alg=none`）、或令牌根本解不开。CI 里可以直接用返回值卡住"签发了一枚永不过期令牌"这类问题。

## 安全体检规则

| 级别 | 触发条件 | 处置 |
| --- | --- | --- |
| 严重 | `alg` 为 `none` | 服务端必须用算法白名单，禁止按令牌自称的 alg 选校验方式 |
| 严重 | 用 `--secret` 在命令行传密钥 | 改用环境变量 `JWT_SECRET`，命令行参数会进 shell 历史、ps 输出与 CI 日志 |
| 高 | 缺 `exp` | 令牌永不过期，泄露后只能换密钥止血 |
| 高 | payload 键名含 password/secret/id_card 等 | 载荷是明文可读的，敏感字段换成不可逆 ID |
| 中 | 有效期超过 30 天 | 访问令牌建议分钟级到小时级，长期凭证交给 refresh token |
| 低 | 缺 `aud` / `jti` / `kid` | 分别对应跨服务重放、无法吊销、密钥轮换不平滑 |

## 边界与常见问题

- 只处理 JWS（3 段）。5 段的 JWE 是加密令牌，不解密也读不出内容，脚本会直接提示。
- 验签只做 HMAC（HS256/384/512），因为纯标准库无法做 RSA/ECDSA 验签；RS/ES/PS 会给 openssl 命令，其中 ES 系列的签名是裸 R‖S，需先转 DER 才能喂给 openssl。
- 解码成功不等于令牌可信：没验签时脚本会在结尾提醒；不要拿"解出来了"当作鉴权通过。
- 令牌是凭证，不要粘进公开工单、聊天群或提交进仓库；调试完及时让签发方吊销。示例与文档里一律只用 example.com 这类占位域名。
- 时间字段按 RFC 7519 都是「秒级 UTC 时间戳」；有些框架误写成毫秒，脚本会把它显示成遥远的未来年份，看到这种就是签发端写错了单位。
