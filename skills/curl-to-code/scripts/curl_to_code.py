#!/usr/bin/env python3
"""把一条 curl 命令转成 8 种语言的请求代码，敏感请求头自动改读环境变量。纯标准库。

用法：
  python3 curl_to_code.py "curl -X POST https://api.example.com/v1/issues -H 'Authorization: Bearer abc' -d '{\"a\":1}'"
  pbpaste | python3 curl_to_code.py -            # 浏览器 Copy as cURL 直接粘贴
  python3 curl_to_code.py - --lang go-nethttp
  python3 curl_to_code.py "curl ..." --all --json
支持语言：python-requests / python-stdlib / javascript-fetch / node-axios / go-nethttp /
          java-httpclient / php-curl / shell
"""
import argparse
import json
import re
import shlex
import sys
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

LANGS = ["python-requests", "python-stdlib", "javascript-fetch", "node-axios",
         "go-nethttp", "java-httpclient", "php-curl", "shell"]

# 值需要改读环境变量的请求头（子串匹配，小写）
SENSITIVE = ("authorization", "cookie", "token", "api-key", "apikey", "secret", "password",
             "passwd", "access-key", "private-token", "session", "csrf", "signature", "x-auth")
SCHEME = re.compile(r"^(Bearer|Token|Basic|JWT|OAuth|Digest)\s+(\S.*)$", re.I)

# curl 里带值的长选项 / 短选项
LONG_VAL = {"--request", "--header", "--data", "--data-raw", "--data-binary", "--data-ascii",
            "--data-urlencode", "--form", "--form-string", "--user", "--url", "--cookie",
            "--user-agent", "--referer", "--max-time", "--connect-timeout", "--output",
            "--upload-file", "--proxy", "--write-out", "--cookie-jar", "--retry", "--resolve",
            "--cert", "--key", "--range", "--oauth2-bearer", "--aws-sigv4"}
LONG_FLAG = {"--location", "--insecure", "--compressed", "--get", "--silent", "--show-error",
             "--include", "--verbose", "--fail", "--head", "--http1.1", "--http2", "--globoff",
             "--no-progress-meter", "--remote-name", "--tlsv1.2", "--path-as-is", "--raw"}
SHORT_VAL = set("XHdFuboAeExmTwcC")
SHORT_FLAG = set("LkGsSivfIONg")


# ---------------------------------------------------------------- 命令行分词

def ansi_c_unquote(s):
    """$'...' 的 ANSI-C 转义。"""
    out, i = [], 0
    simple = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
              "\\": "\\", "'": "'", '"': '"', "?": "?", "e": "\x1b", "0": "\0"}
    while i < len(s):
        c = s[i]
        if c != "\\" or i + 1 >= len(s):
            out.append(c); i += 1; continue
        n = s[i + 1]
        if n == "x" and re.match(r"[0-9a-fA-F]{1,2}", s[i + 2:i + 4] or ""):
            m = re.match(r"[0-9a-fA-F]{1,2}", s[i + 2:i + 4]); out.append(chr(int(m.group(0), 16))); i += 2 + len(m.group(0))
        elif n == "u" and re.match(r"[0-9a-fA-F]{1,4}", s[i + 2:i + 6] or ""):
            m = re.match(r"[0-9a-fA-F]{1,4}", s[i + 2:i + 6]); out.append(chr(int(m.group(0), 16))); i += 2 + len(m.group(0))
        elif n in simple:
            out.append(simple[n]); i += 2
        else:
            out.append(n); i += 2
    return "".join(out)


def split_command(text):
    """把一条 curl 命令切成 token：支持单双引号、反斜杠续行、$'...'。"""
    tokens, buf, started, i = [], [], False, 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            if started:
                tokens.append("".join(buf)); buf, started = [], False
            i += 1; continue
        if c == "\\" and i + 1 < n and text[i + 1] in "\r\n":
            i += 2 + (1 if text[i + 1] == "\r" and text[i + 2:i + 3] == "\n" else 0)
            continue                                  # 行尾续行，不产生 token
        if c == "^" and i + 1 < n and text[i + 1] in "\r\n":
            i += 2; continue                          # Windows cmd 续行
        started = True
        if c == "\\":
            if i + 1 < n:
                buf.append(text[i + 1]); i += 2; continue
            i += 1; continue
        if c == "$" and i + 1 < n and text[i + 1] == "'":
            j = i + 2; raw = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    raw.append(text[j:j + 2]); j += 2; continue
                if text[j] == "'":
                    break
                raw.append(text[j]); j += 1
            buf.append(ansi_c_unquote("".join(raw))); i = j + 1; continue
        if c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                buf.append(text[i + 1:]); break
            buf.append(text[i + 1:j]); i = j + 1; continue
        if c == '"':
            j, raw = i + 1, []
            while j < n:
                if text[j] == "\\" and j + 1 < n and text[j + 1] in '"\\$`\n':
                    if text[j + 1] != "\n":
                        raw.append(text[j + 1])
                    j += 2; continue
                if text[j] == '"':
                    break
                raw.append(text[j]); j += 1
            buf.append("".join(raw)); i = j + 1; continue
        buf.append(c); i += 1
    if started:
        tokens.append("".join(buf))
    return tokens


