# PartPilot · 配件查找助手

基于工业配件识别 PRD 的个人 Agent 工程项目。**72 条合成配件、3 台演示设备，非企业交付、非生产系统。**

描述需求 → 澄清设备与条件 → 显式启动检索 → 查看候选与匹配依据 → 修改条件 → 用户确认 → SQLite 保存记录。

Python + LangGraph + FastAPI + SQLite；原生 HTML/CSS/JavaScript。无需 GPU、Docker、Node 构建或外部数据库即可运行。默认解释器是**离线词法规则基线**，不是本地大模型；完整应用实际查询、更新和保存本地业务数据。

## 快速启动（Windows PowerShell）

本次环境已安装 `.venv`。直接运行：

```powershell
cd 'D:\文档\三一文档\partpilot'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --workers 1
```

打开 **http://127.0.0.1:8765**。接口文档：http://127.0.0.1:8765/docs 。按 Ctrl+C 停止前台服务。也可运行 `./scripts/start.ps1`。

首次安装（Python 3.12 推荐；本次实际为 3.12.7）：

```powershell
cd 'D:\文档\三一文档\partpilot'
New-Item -ItemType Directory -Force .tmp,.cache,artifacts | Out-Null
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $PWD '.cache/pip'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --workers 1
```

或使用 `./scripts/setup.ps1`。应用从自身文件位置解析目录，不依赖密钥或企业资料。首次启动会从 `data/catalog.json` 初始化 `runtime/partpilot.db`，重启不覆盖会话。请保持单进程 `--workers 1`；当前版本使用进程内锁与 SQLite 事务保护本地操作。

## 三分钟演示

1. **0:00–0:30** 新建查找，输入 `找液压回油滤芯`。助手要求补设备，尚未调用检索工具。
2. **0:30–1:00** 选择或输入 `设备编码 DEMO-EX-001`，点击“启动检索”。查看 PP-1001、PP-1002、名称/别名与设备匹配依据。
3. **1:00–1:40** 输入 `重量不超过2公斤`。旧候选立即失效，点击“启动检索”，只剩 1.2 kg 的 PP-1001。展开轨迹观察状态与工具摘要。
4. **1:40–2:15** 打开配件详情，检查材质、重量和层级。点击“就是这个”，再点击“确认并保存”。这是本地确认记录，不创建采购订单。
5. **2:15–2:40** 新建会话，再从历史恢复刚才会话，确认记录仍在；导出会话 JSON。
6. **2:40–3:00** 可选异常演示：输入 `重量不限`，再输入 `重量至少100公斤`，点击检索。查看实际诊断数量，再点击“仅按设备重新检索”。

## 当前能力和边界

| 能力 | 实现状态 |
|---|---|
| 文字条件、必填追问、设备有效性检查 | 已实现，离线规则验证 |
| 多轮条件修订、冲突追问、单位归一化、严格重量边界 | 已实现；`大于`与`至少`不同 |
| 配件编码、名称/别名、材质、重量、位置匹配 | 实际查询合成 SQLite 目录；词法匹配，不是向量语义检索 |
| 无结果诊断、主动回退、工具失败处理 | 已实现；诊断实际移除单项条件计算数量，未擅自放宽条件 |
| 候选详情、确认保存、幂等、会话恢复/重命名/删除/导出 | 已实现；删除界面要求确认，删除后不能恢复 |
| Qwen 结构化解析适配、预算/超时/重试/调用数限制 | 已实现；使用 MockTransport 验证，**未进行本项目真实模型端到端验证** |
| 图片上传、视觉理解、图像向量召回、爆炸图核验 | 暂缓；当前 SVG 只是类别示意，不能用于视觉验证 |
| 企业 SIS、真实配件底库、语音、多语言、多用户、专家协同 | 暂缓，不是已取消的 PRD 要求 |
| 浏览器视觉检查 | 当前工具无可用浏览器，**未完成、无截图**；已做DOM/API集成检查 |

离线解析支持明示设备编码 `DEMO-EX-001/002/003`、目录名称和别名、`材质不锈钢`、`重量不超过2000g`、`至少2公斤`、`重量不限`、`材质从不锈钢改为铝合金`。复杂省略、否定条件或任意口语不保证理解；不能用合成案例通过率宣称通用语言能力。

## 模型和费用配置

**默认预算为 0 元，默认无任何外部模型请求。** 本轮采用最新开发指令中的 0 元上限，未使用此前讨论的 50 元额度。现有环境中的 `DASHSCOPE_API_KEY` 不会在 demo 模式被读取或调用。

