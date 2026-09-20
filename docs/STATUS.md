# 恢复状态

## GitHub公开交付（2026-09-20）
用户明确要求推送GitHub，并选择公开仓库Rotaeno/partpilot。已通过现有Git凭据创建 https://github.com/Rotaeno/partpilot ，确认private=false，正常推送main并建立origin/main跟踪；首批远程SHA与本地af50f8d一致，无强推或其他仓库修改。README补充公开仓库克隆、首次安装及默认离线启动步骤。
发布前验证：75个跟踪文件、126个Git对象（96个blob）的历史扫描未发现凭据匹配，运行库/日志/缓存/依赖/真实.env均未跟踪（artifacts/github-preflight.json）。第三方公开BOM保留源版本、署名和GPL许可证，企业原始PRD及业务数据未进入仓库。61项Python测试通过（5.64秒，1个上游弃用警告），artifacts/tests-github-preflight.log/xml；8源文件/48条目/28章节离线完整性验证通过，artifacts/data-github-preflight.log。本次发布无模型调用。后续使用普通git push同步，不清空费用账本；GitHub公开代码仓库并非在线部署的应用。

## 加载故障修复（2026-09-20）
用户反馈“未能加载”。实查8765无监听，原父进程40656和服务进程59884均已退出，原日志仅有启动记录，无法据此确定退出原因。已恢复Qwen服务，首页/静态资源/配置/历史/健康接口均HTTP 200；账本仍100次、约0.31625元，未新增模型调用。
新增根目录Start-PartPilot.cmd，调用现有PowerShell前台启动脚本；保持窗口打开，重复启动检测现有模式/预算，不重启或清空数据库。脚本补缺失依赖/密钥提示；研究界面网络错误明确提示本地启动及重新同步。README不再假定交付时的后台进程始终存在。最新运行日志artifacts/server-recovery-stdout.log和server-recovery-stderr.log。
验证完成：`node scripts/test_research_connection.cjs`通过模拟断网→启动引导→真实本地API重连→可用会话→模型账本不变（JSDOM，非视觉验收）；`node --check static/research.js`通过。实际执行CMD入口可检测已有Qwen服务；PowerShell在8766冷启动离线服务并验证health=ok，再重复启动正确复用，最后Ctrl+C正常退出测试服务。最初重复启动将策略名offline与配置名demo直接比较，已改读health模式并复测通过。主服务8765保持Qwen模式。浏览器工具本次仍返回空inventory，未声称视觉检查。下一步：用户刷新页面；若服务今后退出，使用根目录CMD启动并保持窗口打开，无需重新安装或清空数据。

## V0.2已完成（最新优先）
用户要求找公开数据并增强Agent必要性，随后明确恢复50元总模型预算，使用qwen3.8-flash真实联调。本轮已完成实现、实际模型场景、界面联调和组合回归。所有改动仍限项目内。准确Git检查点见git log。

### V0.2里程碑更新
- 公开数据已实际获取：prusa3d/Original-Prusa-MINI commit 853bc30c4b10190f1d669ed6d0a567e333c28f21，48部件、28原文BOM章节、8源文件含完整GPL LICENSE。data/public_sources及fetch_public_data.py --verify-only逐文件SHA256/原文行号/确定性重建通过。无虚构设备适配，中文标签为派生。
- research_tools/research_llm/research_agent已实现真实function calling的decide→execute→observe循环；最多8步，来源引用、显式报告保存、revision与持久化。新/research界面已完成；/将成为新工作区，旧流程保留/baseline且强制离线。
- 实际Qwen首批6例满足预设状态/证据检查：皮带比较、轴承分装配数量、模糊追问、兼容性保留、转查完整紧固件BOM、未知电压证据不足。轨迹artifacts/research-live-smoke.json及research-live-batch.json。已有真实API费用，不再为0；统一runtime/partpilot.db usage账本累计。
- 独立审查4项及两项残留已修复并复核：最终事实从原始行生成，拒空白/拼接引用；失活owner恢复且UPDATE带旧payload CAS；失败不计成功去重。14项research+2项独立回归通过。
- 公平对照已完成：固定目录/文档各前2+一次Qwen综合，多轮共享对话；Agent 8/8、固定RAG 7/8满足开发场景要求，前7例两者都能完成。Agent通常更慢更贵，不能宣传普遍优越。R08涉及用途转术语、追加检索；初次引用未读文档失败，改进工具反馈/citation后成功，不能称为盲测。docs/AGENT_EVALUATION.md记录完整限制。
- 新界面主代理18项JSDOM+真实API+Qwen检查通过，来源/轨迹/确认保存/历史/导出均实际执行；子代理16项Mock DOM另行标注。当前外部模型账本约100次/0.31625元估算。
- 浏览器视觉验收仍未完成，当前工具inventory仍为空。没有页面截图，不用DOM快照冒充。
- README已围绕v0.2重写，默认首页为研究Agent，旧流程/baseline强制离线；启动脚本 -Online 显式使用50元/200调用/1200输出token，默认启动仍0元离线。

