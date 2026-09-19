# Agent做了什么，以及它何时值得使用

2026-09-20，Qwen3.8-Flash真实调用。数据为官方Prusa MINI固定BOM快照，不是三一业务数据。

## 从固定流程到可变查证
v0.1是填槽/过滤/确认的固定流程，LangGraph本身不证明Agent必要。
v0.2允许模型根据实际观察选择search_catalog、search_documents、read_part、read_document、compare_parts、ask_user、finish_report。工具参数有schema，已读证据与本轮状态受代码限制；最多8次决策，未知工具不执行，成功调用不重复，失败可在步数预算内重试。

案例：用户描述「送丝时咬住塑料丝往里推的带齿小轮」，未提供英文术语。真实轨迹先尝试英文检索，搜索不同术语，再读E轴BOM、定位MINI filament spur并形成原文引用。这里的作用是按观察改写检索、寻找下一份证据，而不是预先写死返回某条配件。

报告中的数量/规格从被校验的原文行确定性生成，模型负责定位/选证据/追问；不将模型自由摘要当作确定事实。模型匹配出的候选与用户描述是否完全对应，仍需要人核对，不能从型号名称推断物理适配。

## 公平一些的固定RAG对照
主要对照使用相同Qwen、相同公开资料、同一检索实现及相同引用校验：原问题检索目录和文档各一次，各读取前2项，再用一次Qwen综合。多轮保留同样的对话上下文。它没有模型驱动的查询改写和追加检索。

最初的纯词法首条命中基线过弱，不用它作为主要优越性证据。固定RAG初版曾因历史tool消息让模型调用不再提供的工具而失败，修复为单次context输入后再评测；失败日志保留，不能拿实现缺陷抬高Agent结果。

| 场景 | Agent | 固定RAG | Agent / 固定RAG耗时 |
|---|---|---|---|
| R01 X/Y皮带规格 | 满足证据条件 | 满足 | 10.46 / 7.44秒 |
| R02 X/Y的LM8UU数量 | 满足 | 满足 | 15.60 / 8.03秒 |
| R03 轴承型号不明，追问 | 满足 | 满足 | 4.43 / 5.32秒 |
| R04 替换兼容不能只凭BOM | 满足 | 满足 | 18.59 / 13.84秒 |
| R05 选摘目录外的Z轴紧固件原文 | 满足 | 满足 | 13.49 / 6.54秒 |
| R06 未摄取电压参数，证据不足 | 满足 | 满足 | 18.28 / 9.30秒 |
| R07 追问后只补X轴 | 满足 | 满足 | 29.87 / 10.11秒（两轮） |
| R08 不知道术语的用途描述 | 满足（修复后） | 需继续补充，未找到目标证据 | 25.47 / 2.53秒 |

这些是**8个开发场景，各取一次实测，不是盲测或统计结论**。Agent 8/8、固定RAG 7/8满足预定义状态/证据要求；固定RAG在R08的追问是安全行为，不是编造答案。前7例说明仅靠这些任务并不能证明必须使用Agent。

被选结果的平均耗时17.02秒 vs 7.89秒；模型费用估算合计0.0921212元 vs 0.0208874元。Agent通常更慢、更贵；不用调用次数多来证明价值。下一步应在新的未参与调试数据上比较「带查询改写的固定RAG」与Agent，分离查询改写和动态工具编排的贡献。当前只能说明一个可运行的适用场景，不能声称普遍优于RAG。

## 不隐藏失败
R08初次在第7/8步引用了未读取的打印件文档，被引用校验阻止并达到上限。修复是工具返回可直接采用的原始citation、错误明确指出哪个证据未读，并要求只选必要证据；没有放宽验证、硬编码该问题答案或提高8步上限。此后目标案例成功，但已参与调试，不能再称保留盲测。

独立审查还修复：空白引用绕过；拼接多行伪造复合部件；自由摘要编造数量；中断进程遗留working；GET旧快照覆盖刚完成的报告（CAS修复）；暂时工具失败被永久去重。原复现、修复和针对测试保留于artifacts/research-review.md。

## 如何复现
默认回归不调用外部模型：

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/fetch_public_data.py --verify-only
```

下列命令真实计费，使用环境DASHSCOPE_API_KEY，累计写入同一个项目usage账本，50元/200次上限：

```powershell
.venv/Scripts/python scripts/evaluate_research.py --live --output artifacts/new-agent-eval.json
.venv/Scripts/python scripts/evaluate_research.py --fixed-rag --output artifacts/new-fixed-rag-eval.json
node scripts/test_research_ui.cjs --live
```

每次重跑可能不同。API usage计算的是配置单价下估算，不是云端账单。测试gold仅评测脚本读取，不传给模型。人工还需要判断引用是否切题、追问是否有用；自动引用匹配不能证明语义充分性。

当前原始证据：research-agent-final.json、research-agent-paraphrase-fixed.json、research-fixed-rag-v3-smoke.json、research-fixed-rag-v3-batch.json、research-fixed-rag-multiturn.json、research-fixed-rag-paraphrase.json、research-comparison.json，均在artifacts目录。所有较早失败运行也保留。
