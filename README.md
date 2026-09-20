# PartPilot · 公开配件查证 Agent

从工业配件识别 PRD 出发的个人项目：理解问题，按工具观察继续检索公开 BOM、查阅原文、比较条目、追问或保留未知，最后由用户保存查证报告。

**Python + LangGraph + FastAPI + SQLite，单 Agent，原生网页。** 已用 `qwen3.8-flash` 做真实 Function Calling 与端到端联调。无需 GPU、向量数据库、Docker 或前端构建服务。

- `/`、`/research`：官方 Original Prusa MINI 固定开源 BOM，**48 个真实部件出现条目、28 个完整原文章节**，附来源、行号、哈希和 GPL 许可。
- `/baseline`：保留 **72 条合成配件、3 台模拟设备**，始终使用离线规则检索与确认保存。

这是业务背景启发的个人研究项目。公开3D打印机部件不代表三一设备适配、公司交付、真实用户或生产指标。

## 安装和启动

首次下载后先按下方命令安装依赖。安装完成并配置密钥后，**双击项目根目录的 `Start-PartPilot.cmd`** 启动真实 Qwen 模式，然后在浏览器打开 **http://127.0.0.1:8765/**。使用期间保持启动窗口打开；关机或服务退出后需要重新启动。重复启动会检测正在运行的 PartPilot，不会再占用同一端口。

如果页面提示“未能加载”或无法连接，先重新启动上述文件，再刷新页面（已打开的工作区也可点击“重新同步”）。不要直接双击 `static/research.html`；网页需要本地服务提供接口。历史记录和费用账本仍保存在 `runtime/partpilot.db`，重启不会清空。

在 Windows PowerShell 下载并启动（需要 Python 3.12 和 Git）：

```powershell
git clone https://github.com/Rotaeno/partpilot.git
cd partpilot
# 首次安装时执行
.\scripts\setup.ps1
# 默认离线启动，不需要密钥，不产生模型费用
.\scripts\start.ps1
```

真实模型模式需要自行在环境中配置 `DASHSCOPE_API_KEY`，再停止离线服务并执行：

```powershell
# 50元为此工作库的累计应用预算；启动本身不调用模型
.\scripts\start.ps1 -Online -BudgetCny 50
```

没有密钥或不希望产生模型费用时，运行 `./scripts/start.ps1`。此时研究工作区是明确标注的离线策略，**不是本地大模型**；旧基线始终离线。按 Ctrl+C 停止前台服务。接口文档在 `/docs`。

手动安装和启动（本次 Python 3.12.7 验证）：

```powershell
New-Item -ItemType Directory -Force .tmp,.cache,artifacts | Out-Null
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $PWD '.cache/pip'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
# 默认离线，不调用模型
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --workers 1
```

请保留 `--workers 1`。数据库是 `runtime/partpilot.db`；研究流程每步保存，确认报告使用事务，重启不覆盖历史。旧进程中断可恢复为可重试状态，GET 不能覆盖刚完成的报告。

## 三分钟演示

1. 首页确认显示 Qwen、公开来源与许可。
2. 点击用途描述例题：「送丝时咬住塑料丝往里推的那个带齿小轮……不知道英文术语」。观察实际检索词、工具步骤、追加查阅和证据定位；通常数秒到数十秒，模型结果可能波动。
3. 展开原文引用，核对到固定 GitHub 版本的行号。最终数量从被验证的原始表格行生成，不使用模型自由摘要猜数字。
4. 点击“保存查证报告”并确认；新建查证后从历史恢复，导出 JSON。
5. 再试「我想换个轴承，但不知道型号，应该先确认什么？」并回答追问；或询问「这个BOM能确定电机额定电压是48V吗？」观察证据不足。

旧基线：`/baseline` 输入“找液压回油滤芯”→补 `DEMO-EX-001`→检索→输入“重量不超过2公斤”→重新检索→确认保存。此处数据为合成。

## Agent 的价值与限制

v0.1 的填槽/过滤是固定流程；v0.2 模型根据观察选择下一工具、改写查询、补查原文、追问或结束。确定性代码负责工具执行、引用验证、数量展示和写入。

我们使用相同 Qwen、资料和工具的固定 RAG 对照：原问题检索目录与文档各一次、各读前2项，再由一次 Qwen 综合，且保留对话上下文。8个开发场景中，Agent 8/8、固定 RAG 7/8满足预定义状态/证据条件；前7题两者都能完成。用途描述题中 Agent 继续查证找到了原文，固定 RAG 请求更多信息。

**不是盲测或工业效果结论。** Agent 通常更慢、更贵（所选运行平均17.02秒 vs 7.89秒）；不能宣称普遍优于 RAG。R08参与过调试，早期失败保留。实验细节与下一步对照见 [docs/AGENT_EVALUATION.md](docs/AGENT_EVALUATION.md)。下一步应加入“带查询改写的固定RAG”，分离语言改写与动态工具编排的收益。

