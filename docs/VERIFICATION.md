# 验证记录

2026-09-20。本轮所有模型网络调用为0；演示数据全部自建合成。

## 已执行
- Python 3.12.7，FastAPI 0.141.1，LangGraph 1.2.11。完整锁定版本见 requirements.lock.txt。
- 数据：生成器 --check 通过，72配件/3设备；pytest数据断言6项。
- 后端首轮29项通过；独立审查7项缺陷修复后44项通过（artifacts/tests-stage3.log/xml）。
- 前端：Node语法检查；JSDOM执行真实app.js并与本地FastAPI联调，26项通过（artifacts/ui-dom-report.json）。涵盖设备选择、追问、真实查询、修改条件旧候选清除、详情、确认前无写入/确认后有写入、禁用重复选择、导出、历史恢复/重命名/确认删除、冲突、空结果诊断、回退、HTTP503可见、XSS转义、移动历史DOM入口。
- 保留案例：data/eval_holdout.json在实现回归后、首次运行前冻结；12/12通过（artifacts/evaluation.json）。应用不读取答案。当前报告只测离线流程，不测LLM或真实工业检索效果。
- 独立额外验证：确认写入过程中注入失败，selections与session同时回滚；重试成功。预算并发预留不能超过总额。
- 最终组合 `scripts/verify.ps1 -WithUI`：44 passed（3.03秒）、12/12、26检查点通过；完整记录 artifacts/verification-final.log，JUnit artifacts/tests-final.xml。
- 交付前补充“已确认条件不能被不确定新描述擦除”的保护及回归，最新Python测试为45 passed（3.13秒），artifacts/tests-final.log/xml。前述组合日志保留其当时44项原始结果。
- `pip check`通过；锁定依赖 `pip install --dry-run -r requirements.lock.txt --no-index`通过。格式化为可阅读源码，无新增运行依赖。
- 独立修复复核：原7项场景全部通过；15项针对性回归通过，报告已追加复核结果。

## 需求覆盖
| PLAN条目 | 证据 |
|---|---|
| A01/A07 查询→确认→保存、幂等 | test_complete_flow_and_idempotent_confirmation；DOM联调 |
| A02 必填/错误设备 | test_missing_device_asks_without_search、test_unknown_device_never_guessed |
| A03 旧查询失效 | test_changed_device_invalidates_old_query、test_concurrent_revision_rejected |
| A04 冲突 | test_conflicting_weight_blocked_and_resolved、test_unrelated_change_does_not_resolve_device_conflict |
| A05 无结果与回退 | test_no_results_diagnosis_and_explicit_fallback、H06/H12 |
| A06 异常与超时 | test_tool_error_is_not_empty_result、HTTP模拟、Qwen超时MockTransport |
| A08 单位、未知值、推断属性 | test_units_equivalent、test_unknown_weight_is_not_zero、strict_weight_boundary、uncertain_attributes |
| A09 历史恢复 | test_sessions_survive_restart_and_history_crud、DOM联调 |
| A10 预算与结构化校验 | test_providers.py；不产生真实请求 |
| A11 UI功能 | DOM/API通过；**浏览器视觉部分未完成** |
| A12 可复现与真实性 | README、锁定依赖、合成数据声明、Git检查 |

## 发现和修复
独立审查报告 artifacts/backend-review.md 保留修复前问题和复核。修复包含：设备冲突只由对应字段更正解除；材质更正使用新值；模型证据子串校验扩展为值/动作约束；模型自由question不作为最终回答；非法JSON外壳统一受控错误；严格重量边界被正确处理。

DOM测试最初失败源于Node fetch拒绝JSDOM的AbortSignal类型，注入Node对应类型后解决；这不是应用浏览器缺陷。移动历史断言仍期待旧名称而前序已重命名，改为检查明确的新名称，未降低应用验收标准。失败记录在 artifacts/ui-dom-failure.html 与阶段日志。

## 未验证与阻塞
- 浏览器工具两次尝试分别返回Chrome/IAB不可用，inventory为apps=[]、browsers=[]。未通过其他方式假冒视觉检查，无页面截图。
- DOM快照 artifacts/ui-dom-snapshot.html **不是截图**，不能证明实际布局、字体、滚动或移动端表现。
- Qwen adapter仅MockTransport测通；本轮没有真实LLM end-to-end、图像理解或工业数据效果指标。
- 上游Starlette测试工具存在1条AnyIO弃用警告，测试正常通过。

## 后续对照设计
同一份未参与调试的新测试集和相同工具，对比表单固定流程、LLM抽取+固定流程、受限Agent动作选择；记录错误候选确认、无效工具调用、澄清轮次、条件残留、耗时和费用。优先研究显式版本状态是否减少旧候选误确认，不预先假设Agent优于固定流程。现有12例已公开且执行，继续调试后不能再称全新盲测集。
