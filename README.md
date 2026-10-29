# dsh-scrapling on Windows：从 `sidecar exited` 到可用

一份实测记录。目标是让 `@jayyuen66/dsh-scrapling` 在 **Windows** 上真正跑起来。

结论先说：**这个插件的 npm 包能装上，但它在 Windows 上默认一定起不来**，原因有两个，
而且都跟"装包失败"无关：

1. Python 版本门槛 —— sidecar 硬性要求 Python 3.14+，而 Windows 上 PATH 里的
   常是 3.12，插件直接 `SystemExit(78)`。
2. 系统代理写法 —— 插件会把系统代理原样交给 curl_cffi，Windows 上系统代理的
   `https` 条目常被写成 `https://127.0.0.1:7891`，但那个端口其实是 **HTTP** 代理。
   curl_cffi 于是用 TLS 去连一个 HTTP 代理，报
   `BoringSSL SSL_connect: Connection closed abruptly`。

两个问题都修掉之后，`scrapling_fetch` / `scrapling_extract` / `scrapling_answer`
实测可用（HTTP 200）。

---

## 症状长什么样

宿主日志里只有一句：

```
1 entry did not activate
scrapling (@jayyuen66/dsh-scrapling): SidecarError: sidecar exited
```

`sidecar exited ?` 里没有退出码、没有 stderr —— 因为插件把子进程的 stderr 吞掉了。
所以第一件事是**手动用插件的启动参数把 bridge.py 跑一遍**，把真实错误逼出来。

---

## 问题一：Python 3.14 硬门槛

### 定位

`py/bridge.py` 里有一段明确的检查：

```python
MIN_PYTHON = (3, 14)
...
_gate_message = check_python()
if _gate_message is not None:
    print(_gate_message, file=sys.stderr)
    raise SystemExit(78)
```

用插件真实参数复现（`-u -I` 就是 host 传的）：

```sh
python -u -I "<profile>/node_modules/@jayyuen66/dsh-scrapling/py/bridge.py"
```

输出：

```
dsh-scrapling 需要 Python 3.14+，当前 3.12.0。
请升级它，或在设置里填 3.14+ 的绝对路径。
退出码：78
```

### 修复

