# 需求与实施计划

## 来源和边界
只读来源：`../配件识别V2.0 PRD设计（三一项目视角）.docx`（2026-06-22 V2.0）。定位使用章节名及 Word XML 非空/空段落顺序的原始段落编号，不是假定页码。
- 122–160：销服维修/采购；设备编码为起点；输入含图文语音。
- 228–329「模型反问」：填槽、来源区分、必填追问、冲突澄清；仅设备编码也能检索。
- 334–400「检索逻辑说明」：编码精准筛选、用户字段与模型描述区分、单位归一化、图文召回、图片复核。
- 403–451「结果展示/结果确认」：候选、层级、详情、就是这个。
- 455–493「二次检索」：修改后确认启动、回退至设备范围、无结果原因。
- 495–519：历史会话、账号隔离、SIS及无图片配件也应检索。

本次交付：中文、单用户、本地、文字主线、合成数据。PRD 的图片拍摄/框选/视觉校验、爆炸图交互、真实 SIS、语音、多语言、多人账号隔离、专家协同延期，未取消。首版以层级路径替代展示位置，不宣称爆炸图核验。不得引用企业完成率目标作为个人实测指标。

现有包含训练/检索快照，不含完整模型/索引；样例注明未经脱敏。本项目重新实现小型词法检索，只参考业务，不直接复制企业代码/数据。目录原本仅有未提交的空 Git 仓库，无用户代码或适用 AGENTS。

## 架构与接口（主代理维护）
FastAPI 单进程 + LangGraph 状态图 + SQLite 原子持久化 + 静态原生前端。
模型接口 `interpret(text, current_slots) -> Proposal`。离线规则解析和 Qwen 结构化输出共用 Proposal；离线模式明确不称真实 LLM。
状态：id/title/status/revision/slots/pending_conflicts/messages/results/query_id/query_revision/total/diagnostics/trace/selection。
slots: equipment_code、name、part_code、material、max_weight_kg、min_weight_kg、location；每项 `{value, source, confirmed, inclusive}`。inclusive对重量表示是否含边界；不确定新描述不能擦除原有已确认条件。conflict_map按字段保存未解除冲突，advisories记录保留旧条件的提示。
动作：message（解析并提出条件，候选失效）、search（用户显式启动）、fallback（用户选择仅设备）、confirm（用户选择当前候选）、clear_slot。
工具：lookup_equipment、search_parts、get_part_details、diagnose_no_results、confirm_selection。只读工具无写入副作用；confirm 原子写入并按会话/查询唯一键幂等。工具返回结构化证据，回复由证据构造。

### API contract
- GET /api/config -> `{mode, model, budget_cny, external_calls_enabled, equipment_count, part_count}`
- GET /api/equipment -> `{items:[{code,model,name,description}]}`
- GET /api/sessions -> `{items:[{id,title,status,updated_at}]}`
- POST /api/sessions `{}` -> full session
- GET /api/sessions/{id} -> full session
- POST /api/sessions/{id}/turn `{action:'message'|'search'|'fallback'|'clear_slot',text:'',slot:null, expected_revision:int}` -> full session
- POST /api/sessions/{id}/confirm `{part_id,query_id,expected_revision}` -> full session
- PATCH /api/sessions/{id} `{title}` -> full session
- DELETE /api/sessions/{id} -> `{deleted:true}` (history confirmation cascades)
- GET /api/parts/{id} -> full part
- GET /api/sessions/{id}/export -> JSON session and audit
- GET /api/health -> status
Errors `{detail: human_message}` with 404/409/422/503. Tool failure becomes session.status=error, no false no-results.
Session messages `{role,content,at}`; trace `{tool,status,summary,elapsed_ms,at}`. Results array part objects + `reasons:[str]`; no fabricated confidence percentages. Status: collecting/ready/results/no_results/conflict/error/confirmed.

### Data schema
`data/catalog.json`: `{meta:{synthetic:true,description,version},equipment:[{code,model,name,description}],parts:[{id,name,aliases:[str],category,material,weight_kg:number|null,dimensions_mm:[number,number,number]|null,equipment_codes:[str],assembly_path:[str],description,illustration:'filter'|'pump'|'valve'|'bolt'|'seal'|'bearing'|'hose'|'sensor'|'motor',source:'synthetic'}]}`.
Equipment: DEMO-EX-001/002/003. No real company name, material codes or photos. Parts IDs PP-1001 etc. Three equipment, 60–120 sensible records; lookalikes, parent/child, absent weight/image.

## Frozen acceptance (before implementation)
A01 enough information -> explicit search -> database candidate -> explicit confirmation persisted.
A02 missing equipment -> ask, no retrieval; unknown equipment -> clarification, no guessing.
A03 change constraints/device -> invalidate old query, old candidate confirmation rejected, next search uses new state.
A04 contradictory min/max or two equipment in one utterance -> no search until resolved.
A05 zero candidates -> actual per-condition diagnostic counts; no silent relaxation; fallback preserves only equipment.
A06 tool failure/timeout -> visible error and retry; never labeled no results.
A07 duplicate confirm -> same record; stale/query mismatch/candidate mismatch -> rejected.
A08 units g/kg -> equivalent filtering; unknown weight not treated as zero; model inferred attributes not hard filters.
A09 sessions survive new app/store instance; history rename/delete works; new session isolated.
A10 zero budget blocks Qwen request before networking; structured outputs validated; limited outputs/retries/timeouts and persisted usage reservation.
A11 responsive UI: empty/loading/error/results/detail/confirmed; keyboard enter; all visible action buttons work; browser screenshots and core flow checked.
A12 instructions reproducible, no credentials/private data, no external API calls, deterministic test artifacts and stated limitations.

## Milestones
1 records + data + database + minimal API/UI startup.
2 LangGraph, model adapters, state versioning and persistence.
3 frozen acceptance tests, exceptions and review fixes.
4 UI polish and actual browser check.
5 full regression, clean-start check, evidence + README + Git checkpoint.

## Decisions
- FastAPI plus vanilla frontend avoids a Node build chain while allowing complete custom UX.
- Explicit start-search matches PRD secondary-search confirmation; parsing is not database execution.
- Re-run small local query after changes; defer cached-stage reuse to avoid stale data.
- SQLite stores per-turn graph snapshot and audit atomically; no mid-node resume or claim of LangGraph checkpointer persistence.
- Synthetic keyword/alias retrieval is a baseline, not semantic embeddings or visual retrieval.
- Latest instruction sets this implementation run's external API budget to 0; prior one-request Qwen connectivity test is not Agent E2E validation.