# ---------------------------------------------------------------- 请求模型

class Req:
    def __init__(self):
        self.method = None
        self.url = ""
        self.headers = []          # [(name, Val)]
        self.query_extra = []      # -G 追加的查询参数 [(k, v)]
        self.kind = None           # json | raw | form | multipart
        self.json_obj = None
        self.raw = ""
        self.form = []             # [(k, v)] 表单字段
        self.files = []            # [(field, filename)] -F name=@file
        self.auth = None           # (user, Val)
        self.follow = False
        self.insecure = False
        self.compressed = False
        self.timeout = None
        self.secrets = []          # [{"header","env","masked"}]
        self.notes = []
        self.warnings = []


def mask(s):
    s = str(s)
    return (s[:4] + "***" if len(s) > 6 else "***") + f"（{len(s)} 字符）"


def make_env(name, used):
    low = name.lower()
    if low == "authorization":
        base = "API_TOKEN"
    elif low == "cookie":
        base = "COOKIE"
    elif low in ("password", "passwd"):
        base = "API_PASSWORD"
    else:
        base = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "SECRET"
    env = base
    k = 2
    while env in used:
        env = f"{base}_{k}"; k += 1
    used.add(env)
    return env


def secretize(req, name, value, used, no_env, label=None):
    """返回 Val：[("lit", s) | ("env", NAME)]；命中敏感头时把凭据部分换成环境变量。"""
    low = name.lower()
    if no_env or not any(k in low for k in SENSITIVE):
        return [("lit", value)]
    m = SCHEME.match(value)
    prefix, cred = (m.group(1) + " ", m.group(2)) if m else ("", value)
    if not cred.strip():
        return [("lit", value)]
    env = make_env(name, used)
    req.secrets.append({"header": label or name, "env": env, "masked": mask(cred)})
    return ([("lit", prefix)] if prefix else []) + [("env", env)]