插件自带的一键安装器**只支持 macOS arm64**（Windows 上所有 pack 报 `blocked`），
所以 Windows 必须自己准备解释器。用 [uv](https://github.com/astral-sh/uv) 最省事：

```sh
uv python install 3.14
uv venv --python 3.14 %USERPROFILE%\.dsh-scrapling\venv
uv pip install --python %USERPROFILE%\.dsh-scrapling\venv\Scripts\python.exe "scrapling[rag]>=0.5,<0.6"
```

或者直接跑本仓库的脚本：

```sh
python setup_scrapling_windows.py
```

它会把 Python 3.14 和 venv 都装到 `%USERPROFILE%\.dsh-scrapling`，不污染系统
Python，也不碰 `AppData`（`uv` 默认缓存目录在某些机器上会 `拒绝访问`）。

> `rag` 这个 extra 不能省。默认 `extractionType` 是 `markdown`，只装 `fetchers`
> 的话第一次抓取就会在 Markdown 转换处抛 `ModuleNotFoundError`。

### 写进配置

在 profile 的 `cordis.patch.yml` 末尾追加（**注意用正斜杠**）：

```yaml
- id: scrapling
  name: "@jayyuen66/dsh-scrapling"
  config:
    pythonBin: 'C:/Users/<you>/.dsh-scrapling/venv/Scripts/python.exe'
```

用双引号 + 反斜杠会直接让 YAML 解析失败：

```
YAMLException: expected hexadecimal character
```

因为 `\U` 在双引号里被当成 Unicode 转义。

---

## 问题二：系统代理把 HTTPS 写成了 HTTPS 代理

### 定位

Python 门槛解决后，sidecar 能握手了，但一抓就报：

```
FETCH_FAILED: SSLError: curl: (35) BoringSSL SSL_connect:
Connection closed abruptly (SSL_ERROR_SYSCALL) in connection to 127.0.0.1:7891
```

排查过程（每一步都做了对照）：

| 测试 | 结果 |
|---|---|
| `curl_cffi` 直连 example.com | ✅ 200 |
| `curl_cffi` 显式传 `proxies={'http':..., 'https':...}` | ✅ 200 |
| `scrapling` 的 `Fetcher.get()` 直接调用 | ✅ 200 |
| 走插件的 `bridge.py` | ❌ SSL 错误 |

差别在插件怎么算代理。`py/guard.py` 会读系统代理：

```python
_SYSTEM_PROXIES = {'http': 'http://127.0.0.1:7891',
                   'https': 'https://127.0.0.1:7891'}
```

然后 `proxies_for()` 返回 `{"all": "https://127.0.0.1:7891"}` ——
**协议头是 `https://`，但 7891 是 HTTP 代理端口**。

验证：

```sh
# 用 https:// 前缀去连 HTTP 代理 —— 失败
Fetcher.get(url, proxies={'all': 'https://127.0.0.1:7891'})   # ❌
# 换成 http:// —— 成功
Fetcher.get(url, proxies={'all': 'http://127.0.0.1:7891'})    # ✅ 200
```

curl_cffi 看到 `https://` 前缀就以为要对代理本身做 TLS 握手，而 Clash 这类
代理的 7891 端口只接受明文 HTTP CONNECT，于是连接被直接关掉。

### 修复

在插件配置里显式写 `proxyUrl`，覆盖掉系统代理那个错误的值：

```yaml
- id: scrapling
  name: "@jayyuen66/dsh-scrapling"
  config:
    pythonBin: 'C:/Users/<you>/.dsh-scrapling/venv/Scripts/python.exe'
    proxyUrl: 'http://127.0.0.1:7891'
```

`proxyUrl` 的优先级高于系统代理，所以填了它之后 `guard.py` 不再读系统设置。

确认端口：代理软件的 HTTP 端口（Clash 默认 7890，Clash Verge 常是 7891）。
不确定就看 `netstat -ano | findstr :7891`，或者在代理软件里看"HTTP 代理端口"。

> 不用代理的话可以留空 `proxyUrl`，但要注意插件会继续读系统代理，
> 同样的问题会复现。

---

## 生效顺序（很容易踩）

**配置是插件 `apply()` 时快照的，改完必须重新加载。** 光改文件没用。

在 GUI 里关掉再打开插件即可（我用 `plugin_manager` 的 `set_bundle` 关再开，
`application: applied` 之后立刻生效，不用重启整个 DSH）：

```
plugin_manager set_bundle @jayyuen66/dsh-scrapling enabled=false
plugin_manager set_bundle @jayyuen66/dsh-scrapling enabled=true
```

验证成功的标志是工具调用能拿到 200，而不是日志里没有报错。

---

## 验证清单

```text
scrapling_fetch   https://example.com                    → HTTP 200 ✅
scrapling_extract 内联 HTML + CSS selector               → 返回元素 ✅
scrapling_answer  https://example.com + 提问              → 返回结论 ✅
```

`scrapling_render` / `scrapling_screenshot` 需要浏览器（patchright + Chromium），
本机没装，所以插件按设计**不注册**这些工具 —— 这是条件注册在工作，不是故障。
需要的话：

```sh
%USERPROFILE%\.dsh-scrapling\venv\Scripts\python.exe -m patchright install chromium
```

---

## 环境信息（实测机器）

| 项 | 值 |
|---|---|
| 系统 | Windows |
| Python | 3.14.5（uv 装的独立 CPython） |
| Scrapling | 0.5 |
| 插件 | @jayyuen66/dsh-scrapling 0.1.5 |
| 宿主 | DeepSeek Harness (desktop profile) |
| 代理 | 127.0.0.1:7891（HTTP） |

---

## 顺带发现

排查期间插件被 `dsh-defend` 的安装**连带卸载**过一次 —— pnpm 日志里是
`- @jayyuen66/dsh-scrapling 0.1.5` 和 `+ dsh-defend 0.3.25` 同一条记录。
所以"装完没生效"的时候，先确认插件还在不在 `package.json` 的
`dsh.profile.bundles` 里，别只盯着 sidecar 报错。

---

## 文件

- `setup_scrapling_windows.py` —— 一键准备 Python 3.14 + venv + Scrapling
- `findings.md` —— 完整排查记录（含每一步对照实验）