最终61项Python测试通过（10.86秒），artifacts/tests-v02-final.log/xml。旧界面26项DOM/API检查、新界面18项真实Qwen/API DOM检查通过；公开文件离线哈希和原文定位复验通过。原始资料Git属性设为-text，保留字节而不强制换行转换。README与实验记录完成。
最新服务：127.0.0.1:8765，研究Qwen模式（50元、200调用、1200输出token），旧/baseline离线；日志artifacts/server-v02-final-stdout.log、server-v02-final-stderr.log，父进程PID在runtime/server.pid。
本轮到此停止，不为指标继续调参。下次重点是浏览器视觉验收、新的未参与调试集，以及带查询改写的固定RAG对照。

2026-09-20，功能首版已交付。浏览器视觉验收受环境阻塞，明确未完成。

## 完成
- 读取 PRD 核心章节、上级 README/检索说明，检查目录及 Git。初始目录只有空 .git，无用户代码。
- 冻结 PLAN 的 A01–A12 验收条件；建立目录和恢复规则。
- 确定本轮外部 API 预算为 0；不使用密钥测试。Qwen 已有连接测试不等于本项目已验证。
- 已安装项目内 .venv，依赖锁定 requirements.lock.txt，安装日志 artifacts/install.log。
- 全合成目录 72 配件 / 3 设备，生成器、6 项数据测试、9 类 SVG 示意。
- SQLite 实际查询/会话/确认记录；LangGraph 解析→约束→查询→诊断→回复；Qwen结构化输出适配和预算预留；前后端 API。
- 第一轮 29 项测试全部通过（2.34秒），含6项目录测试、业务流程及MockTransport模型测试。真实模型请求为0。一个上游Starlette/AnyIO弃用警告，不影响结果。
- 独立后端审查发现7项可复现问题（artifacts/backend-review.md）；修复字段冲突误解除、材质更正、模型值/动作证据、虚假成功文本、非法response结构、严格重量边界。追加回归后44 passed（3.16秒），artifacts/tests-stage3.xml/log。
- 确认事务故障回滚和并发预算预留由审查代理额外验证通过。
- 前端HTML/CSS/JS已集成，Node语法/DOM契约/静态HTTP检查通过；新增无外部依赖的SVG配件示意。
- 主代理完成前端脚本与真实本地API联调：26检查点全部通过，覆盖显式确认与持久化、历史恢复/重命名/删除、导出、空结果/异常和输入转义。
- 冻结12个离线流程保留案例，首次执行12/12通过。不是LLM或工业检索效果指标。
- 独立复核原7项问题及15项针对性回归全部通过；报告已追加修复后结果。
- 完整README、三分钟演示、配置/费用边界、代码阅读入口和VERIFICATION已写入。
- 服务本地运行在127.0.0.1:8765，后台进程PID文件runtime/server.pid；最新日志artifacts/server-final-stdout.log、server-final-stderr.log。无需保持本轮对话才能访问已启动进程，但机器重启后需按README重新启动。
- 已创建本地Git实现检查点0153fe6；最终状态保护与交付文档在后续提交，准确版本用git log查看。密钥匹配检查0，运行数据/依赖/日志均不入Git。
- 交付前补充保护：不确定的新属性不会擦除已确认的过滤条件。最新45项Python测试全部通过（3.13秒），artifacts/tests-final.log/xml。

## 当前/下一步
首版交付停止，不再扩范围。下次恢复先读本文件和PLAN；下一步为浏览器视觉检查、用户重新确认费用后做Qwen真实模型联调，或按新指令扩展图片能力。

## 未完成
功能验收已完成，原始PRD延期项保留在PLAN和README。真实模型端到端未验证。
浏览器视觉验收阻塞：cua.createBrowserTab chrome及iab均报Browser is not available；cua.getState返回apps=[] browsers=[]。没有截图，不能声称看过页面。用户已规定无浏览器时完成可执行检查并标明限制，因此继续其他验收。

## 验证与失败
Python 3.12.7；git初始空main。最终`./scripts/verify.ps1 -WithUI`：44 passed（3.03秒）、离线案例12/12、DOM/API检查26项通过，artifacts/verification-final.log。`pip check`及锁定依赖dry-run通过。全部真实模型调用为0，工作库预算账本为0。
DOM联调初始问题：JSDOM AbortSignal与Node fetch不兼容，测试注入正确类后解决；移动历史断言未考虑前序改名，修正为明确的新标题检查。未删除失败用例或降低应用标准。

## 恢复
读 AGENTS/PLAN/STATUS，检查 git status，查看 artifacts，再继续当前阶段。不要根据计划认定功能已实现。