def parse_curl(tokens, no_env=False):
    req, used = Req(), set()
    datas, urlencodes, head_only = [], [], False
    i = 0
    if tokens and tokens[0].lower().rstrip(".exe") in ("curl", "curl.exe"):
        i = 1
    argv = []
    while i < len(tokens):                             # 先把短选项簇展开
        t = tokens[i]
        if t.startswith("--") or not t.startswith("-") or t == "-":
            argv.append(t); i += 1; continue
        j = 1
        while j < len(t):
            c = t[j]
            if c in SHORT_VAL:
                argv.append("-" + c)
                if t[j + 1:]:
                    argv.append(t[j + 1:])
                break
            argv.append("-" + c); j += 1
        i += 1

    i = 0
    while i < len(argv):
        t = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None

        def take():
            nonlocal i
            i += 1
            return nxt if nxt is not None else ""

        if t in ("-X", "--request"):
            req.method = take().upper()
        elif t in ("-H", "--header"):
            v = take()
            if ":" in v:
                k, _, hv = v.partition(":")
                k, hv = k.strip(), hv.strip()
                if hv:
                    req.headers.append((k, secretize(req, k, hv, used, no_env)))
                else:
                    req.warnings.append(f"忽略空值请求头 {k}（curl 用 `{k};` 才是发送空头）")
            else:
                req.warnings.append(f"无法解析的 -H 参数：{v!r}")
        elif t in ("-d", "--data", "--data-raw", "--data-ascii", "--data-binary"):
            v = take()
            if v.startswith("@"):
                req.warnings.append(f"{t} 从文件读取（{v[1:]}），生成的代码里用占位路径，请自行确认")
            datas.append(v)
        elif t == "--data-urlencode":
            urlencodes.append(take())
        elif t in ("-F", "--form", "--form-string"):
            v = take()
            k, _, fv = v.partition("=")
            if fv.startswith("@") or fv.startswith("<"):
                req.files.append((k, fv[1:]))
            else:
                req.form.append((k, fv))
            req.kind = "multipart"
        elif t in ("-u", "--user"):
            v = take()
            u, _, p = v.partition(":")
            req.auth = (u, secretize(req, "password", p, used, no_env, label="-u 密码") if p else [("lit", "")])
        elif t == "--oauth2-bearer":
            v = take()
            req.headers.append(("Authorization", secretize(req, "Authorization", "Bearer " + v, used, no_env)))
        elif t == "--url":
            req.url = take()
        elif t in ("-b", "--cookie"):
            v = take()
            if "=" in v:
                req.headers.append(("Cookie", secretize(req, "Cookie", v, used, no_env)))
            else:
                req.warnings.append(f"-b {v} 看起来是 cookie 文件，生成的代码未包含")
        elif t in ("-A", "--user-agent"):
            req.headers.append(("User-Agent", [("lit", take())]))
        elif t in ("-e", "--referer"):
            req.headers.append(("Referer", [("lit", take())]))
        elif t in ("-m", "--max-time", "--connect-timeout"):
            try:
                tv = float(take())
                req.timeout = int(tv) if tv == int(tv) else tv
            except ValueError:
                pass
        elif t in ("-L", "--location"):
            req.follow = True
        elif t in ("-k", "--insecure"):
            req.insecure = True
        elif t == "--compressed":
            req.compressed = True
        elif t in ("-G", "--get"):
            req.method = req.method or "GET"
            req.notes.append("-G：请求体参数已并入 URL 查询串，并按 URL 编码规则重新编码（curl 的 -d 不会自动编码）")
            req.kind = req.kind or "query"
        elif t in ("-I", "--head"):
            head_only = True
        elif t in LONG_VAL or t in ("-o", "-T", "-x", "-w", "-c", "-C", "-E"):
            take()                                     # 与代码生成无关的带值选项，吃掉值
        elif t in LONG_FLAG or (t.startswith("-") and len(t) == 2 and t[1] in SHORT_FLAG):
            pass
        elif t.startswith("-"):
            req.warnings.append(f"未识别选项 {t}（已忽略）")
        elif not req.url:
            req.url = t
        else:
            req.warnings.append(f"多个 URL，只转换第一个；忽略 {t}")
        i += 1

    if not req.url:
        raise SystemExit("解析失败：命令里没有 URL")
    if "://" not in req.url:
        req.url = "https://" + req.url

    body = "&".join(datas)
    for item in urlencodes:
        k, _, v = item.partition("=")
        body = (body + "&" if body else "") + (f"{k}={quote(v)}" if k else quote(v))
    ctype = next((render(v, "raw") for k, v in req.headers if k.lower() == "content-type"), "")

    if req.kind == "query" or (body and req.method == "GET" and any(a in ("-G", "--get") for a in argv)):
        sp = urlsplit(req.url)
        q = parse_qsl(sp.query, keep_blank_values=True) + parse_qsl(body, keep_blank_values=True)
        req.url = urlunsplit((sp.scheme, sp.netloc, sp.path, urlencode(q), sp.fragment))
        body, req.kind = "", None
    if req.kind != "multipart" and body:
        if "json" in ctype.lower() or (not ctype and body.lstrip()[:1] in "{["):
            try:
                req.json_obj = json.loads(body); req.kind = "json"
                if not ctype:
                    req.notes.append("请求体是 JSON 但 curl 没带 Content-Type（curl 默认发 x-www-form-urlencoded），生成的代码显式补了 application/json")
            except json.JSONDecodeError:
                req.kind, req.raw = "raw", body
        elif ("x-www-form-urlencoded" in ctype.lower() or not ctype) and re.fullmatch(r"[^=&]+=[^&]*(&[^=&]+=[^&]*)*", body or "x="):
            req.kind, req.form = "form", parse_qsl(body, keep_blank_values=True)
        else:
            req.kind, req.raw = "raw", body
    if not req.method:
        req.method = "HEAD" if head_only else ("POST" if req.kind in ("json", "raw", "form", "multipart") else "GET")
    if req.compressed and not any(k.lower() == "accept-encoding" for k, _ in req.headers):
        req.headers.append(("Accept-Encoding", [("lit", "gzip, deflate")]))
    if not req.follow:
        req.notes.append("原命令没有 -L，生成的代码保持「不自动跟随重定向」以与 curl 行为一致")
    if req.insecure:
        req.warnings.append("-k 跳过证书校验：生成的代码里关掉了 TLS 校验，生产环境请去掉")
    return req


# ---------------------------------------------------------------- 字面量与 Val 渲染

def esc(s, lang):
    if lang == "php":
        return s.replace("\\", "\\\\").replace("'", "\\'")
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    if lang == "sh":
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    return out


ENV_EXPR = {"py": 'os.environ["{0}"]', "js": "process.env.{0}", "go": 'os.Getenv("{0}")',
            "java": 'System.getenv("{0}")', "php": "getenv('{0}')", "sh": '"${0}"'}
QUOTE = {"py": '"{0}"', "js": '"{0}"', "go": '"{0}"', "java": '"{0}"', "php": "'{0}'", "sh": '"{0}"'}
JOIN = {"py": " + ", "js": " + ", "go": " + ", "java": " + ", "php": " . ", "sh": ""}


def render(val, lang):
    """把 Val 渲染成目标语言的表达式；lang='raw' 时还原原始明文（仅内部用）。"""
    merged = []
    for kind, txt in val:                              # 合并相邻字面量
        if kind == "lit" and merged and merged[-1][0] == "lit":
            merged[-1] = ("lit", merged[-1][1] + txt)
        else:
            merged.append((kind, txt))
    val = merged
    if lang == "raw":
        return "".join(p[1] if p[0] == "lit" else "$" + p[1] for p in val)
    if lang == "sh":
        return '"' + "".join(esc(p[1], "sh") if p[0] == "lit" else "${%s}" % p[1] for p in val) + '"'
    parts = [QUOTE[lang].format(esc(p[1], lang)) if p[0] == "lit" else ENV_EXPR[lang].format(p[1]) for p in val]
    return JOIN[lang].join(parts) if parts else QUOTE[lang].format("")