应用只读取进程环境变量；`.env.example` 是说明，**不自动加载 `.env`**。

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PARTPILOT_MODE` | `demo` | `demo` 或 `qwen` |
| `PARTPILOT_ENABLE_PAID_API` | `false` | 启用真实调用的独立开关 |
| `PARTPILOT_BUDGET_CNY` | `0` | 该工作库累计预算；必须大于0才可调用 |
| `DASHSCOPE_API_KEY` | 无 | 从进程环境读取，禁止提交或写入日志 |
| `PARTPILOT_MAX_CALLS` | `50` | 全工作库累计上限，重试也计数 |
| `PARTPILOT_MAX_OUTPUT_TOKENS` | `700` | 单次模型输出上限，最多2000 |
| `PARTPILOT_TIMEOUT_SECONDS` | `20` | 请求超时，最多60秒 |
| `PARTPILOT_RETRIES` | `0` | 仅网络/超时可重试，最多1次 |
| `PARTPILOT_INPUT_PRICE` / `PARTPILOT_OUTPUT_PRICE` | `0.8` / `2.7` | 每百万token人民币估算单价；启用前核对供应商价格 |

后续获得调用授权后，同时设 `PARTPILOT_MODE=qwen`、付费开关为true及正预算，再启动应用。模型固定 `qwen3.8-flash`，使用北京 DashScope OpenAI兼容端点；未做隐式旗舰模型回退。Qwen 输出经 Pydantic、原文证据、值/动作约束校验，不接收任意工具名或任意 SQL。

调用前在 SQLite 原子预留费用，响应后以 usage 更新；超时和用量未知保留预留额。费用=`输入tokens×输入单价/1e6 + 输出tokens×输出单价/1e6`。这是应用内控制，**不是阿里云账号硬限额或账单确认**；不覆盖其他应用使用同一密钥的费用。重启保留用量，切勿通过删除库重置预算。

## 验证与证据

```powershell
.\.venv\Scripts\python.exe scripts/generate_catalog.py --check
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/tests-final.xml
.\.venv\Scripts\python.exe scripts/evaluate.py
```

前端测试是可选开发依赖，应用运行不需要 Node：

```powershell
npm.cmd ci --ignore-scripts --cache .cache/npm --no-audit --no-fund
# 保持本地应用在另一个终端运行
node --check static/app.js
node scripts/test_ui.cjs
```

`./scripts/verify.ps1 -WithUI` 可组合执行；不加参数只运行Python验证。非8765端口用 `PARTPILOT_TEST_URL` 配置DOM联调。该脚本只清理它自己创建的测试会话，不删除已有会话。

当前已执行：44项Python测试通过；12个冻结离线案例通过；26项JSDOM＋真实本地HTTP检查通过。最新结果与限制以 [docs/VERIFICATION.md](docs/VERIFICATION.md) 为准。

`artifacts/` 保存JUnit、评测JSON、DOM报告、安装/服务日志和审查记录，默认不入Git。`data/eval_holdout.json` 的答案仅评测器读取，应用不加载。它是离线业务流程保留集，不是工业检索准确率评测。

## 代码阅读与面试入口

| 文件 | 重点 |
|---|---|
| `app/schemas.py` | 模型提案、证据、业务请求契约 |
| `app/agent.py` | LangGraph节点、条件路由、业务状态、冲突与结果失效 |
| `app/providers.py` | 离线规则基线、Qwen结构化解析、预算阻断与错误分类 |
| `app/tools.py` | 确定性查询、缺失值、含/不含边界、无结果诊断 |
| `app/service.py` | revision并发保护、用户确认、候选与query绑定、幂等重放 |
| `app/store.py` | SQLite快照、确认事务、持久化预算预留 |
| `app/main.py` | FastAPI入口与异常到HTTP响应的映射 |
| `static/app.js` | UI只消费服务端快照，不生成业务结果 |
| `tests/` | 需求验收、审查缺陷回归、网络模拟 |
| `docs/PLAN.md` / `docs/STATUS.md` | 需求出处、延期、验收与恢复路线 |

状态由SQLite在**完整轮次结束时**原子保存；LangGraph负责编排，不宣称实现了节点级断点恢复。确认记录和会话快照在同一事务中保存。当前可展示重点是状态一致性、工具真实性和异常处理；模型自主决策是否胜过固定流程，仍需以后在相同数据/工具上做真实模型对照实验。

## 后续建议

1. 在可用浏览器中完成桌面/小屏视觉检查并补截图。
2. 明确模型预算后跑真实Qwen场景，分别记录字段提取、错误调用、任务完成、耗时与token；不把模拟结果混入。
3. 基于公开授权图片增加图片抽取；再以实际评测决定是否引入向量检索。

不自动发布、不上传企业资料。项目仅在本地使用，公开部署前需要单独设计认证、数据隔离和并发策略。
