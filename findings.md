# 诊断证据

- 用户日志：npm 安装、锁文件供应链校验成功，@jayyuen66/dsh-scrapling 0.1.5 已加入 dependencies，失败为 entry 激活时 sidecar exited ?。
- Live Config 发现 entry include:scrapling，patchId scrapling。
- 安装目录来自 Config 查询：C:/Users/Tismi/.dsh/profiles/desktop/node_modules/@jayyuen66/dsh-scrapling。
- Config 支持 pythonBin（默认空，自动探测）、sidecarHandshakeTimeoutMs（默认30000）、integrationMode（默认 native）。
- 当前 DSH_PROFILE=desktop，DSH_PROFILE_DIR=C:/Users/Tismi/.dsh/profiles/desktop。
- 实际 shell 为 Bash，pwd=/e/答题；PATH Python 为 Python312/python，版本3.12.0；uv 0.11.14。
- 工作目录已有另一任务的 planning 文件，已读取但不覆盖，本任务记录位于 scrapling-diagnosis。
- 安装包 README 第80行要求 Python3.14+ 与 scrapling[rag]>=0.5,<0.6；当前 PATH Python3.12.0 低于说明的要求。尚需复现以判断是否为实际退出原因。
- npm tarball 不含 Python 和浏览器，无 postinstall。自带 runtime packs 安装器只验证 macOS arm64，Windows 的 packs 安装被明确 blocked，不能建议在 Windows 直接运行 setup --apply。
- 安装 manifest main=host.js，Python入口为 py/bridge.py；bundle patch 为默认配置的单一 scrapling entry。
- host.js 中实际 argv 为 [python, -u, -I, bridgePath]，Windows 自动探测 fallback 为 python.exe。
- py/bridge.py 第60至81行硬性检查 MIN_PYTHON=(3,14)，当前版本不满足时在 ready 握手前输出 stderr 并 SystemExit(78)。
- 用 PATH Python3.12.0 与相同 -u -I 参数直接执行原安装 bridge.py，立即返回 exit78；stderr明确“dsh-scrapling 需要 Python3.14+，当前3.12.0”。已复现具体根因，非 pnpm 安装失败。
- 用该解释器 -I 检查 importlib.util.find_spec，scrapling=None，patchright=None。因此升级/切换 Python 后仍需把依赖安装在选中的解释器/虚拟环境里。
- uv python list --only-installed 尝试初始化用户缓存时，访问缓存 sdists-v9/.git 失败（os error5）；此诊断无需写用户缓存，不重试或绕过，改用 Windows Python launcher 的只读版本列表。该 uv 错误与插件启动的 Python版本门槛相互独立。
- py -0p 成功，登记了3.14t、3.14（D:/python3.14.0a5）、3.12 与 uv 3.11.15；登记不等于可执行。
- D:/python3.14.0a5/python.exe 直接执行No such file（exit127），随后 py -3.14 --version 也 Unable to create process（exit101）。已确认这条登记不能启动，不能推荐直接把 pythonBin 改为该路径。
- 结论：npm包安装成功，但默认 PATH Python3.12无法通过插件3.14硬门槛；默认解释器也没有scrapling/patchright。修复需可用的稳定Python3.14+、同一解释器/venv安装scrapling[rag]>=0.5,<0.6、设置pythonBin绝对路径并重启DSH。浏览器依赖按需要另装，Windows不可用包内macOS-only setup安装器。