def has_env(req):
    return any(p[0] == "env" for _, v in req.headers for p in v) or (req.auth and any(p[0] == "env" for p in req.auth[1]))


def py_literal(obj, indent=0):
    pad, pad2 = " " * indent, " " * (indent + 4)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = ",\n".join(f'{pad2}{json.dumps(k, ensure_ascii=False)}: {py_literal(v, indent + 4)}' for k, v in obj.items())
        return "{\n" + items + ",\n" + pad + "}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        return "[\n" + ",\n".join(pad2 + py_literal(v, indent + 4) for v in obj) + ",\n" + pad + "]"
    if obj is True:
        return "True"
    if obj is False:
        return "False"
    if obj is None:
        return "None"
    return json.dumps(obj, ensure_ascii=False)


def json_text(obj, indent=2):
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def dict_lines(pairs, lang, indent=4):
    pad = " " * indent
    kv = {"py": '{k}: {v},', "js": "{k}: {v},", "php": "{k} => {v},"}[lang]
    return "\n".join(pad + kv.format(k=QUOTE[lang].format(esc(k, lang)), v=render(v, lang)) for k, v in pairs)


# ---------------------------------------------------------------- 代码生成

def gen_python_requests(r):
    L = ["import os" if has_env(r) else None, "import requests", "", f'url = "{esc(r.url, "py")}"']
    L = [x for x in L if x is not None]
    if r.headers:
        L += ["headers = {", dict_lines(r.headers, "py"), "}"]
    kw = ["url", "headers=headers" if r.headers else None]
    if r.kind == "json":
        L += ["payload = " + py_literal(r.json_obj)]; kw.append("json=payload")
    elif r.kind == "form":
        L += ["data = {", dict_lines([(k, [("lit", v)]) for k, v in r.form], "py"), "}"]; kw.append("data=data")
    elif r.kind == "raw":
        L += [f'data = """{r.raw}"""' if "\n" in r.raw else f'data = "{esc(r.raw, "py")}"']; kw.append("data=data")
    elif r.kind == "multipart":
        if r.form:
            L += ["data = {", dict_lines([(k, [("lit", v)]) for k, v in r.form], "py"), "}"]; kw.append("data=data")
        if r.files:
            L += ["files = {", "\n".join(f'    "{esc(k, "py")}": open("{esc(f, "py")}", "rb"),' for k, f in r.files), "}"]
            kw.append("files=files")
    if r.auth:
        kw.append(f'auth=("{esc(r.auth[0], "py")}", {render(r.auth[1], "py")})')
    kw.append(f"timeout={r.timeout or 30}")
    if not r.follow:
        kw.append("allow_redirects=False")
    if r.insecure:
        kw.append("verify=False")
    L += ["", f'resp = requests.{r.method.lower() if r.method.lower() in ("get", "post", "put", "patch", "delete", "head", "options") else "request"}('
          + (f'"{r.method}", ' if r.method.lower() not in ("get", "post", "put", "patch", "delete", "head", "options") else "")
          + ", ".join(x for x in kw if x) + ")",
          "resp.raise_for_status()", "print(resp.status_code)", "print(resp.text)"]
    return "\n".join(L)