## 公开数据

来自官方 `prusa3d/Original-Prusa-MINI`，commit `853bc30c4b10190f1d669ed6d0a567e333c28f21`。完整 GPL v3 随原始资料保留，中文名称是派生翻译，本地ID不是厂家料号。未知重量、材质、尺寸保持 null。

```powershell
# 无网络：原始哈希、原文行和确定性重建
.venv/Scripts/python scripts/fetch_public_data.py --verify-only
# 从公开上游重新获取固定版本，不调用模型
.venv/Scripts/python scripts/fetch_public_data.py
```

详见 [数据与许可说明](data/public_sources/README.md)。48条索引不是完整采购清单；紧固件等可通过28个完整章节检索。数量属于对应装配段落，不是库存。链接PDF、第三方参数表未摄取，不能据BOM认定替换兼容或当前产品适配。

## 费用与配置

默认 `Settings()` 为0预算离线；`start.ps1 -Online` 显式设置50元上限、200次累计调用、1200输出token。所有真实研究评测写同一份持久化 `usage` 账本。原子预留费用，返回后按usage记账；超时和未知用量保留预留额。应用额度不是阿里云硬额度，不覆盖其他应用使用同一密钥的费用，不要删库绕过预算。

| 环境变量 | 普通默认值 | 含义 |
|---|---|---|
| PARTPILOT_MODE | demo | 研究策略 demo / qwen |
| PARTPILOT_ENABLE_PAID_API | false | 独立调用开关 |
| PARTPILOT_BUDGET_CNY | 0 | 工作库累计预算 |
| DASHSCOPE_API_KEY | 无 | 仅从进程环境读取 |
| PARTPILOT_MAX_CALLS | 50 | Online脚本设200，重试计入 |
| PARTPILOT_MAX_OUTPUT_TOKENS | 700 | Online脚本设1200，最多2000 |
| PARTPILOT_TIMEOUT_SECONDS | 20 | 单次超时，最多60秒 |
| PARTPILOT_RETRIES | 0 | 网络/超时最多重试1次 |
| PARTPILOT_INPUT_PRICE / PARTPILOT_OUTPUT_PRICE | 0.8 / 2.7 | 每百万token人民币估算单价，使用前核对供应商 |

`.env.example` 仅说明，不自动加载 `.env`。模型固定 qwen3.8-flash，无旗舰模型隐式回退。每轮最多8次决策；仅可访问允许的本地资料工具，不执行Shell、任意SQL或任意URL。模型不能自行保存报告。所有配件数量来自已读的真实原文行，而非自由摘要。

## 验证与产物

```powershell
# 不产生模型费用
.\scripts\verify.ps1
# 前端开发测试依赖；应用运行无需Node
npm.cmd ci --ignore-scripts --cache .cache/npm --no-audit --no-fund
# 保持应用运行，旧界面离线检查
node scripts/test_ui.cjs
# 断网提示与重新连接（JSDOM + 真实本地API，不调用模型）
node scripts/test_research_connection.cjs
# 以下会调用真实Qwen，计入授权账本
node scripts/test_research_ui.cjs --live
.venv/Scripts/python scripts/evaluate_research.py --live --output artifacts/new-agent-eval.json
.venv/Scripts/python scripts/evaluate_research.py --fixed-rag --output artifacts/new-fixed-eval.json
```

原业务45项、研究及审查回归16项；旧界面26项 DOM/API 检查、新界面18项真实 Qwen/API DOM 联调；公开资料复验与8个开发场景对照。最新完整结果见 [验证记录](docs/VERIFICATION.md)。原始轨迹、JUnit、费用、DOM快照和失败记录在 `artifacts/`，不入 Git。

**浏览器视觉验收未完成**：浏览器工具无连接。JSDOM验证了脚本、控件和API联动，不能证明布局、字体、滚动和移动设备效果；没有页面截图。

## 代码阅读入口

| 文件 | 职责 |
|---|---|
| app/research_agent.py | decide→execute循环、策略对照、报告保存、中断恢复 |
| app/research_llm.py | 原生Function Calling、预算/用量、错误分类 |
| app/research_tools.py | 公开检索/原文/比较、工具schema、来源引用 |
| app/main.py | 新旧工作区API |
| app/store.py | 原业务快照与共享费用账本 |
| static/research.js | 实时轮询、引用、显式保存与恢复 |
| scripts/fetch_public_data.py | 可复现公开数据获取及校验 |
| scripts/evaluate_research.py | 开发场景和固定RAG对照，不传gold给模型 |
| app/agent.py、tools.py、service.py | 原离线基线状态、检索、幂等确认 |
| docs/PLAN.md、STATUS.md | PRD定位、范围、决策、失败与恢复 |

本轮仍暂缓图片理解、图像向量检索、爆炸图核验、真实SIS、库存/采购系统、多用户、多语言和公开部署。先补真实浏览器检查，再用未参与调试的新问题检验增量收益。
