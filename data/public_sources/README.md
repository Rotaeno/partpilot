# 公开配件资料：Original Prusa MINI BOM 快照

这是真实公开硬件项目的物料清单摘录，**不是模拟数据，也不是三一设备业务数据**。不能把此处零件描述成适配挖掘机或企业生产设备，也不能把官方旧版本清单视为当前产品库存。

- 上游：[PRUSA RESEARCH 官方 Original-Prusa-MINI 仓库](https://github.com/prusa3d/Original-Prusa-MINI)。
- 固定 commit：`853bc30c4b10190f1d669ed6d0a567e333c28f21`。
- 许可：仓库根目录 `LICENSE` 为 **GNU GPL v3**；本目录保留完整原文于 `raw/LICENSE`。上游 BOM 作者署名归 PRUSA RESEARCH / prusa3d contributors。公开可访问本身不被当作复制许可。
- 修改说明：PartPilot 从 Markdown 表格提取行，增加本地标识、中文翻译和证据定位。`raw/` 不作修改；派生资料遵循所保留的上游许可。提取脚本 `scripts/fetch_public_data.py` 是可修改、可复现的派生生成来源。
- 未下载：BOM 中链接的 PDF、第三方数据手册、图像、其他仓库。仅保留链接不意味着这些资料已经读过、其许可已经核查或内容可用于回答。

## 文件与复现

| 文件 | 内容 |
|---|---|
| `source_manifest.json` | 来源、固定版本、获取时间、许可、每个原始文件的字节数及 SHA256 |
| `normalized_parts.json` | 48 个真实 BOM 出现条目，含原名、派生中文名、所属装配及数量 |
| `evidence_docs.json` | 28 个完整原文章节，含行号、源链接、原始哈希及部件 ID 关联 |
| `raw/BOM/*.md` | 6 份原始 BOM 的完整字节快照 |
| `raw/README.md`、`raw/LICENSE` | 仓库原始说明和许可 |

在项目根目录执行：

```powershell
# 重新获取固定版本的8个文本文件，不需要密钥、模型或额外依赖
.venv/Scripts/python scripts/fetch_public_data.py

# 完全离线：核对哈希、原文行、数量范围及确定性重建
.venv/Scripts/python scripts/fetch_public_data.py --verify-only
```

验证报告写入 `artifacts/public-data/verification.json`。原始文件 SHA256 应保持一致；重新获取时 manifest 的获取时间允许变化。

## 字段与证据边界

- `name_original`、`raw_specification`、`raw_row` 和 `quantity` 来自原表格；数量是**该装配章节的清单数量**，不是库存、采购建议或去重后的整机数量。
- `name_zh`、`assembly_zh`、中文别名是本项目派生翻译，已明确标记。原始引用应使用 `raw_row` 或文档 `text`。
- `id` 是本项目本地证据条目标识，**不是制造商料号**；`manufacturer_part_number` 保持 `null`。
- `weight_kg`、`dimensions_mm`、`material` 没有经结构化解析或外部核验，保持 `null`；即使部件原名包含尺寸或材质，也只原样保留在 `raw_specification`，避免误释型号为参数。
- `source_line_start/end` 是原 Markdown 的 1 基行号，文档 `line_start/end` 同理；原始文件按 SHA256 检查。
- 同名零件在不同装配章节出现时不自动合并。比如 X 轴 `LM8UU linear bearing` 数量为 2，Y 轴为 3。这能回答各章节清单事实，不能独立证明更换兼容性。
- X 轴清单列 `X-axis belt 561 mm`，Y 轴列 `Y-axis belt 496 mm`。可以比对原文长度，不能据此认可两者互换。
- 48 条索引选择规则：所有 `STANDARD PARTS` / `CUSTOM PARTS`，排除纺织护套；额外收录四个轴电机。28 个原文章节保留紧固件等完整信息。**索引不是完整购机 BOM，也不以未被索引表示源文档不存在。**
- 一个固定仓库快照不能证明所有 MINI / MINI+ 版本均通用。未知替代件、现售版本、未摄取的数据手册、电压、维修安全操作应明确证据不足。

## 已执行验证

本次抓取与离线复验检查 8 个源文件哈希、48 个唯一部件标识、28 个章节与源行切片完全一致、每个条目对应原始行及文档，核对 X/Y 轴承数量和皮带长度的快照事实。结果以 `artifacts/public-data/verification.json` 的实际输出为准。外部模型调用为 0。