def gen_python_stdlib(r):
    imp = ["import base64", "import json", "import os", "import ssl", "import urllib.error",
           "import urllib.parse", "import urllib.request"]
    if not r.auth:
        imp.remove("import base64")
    if not has_env(r):
        imp.remove("import os")
    if r.kind != "json":
        imp.remove("import json")
    if not r.insecure:
        imp.remove("import ssl")
    if r.kind != "form":
        imp.remove("import urllib.parse")
    L = imp + ["", f'url = "{esc(r.url, "py")}"']
    body = "None"
    if r.kind == "json":
        L += ["payload = " + py_literal(r.json_obj), 'body = json.dumps(payload).encode("utf-8")']; body = "body"
    elif r.kind == "form":
        L += ["body = urllib.parse.urlencode(" + py_literal(dict(r.form)) + ').encode("utf-8")']; body = "body"
    elif r.kind == "raw":
        L += [f'body = "{esc(r.raw, "py")}".encode("utf-8")']; body = "body"
    elif r.kind == "multipart":
        L += ['boundary = "----curl2code7MA4YWxkTrZu0gW"      # 换成随机串更稳妥', "parts = []"]
        for k, v in r.form:
            L.append(f'parts.append(("{esc(k, "py")}", None, "{esc(v, "py")}"))')
        for k, f in r.files:
            L.append(f'parts.append(("{esc(k, "py")}", "{esc(f, "py")}", open("{esc(f, "py")}", "rb").read()))')
        L += ["chunks = []",
              "for name, filename, content in parts:",
              '    disp = f\'form-data; name="{name}"\' + (f\'; filename="{filename}"\' if filename else "")',
              '    head = f"--{boundary}\\r\\nContent-Disposition: {disp}\\r\\n\\r\\n".encode("utf-8")',
              "    chunks.append(head + (content if isinstance(content, bytes) else content.encode(\"utf-8\")) + b\"\\r\\n\")",
              'chunks.append(f"--{boundary}--\\r\\n".encode("utf-8"))', 'body = b"".join(chunks)']
        body = "body"
    hdrs = list(r.headers)
    if r.kind == "json" and not any(k.lower() == "content-type" for k, _ in hdrs):
        hdrs.append(("Content-Type", [("lit", "application/json")]))
    if r.kind == "form" and not any(k.lower() == "content-type" for k, _ in hdrs):
        hdrs.append(("Content-Type", [("lit", "application/x-www-form-urlencoded")]))
    L += ["headers = {" + ("\n" + dict_lines(hdrs, "py") + "\n" if hdrs else "") + "}"]
    if r.kind == "multipart":
        L.append('headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"')
    if r.auth:
        L += [f'headers["Authorization"] = "Basic " + base64.b64encode(("{esc(r.auth[0], "py")}:" + {render(r.auth[1], "py")}).encode()).decode()']
    L += [f'req = urllib.request.Request(url, data={body}, headers=headers, method="{r.method}")']
    if not r.follow:
        L += ["", "class NoRedirect(urllib.request.HTTPRedirectHandler):   # curl 默认不跟随重定向",
              "    def redirect_request(self, *a, **kw):", "        return None"]
    ctx = ""
    if r.insecure:
        L += ["ctx = ssl.create_default_context()", "ctx.check_hostname = False", "ctx.verify_mode = ssl.CERT_NONE"]
        ctx = ", context=ctx"
    opener = "urllib.request.build_opener(NoRedirect)" if not r.follow else "urllib.request.build_opener()"
    L += [f"opener = {opener}", "try:",
          f"    with opener.open(req, timeout={r.timeout or 30}{ctx}) as resp:",
          "        print(resp.status)", '        print(resp.read().decode("utf-8", "replace"))',
          "except urllib.error.HTTPError as e:", '    print(e.code, e.read().decode("utf-8", "replace"))']
    return "\n".join(L)


def gen_fetch(r):
    L = [f'const url = "{esc(r.url, "js")}";']
    opts = [f'method: "{r.method}"']
    if r.headers:
        L += ["const headers = {", dict_lines(r.headers, "js"), "};"]
        opts.append("headers")
    if r.kind == "json":
        L += ["const payload = " + json_text(r.json_obj) + ";"]; opts.append("body: JSON.stringify(payload)")
    elif r.kind == "form":
        L += ["const body = new URLSearchParams(" + json_text(dict(r.form)) + ");"]; opts.append("body")
    elif r.kind == "raw":
        L += [f'const body = "{esc(r.raw, "js")}";']; opts.append("body")
    elif r.kind == "multipart":
        L += ["const body = new FormData();"]
        L += [f'body.append("{esc(k, "js")}", "{esc(v, "js")}");' for k, v in r.form]
        L += [f'body.append("{esc(k, "js")}", fileInput.files[0], "{esc(f, "js")}");  // 浏览器里用 <input type=file>' for k, f in r.files]
        opts.append("body")
    if r.auth:
        L += [f'headers["Authorization"] = "Basic " + btoa("{esc(r.auth[0], "js")}" + ":" + {render(r.auth[1], "js")});']
    if not r.follow:
        opts.append('redirect: "manual"')
    L += ["", "const res = await fetch(url, {", "  " + ",\n  ".join(opts) + ",", "});",
          "console.log(res.status);", "console.log(await res.text());"]
    if r.insecure:
        L.insert(0, "// -k 无法在 fetch 里表达；Node 下可设 NODE_TLS_REJECT_UNAUTHORIZED=0（仅调试）")
    return "\n".join(L)


def gen_axios(r):
    L = ['const axios = require("axios");']
    if r.kind == "multipart":
        L.append('const FormData = require("form-data");')
    if r.insecure:
        L.append('const https = require("https");')
    L.append("")
    cfg = [f'method: "{r.method.lower()}"', f'url: "{esc(r.url, "js")}"']
    if r.headers:
        L += ["const headers = {", dict_lines(r.headers, "js"), "};"]
        cfg.append("headers")
    if r.kind == "json":
        L += ["const data = " + json_text(r.json_obj) + ";"]; cfg.append("data")
    elif r.kind == "form":
        L += ["const data = new URLSearchParams(" + json_text(dict(r.form)) + ").toString();"]; cfg.append("data")
    elif r.kind == "raw":
        L += [f'const data = "{esc(r.raw, "js")}";']; cfg.append("data")
    elif r.kind == "multipart":
        L += ["const data = new FormData();"]
        L += [f'data.append("{esc(k, "js")}", "{esc(v, "js")}");' for k, v in r.form]
        L += [f'data.append("{esc(k, "js")}", require("fs").createReadStream("{esc(f, "js")}"));' for k, f in r.files]
        cfg.append("data")
    if r.auth:
        cfg.append(f'auth: {{ username: "{esc(r.auth[0], "js")}", password: {render(r.auth[1], "js")} }}')
    cfg.append(f"timeout: {int((r.timeout or 30) * 1000)}")
    if not r.follow:
        cfg.append("maxRedirects: 0")
    if r.insecure:
        cfg.append("httpsAgent: new https.Agent({ rejectUnauthorized: false })")
    L += ["", "const res = await axios({", "  " + ",\n  ".join(cfg) + ",", "});",
          "console.log(res.status);", "console.log(res.data);"]
    return "\n".join(L)


def gen_go(r):
    imp = ['"fmt"', '"io"', '"net/http"', '"time"']
    if has_env(r) or r.auth:
        imp.append('"os"')
    if r.kind in ("json", "raw", "form", "multipart"):
        imp.append('"strings"')
    if r.kind == "form":
        imp.append('"net/url"')
    if r.kind == "multipart":
        imp += ['"bytes"', '"mime/multipart"']; imp.remove('"strings"')
    if r.insecure:
        imp += ['"crypto/tls"']
    imp = sorted(set(imp))
    L = ["package main", "", "import (", *["\t" + x for x in imp], ")", "", "func main() {"]
    body = "nil"
    if r.kind == "json":
        payload = json_text(r.json_obj)
        if "`" in payload:
            L.append(f'\tpayload := "{esc(payload, "go")}"')
        else:
            L.append("\tpayload := `" + payload + "`")
        L.append("\tbody := strings.NewReader(payload)"); body = "body"
    elif r.kind == "form":
        L += ["\tform := url.Values{}"] + [f'\tform.Set("{esc(k, "go")}", "{esc(v, "go")}")' for k, v in r.form]
        L.append("\tbody := strings.NewReader(form.Encode())"); body = "body"
    elif r.kind == "raw":
        L += [f'\tbody := strings.NewReader("{esc(r.raw, "go")}")']; body = "body"
    elif r.kind == "multipart":
        L += ["\tbuf := &bytes.Buffer{}", "\tmw := multipart.NewWriter(buf)"]
        L += [f'\tmw.WriteField("{esc(k, "go")}", "{esc(v, "go")}")' for k, v in r.form]
        for k, f in r.files:
            L += [f'\tfw, _ := mw.CreateFormFile("{esc(k, "go")}", "{esc(f, "go")}")',
                  f'\t// io.Copy(fw, fileReader)  // 打开 {esc(f, "go")} 写入 fw', "\t_ = fw"]
        L += ["\tmw.Close()"]; body = "buf"
    L += [f'\treq, err := http.NewRequest("{r.method}", "{esc(r.url, "go")}", {body})',
          "\tif err != nil {", "\t\tpanic(err)", "\t}"]
    for k, v in r.headers:
        L.append(f'\treq.Header.Set("{esc(k, "go")}", {render(v, "go")})')
    if r.kind == "json" and not any(k.lower() == "content-type" for k, _ in r.headers):
        L.append('\treq.Header.Set("Content-Type", "application/json")')
    if r.kind == "form" and not any(k.lower() == "content-type" for k, _ in r.headers):
        L.append('\treq.Header.Set("Content-Type", "application/x-www-form-urlencoded")')
    if r.kind == "multipart":
        L.append("\treq.Header.Set(\"Content-Type\", mw.FormDataContentType())")
    if r.auth:
        L.append(f'\treq.SetBasicAuth("{esc(r.auth[0], "go")}", {render(r.auth[1], "go")})')
    client = [f"Timeout: {int(r.timeout or 30)} * time.Second"]
    if not r.follow:
        client.append("CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }")
    if r.insecure:
        client.append("Transport: &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}")
    L += ["\tclient := &http.Client{", *[f"\t\t{c}," for c in client], "\t}",
          "\tresp, err := client.Do(req)", "\tif err != nil {", "\t\tpanic(err)", "\t}",
          "\tdefer resp.Body.Close()", "\tout, _ := io.ReadAll(resp.Body)",
          "\tfmt.Println(resp.StatusCode)", "\tfmt.Println(string(out))", "}"]
    return "\n".join(L)


def gen_java(r):
    L = ["import java.net.URI;", "import java.net.http.HttpClient;", "import java.net.http.HttpRequest;",
         "import java.net.http.HttpResponse;", "import java.time.Duration;", "",
         "public class CurlToCode {", "    public static void main(String[] args) throws Exception {"]
    pub = "HttpRequest.BodyPublishers.noBody()"
    if r.kind == "json":
        L.append(f'        String body = "{esc(json.dumps(r.json_obj, ensure_ascii=False), "java")}";')
        pub = "HttpRequest.BodyPublishers.ofString(body)"
    elif r.kind == "form":
        L.append('        String body = "' + esc(urlencode(r.form), "java") + '";')
        pub = "HttpRequest.BodyPublishers.ofString(body)"
    elif r.kind == "raw":
        L.append(f'        String body = "{esc(r.raw, "java")}";')
        pub = "HttpRequest.BodyPublishers.ofString(body)"
    elif r.kind == "multipart":
        L += ['        String boundary = "----curl2code" + System.currentTimeMillis();', "        StringBuilder sb = new StringBuilder();"]
        for k, v in r.form:
            L.append(f'        sb.append("--").append(boundary).append("\\r\\nContent-Disposition: form-data; name=\\"{esc(k, "java")}\\"\\r\\n\\r\\n").append("{esc(v, "java")}").append("\\r\\n");')
        for k, f in r.files:
            L.append(f'        // 文件字段 {esc(k, "java")}（{esc(f, "java")}）：把文件内容按同样格式追加，二进制请改用 byte[] 拼装')
        L += ['        sb.append("--").append(boundary).append("--\\r\\n");', "        String body = sb.toString();"]
        pub = "HttpRequest.BodyPublishers.ofString(body)"
    L += ["        HttpRequest.Builder b = HttpRequest.newBuilder()",
          f'                .uri(URI.create("{esc(r.url, "java")}"))',
          f"                .timeout(Duration.ofSeconds({int(r.timeout or 30)}))",
          f'                .method("{r.method}", {pub});']
    for k, v in r.headers:
        L.append(f'        b.header("{esc(k, "java")}", {render(v, "java")});')
    if r.kind == "json" and not any(k.lower() == "content-type" for k, _ in r.headers):
        L.append('        b.header("Content-Type", "application/json");')
    if r.kind == "form" and not any(k.lower() == "content-type" for k, _ in r.headers):
        L.append('        b.header("Content-Type", "application/x-www-form-urlencoded");')
    if r.kind == "multipart":
        L.append('        b.header("Content-Type", "multipart/form-data; boundary=" + boundary);')
    if r.auth:
        L += ["        String basic = java.util.Base64.getEncoder().encodeToString(",
              f'                ("{esc(r.auth[0], "java")}" + ":" + {render(r.auth[1], "java")}).getBytes());',
              '        b.header("Authorization", "Basic " + basic);']
    L += [f"        HttpClient client = HttpClient.newBuilder()",
          f"                .followRedirects(HttpClient.Redirect.{'NORMAL' if r.follow else 'NEVER'})",
          "                .connectTimeout(Duration.ofSeconds(10))", "                .build();",
          "        HttpResponse<String> resp = client.send(b.build(), HttpResponse.BodyHandlers.ofString());",
          "        System.out.println(resp.statusCode());", "        System.out.println(resp.body());", "    }", "}"]
    if r.insecure:
        L.insert(0, "// -k：java.net.http 需自定义 SSLContext（TrustManager 全信任）才能跳过校验，生产禁用")
    return "\n".join(L)


def gen_php(r):
    L = ["<?php", "$ch = curl_init();", "$options = ["]
    opts = [f"CURLOPT_URL => '{esc(r.url, 'php')}'", "CURLOPT_RETURNTRANSFER => true",
            f"CURLOPT_CUSTOMREQUEST => '{r.method}'", f"CURLOPT_TIMEOUT => {int(r.timeout or 30)}",
            f"CURLOPT_FOLLOWLOCATION => {'true' if r.follow else 'false'}"]
    if r.headers:
        hl = ",\n".join(f"        {render([('lit', k + ': ')] + v, 'php')}" for k, v in r.headers)
        opts.append("CURLOPT_HTTPHEADER => [\n" + hl + ",\n    ]")
    if r.kind == "json":
        L = ["<?php", "$payload = " + php_array(r.json_obj, 0) + ";", "$ch = curl_init();", "$options = ["]
        opts.append("CURLOPT_POSTFIELDS => json_encode($payload, JSON_UNESCAPED_UNICODE)")
        if not any(k.lower() == "content-type" for k, _ in r.headers):
            opts.append("CURLOPT_HTTPHEADER => ['Content-Type: application/json']")
    elif r.kind == "form":
        opts.append("CURLOPT_POSTFIELDS => http_build_query(" + php_array(dict(r.form), 0) + ")")
    elif r.kind == "raw":
        opts.append(f"CURLOPT_POSTFIELDS => '{esc(r.raw, 'php')}'")
    elif r.kind == "multipart":
        fields = dict(r.form)
        items = ",\n".join([f"        '{esc(k, 'php')}' => '{esc(v, 'php')}'" for k, v in fields.items()]
                           + [f"        '{esc(k, 'php')}' => new CURLFile('{esc(f, 'php')}')" for k, f in r.files])
        opts.append("CURLOPT_POSTFIELDS => [\n" + items + ",\n    ]")
    if r.auth:
        opts.append(f"CURLOPT_USERPWD => '{esc(r.auth[0], 'php')}' . ':' . {render(r.auth[1], 'php')}")
    if r.insecure:
        opts += ["CURLOPT_SSL_VERIFYPEER => false", "CURLOPT_SSL_VERIFYHOST => 0"]
    L += [f"    {o}," for o in opts]
    L += ["];", "curl_setopt_array($ch, $options);", "$body = curl_exec($ch);",
          "$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);", "curl_close($ch);",
          "echo $code . PHP_EOL;", "echo $body . PHP_EOL;"]
    return "\n".join(L)


def php_array(obj, indent):
    pad, pad2 = " " * indent, " " * (indent + 4)
    if isinstance(obj, dict):
        if not obj:
            return "[]"
        return "[\n" + ",\n".join(f"{pad2}'{esc(str(k), 'php')}' => {php_array(v, indent + 4)}" for k, v in obj.items()) + ",\n" + pad + "]"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        return "[\n" + ",\n".join(pad2 + php_array(v, indent + 4) for v in obj) + ",\n" + pad + "]"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if obj is None:
        return "null"
    if isinstance(obj, (int, float)):
        return str(obj)
    return "'" + esc(str(obj), "php") + "'"


def gen_shell(r):
    L = ["curl -sS \\"]
    if r.method not in ("GET",):
        L.append(f"  -X {r.method} \\")
    if r.follow:
        L.append("  -L \\")
    if r.insecure:
        L.append("  -k \\")
    if r.compressed:
        L.append("  --compressed \\")
    if r.timeout:
        L.append(f"  --max-time {int(r.timeout)} \\")
    for k, v in r.headers:
        L.append(f"  -H {render([('lit', k + ': ')] + v, 'sh')} \\")
    if r.auth:
        L.append(f"  -u {render([('lit', r.auth[0] + ':')] + r.auth[1], 'sh')} \\")
    if r.kind == "json":
        L.append("  -d " + shlex.quote(json.dumps(r.json_obj, ensure_ascii=False)) + " \\")
    elif r.kind == "form":
        for k, v in r.form:
            L.append("  --data-urlencode " + shlex.quote(f"{k}={v}") + " \\")
    elif r.kind == "raw":
        L.append("  -d " + shlex.quote(r.raw) + " \\")
    elif r.kind == "multipart":
        for k, v in r.form:
            L.append("  -F " + shlex.quote(f"{k}={v}") + " \\")
        for k, f in r.files:
            L.append("  -F " + shlex.quote(f"{k}=@{f}") + " \\")
    L.append(f"  {shlex.quote(r.url)}")
    return "\n".join(L)


GEN = {"python-requests": gen_python_requests, "python-stdlib": gen_python_stdlib,
       "javascript-fetch": gen_fetch, "node-axios": gen_axios, "go-nethttp": gen_go,
       "java-httpclient": gen_java, "php-curl": gen_php, "shell": gen_shell}
FENCE = {"python-requests": "python", "python-stdlib": "python", "javascript-fetch": "javascript",
         "node-axios": "javascript", "go-nethttp": "go", "java-httpclient": "java",
         "php-curl": "php", "shell": "bash"}


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description="curl 命令转代码")
    ap.add_argument("command", nargs="?", help="整条 curl 命令（引号包住）；写 - 或留空则从标准输入读")
    ap.add_argument("--lang", choices=LANGS, default="python-requests")
    ap.add_argument("--all", action="store_true", help="输出全部 8 种语言")
    ap.add_argument("--no-env", action="store_true", help="不做环境变量替换，明文写入代码（不推荐）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    text = a.command
    if text is None or text == "-":
        text = sys.stdin.read()
    if not text.strip():
        sys.exit("没有输入：把 curl 命令作为参数，或从标准输入喂给它（pbpaste | curl_to_code.py -）")
    try:
        req = parse_curl(split_command(text), no_env=a.no_env)
    except SystemExit:
        raise
    except Exception as e:                                  # noqa: BLE001
        sys.exit(f"解析失败：{e}")

    langs = LANGS if a.all else [a.lang]
    codes = {L: GEN[L](req) for L in langs}
    if a.json:
        print(json.dumps({"request": {"method": req.method, "url": req.url,
                                      "headers": [[k, render(v, "raw")] for k, v in req.headers],
                                      "body_kind": req.kind, "timeout": req.timeout,
                                      "follow_redirects": req.follow, "insecure": req.insecure},
                          "env_vars": req.secrets, "notes": req.notes, "warnings": req.warnings,
                          "code": codes}, ensure_ascii=False, indent=2))
        return

    print(f"# {req.method} {req.url}")
    meta = [f"请求头 {len(req.headers)} 个", f"请求体 {req.kind or '无'}"]
    if req.timeout:
        meta.append(f"超时 {req.timeout}s")
    meta.append("跟随重定向" if req.follow else "不跟随重定向")
    if req.insecure:
        meta.append("跳过 TLS 校验")
    print("· " + "，".join(meta))
    for L in langs:
        print(f"\n## {L}\n```{FENCE[L]}\n{codes[L]}\n```")
    if req.secrets:
        print("\n## 环境变量（原值未写入代码）")
        for s in req.secrets:
            print(f"  {s['header']:<20} → ${s['env']:<18} 原值 {s['masked']}")
        print("  运行前先导出，例如：" + " ".join(f"export {s['env']}=…" for s in req.secrets))
        print("  别把原值提交进仓库；CI 里放到密钥管理（Secrets / Vault）中。")
    for n in req.notes:
        print(f"\n[说明] {n}")
    for w in req.warnings:
        print(f"\n[注意] {w}")


if __name__ == "__main__":
    main()
