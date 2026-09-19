"""Generate a deterministic, entirely fictional maintenance-parts catalogue.

No source documents, company records, model calls or network access are used.
Run this file normally to rebuild catalog.json, or with --check to verify it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "catalog.json"
ILLUSTRATION_KINDS = {
    "filter",
    "pump",
    "valve",
    "bolt",
    "seal",
    "bearing",
    "hose",
    "sensor",
    "motor",
}

# These are synthetic teaching specifications, not fitment recommendations.
# Each tuple supplies: name, aliases, category, material, weight kg, dimensions
# in mm, subsystem, assembly, illustration, description.
RECIPES = [
    (
        "液压回油滤芯",
        ["回油滤芯", "液压滤芯", "回油滤", "油滤芯"],
        "滤芯",
        "玻璃纤维",
        1.2,
        [90, 90, 180],
        "液压系统",
        "液压滤清器总成",
        "filter",
        "短筒型可更换滤芯；用于回油过滤。需要按设备范围和尺寸核对。",
    ),
    (
        "液压回油滤芯",
        ["回油滤芯", "液压滤芯", "长款滤芯", "回油滤"],
        "滤芯",
        "不锈钢",
        2.4,
        [110, 110, 260],
        "液压系统",
        "液压滤清器总成",
        "filter",
        "长筒型可更换滤芯；与短筒款名称相同但材质和尺寸不同。",
    ),
    (
        "液压滤清器总成",
        ["液压过滤器", "回油滤清器", "回油滤总成", "过滤器总成"],
        "总成",
        "铝合金",
        5.6,
        [180, 180, 350],
        "液压系统",
        None,
        "filter",
        "含壳体、端盖和滤芯的总成示例；采购总成与仅采购滤芯应明确区分。",
    ),
    (
        "空气滤芯外芯",
        ["空气滤芯", "空气滤清器外芯", "外空气滤", "空滤"],
        "滤芯",
        "纸质复合材料",
        0.85,
        [150, 150, 280],
        "动力系统",
        "进气滤清器总成",
        "filter",
        "发动机进气用外层滤芯；外观类似回油滤芯但不属于液压系统。",
    ),
    (
        "空气滤芯内芯",
        ["空气滤芯", "空气滤清器内芯", "安全滤芯", "内空气滤"],
        "滤芯",
        "无纺布",
        None,
        [90, 90, 250],
        "动力系统",
        "进气滤清器总成",
        "filter",
        "进气安全滤芯；演示目录未登记重量，未知值不能当作零。",
    ),
    (
        "液压主泵",
        ["液压泵", "主泵", "柱塞泵", "油泵"],
        "泵",
        "铸铁",
        38.0,
        [330, 250, 260],
        "液压系统",
        "主泵总成",
        "pump",
        "液压系统动力元件；用于演示同名部件在不同设备上的规格差异。",
    ),
    (
        "液压泵密封组件",
        ["泵密封包", "主泵修理包", "液压泵密封圈", "泵密封件"],
        "密封件",
        "氟橡胶",
        0.18,
        [160, 120, 25],
        "液压系统",
        "主泵总成",
        "seal",
        "主泵维修用密封组件，不含液压泵本体。尺寸指演示包装外廓。",
    ),
    (
        "先导电磁阀",
        ["电磁阀", "先导阀", "液压电磁阀", "换向阀"],
        "阀",
        "不锈钢",
        0.72,
        [110, 45, 55],
        "液压系统",
        "先导阀组",
        "valve",
        "先导控制阀组中的电控阀；线圈电压和接口需在真实应用另行核验。",
    ),
    (
        "液压减压阀",
        ["减压阀", "压力控制阀", "调压阀"],
        "阀",
        "碳钢",
        0.48,
        [75, 35, 35],
        "液压系统",
        "先导阀组",
        "valve",
        "调节支路压力的阀件；不能凭名称替代先导电磁阀。",
    ),
    (
        "回油口O形密封圈",
        ["密封圈", "O形圈", "O型圈", "回油密封圈"],
        "密封件",
        "丁腈橡胶",
        0.015,
        [65, 65, 4],
        "液压系统",
        "液压滤清器总成",
        "seal",
        "回油口密封件；与金属垫圈名称相似但材料及用途不同。",
    ),
    (
        "油缸防尘密封圈",
        ["防尘圈", "油缸密封圈", "刮尘圈", "密封圈"],
        "密封件",
        "聚氨酯",
        0.035,
        [80, 80, 8],
        "工作装置",
        "动臂油缸总成",
        "seal",
        "动臂油缸杆端防尘件；用于演示同为密封圈时的位置澄清。",
    ),
    (
        "六角头螺栓",
        ["螺栓", "六角螺栓", "螺丝", "紧固件"],
        "紧固件",
        "碳钢",
        0.08,
        [17, 17, 50],
        "车身结构",
        "检修盖板",
        "bolt",
        "检修盖板安装紧固件；材料相同也必须核对螺纹规格。",
    ),
    (
        "六角锁紧螺母",
        ["螺母", "锁紧螺母", "六角螺母", "紧固件"],
        "紧固件",
        "碳钢",
        0.02,
        [17, 17, 10],
        "车身结构",
        "检修盖板",
        "bolt",
        "盖板锁紧螺母；不是螺栓或垫圈。",
    ),
    (
        "平垫圈",
        ["垫圈", "平垫", "垫片", "紧固件"],
        "紧固件",
        "不锈钢",
        0.006,
        [20, 20, 2],
        "车身结构",
        "检修盖板",
        "bolt",
        "金属紧固垫圈；与橡胶密封圈有区别。",
    ),
    (
        "深沟球轴承",
        ["轴承", "球轴承", "滚动轴承"],
        "轴承",
        "轴承钢",
        0.31,
        [72, 72, 19],
        "动力系统",
        "冷却风扇总成",
        "bearing",
        "冷却风扇支撑轴承；外廓尺寸只用于示例检索。",
    ),
    (
        "回转支承",
        ["转盘轴承", "回转轴承", "大轴承", "回转支撑"],
        "轴承",
        "合金钢",
        62.0,
        [600, 600, 70],
        "回转系统",
        "回转支承总成",
        "bearing",
        "上车与底盘之间的支承部件；与小型球轴承用途不同。",
    ),
    (
        "动臂高压软管",
        ["液压软管", "高压油管", "动臂油管", "高压管"],
        "管路",
        "钢丝增强橡胶",
        1.15,
        [850, 26, 26],
        "工作装置",
        "动臂油缸总成",
        "hose",
        "通向动臂油缸的高压软管；压力等级及端接规格不在首版数据范围。",
    ),
    (
        "液压回油软管",
        ["回油管", "回油软管", "低压油管", "液压软管"],
        "管路",
        "耐油橡胶",
        0.68,
        [620, 32, 32],
        "液压系统",
        "液压油箱总成",
        "hose",
        "回油管路部件；不可根据相似外观替代高压软管。",
    ),
    (
        "机油压力传感器",
        ["压力传感器", "油压传感器", "机油感应器"],
        "传感器",
        "不锈钢",
        None,
        [50, 25, 25],
        "动力系统",
        "发动机润滑系统",
        "sensor",
        "机油压力监测元件；演示目录缺少重量。",
    ),
    (
        "冷却液温度传感器",
        ["水温传感器", "温度传感器", "水温感应器"],
        "传感器",
        "黄铜",
        0.045,
        [45, 18, 18],
        "动力系统",
        "冷却系统",
        "sensor",
        "冷却液温度检测元件；实际接头和电气参数需另行确认。",
    ),
    (
        "起动电机",
        ["启动马达", "起动机", "启动电机", "马达"],
        "电机",
        "铝合金",
        4.8,
        [230, 105, 120],
        "电气系统",
        "起动系统",
        "motor",
        "发动机起动用电机；同名规格跨设备不同。",
    ),
    (
        "雨刮电机",
        ["雨刷电机", "雨刮马达", "雨刷马达", "马达"],
        "电机",
        "铝合金",
        0.65,
        [110, 75, 65],
        "驾驶室",
        "前窗雨刮总成",
        "motor",
        "驾驶室前窗雨刮驱动电机，不是起动电机。",
    ),
    (
        "铲斗连接销轴",
        ["销轴", "斗销", "铲斗销", "连接销"],
        "连接件",
        "合金钢",
        2.8,
        [220, 45, 45],
        "工作装置",
        "铲斗连接机构",
        "bolt",
        "铲斗与连杆连接件；销径和长度必须匹配。",
    ),
    (
        "液压油箱呼吸器",
        ["呼吸器", "油箱通气滤", "通气滤芯", "空气滤清器"],
        "滤芯",
        "铝合金",
        None,
        [65, 65, 95],
        "液压系统",
        "液压油箱总成",
        "filter",
        "液压油箱通气过滤件；与发动机进气空气滤芯不同，重量未登记。",
    ),
]


def build_catalog() -> dict:
    """Return exactly the same catalogue each time, without I/O."""
    equipment = [
        {
            "code": "DEMO-EX-001",
            "model": "EX-DEMO-08",
            "name": "演示挖掘机 · 轻型",
            "description": "虚构的轻型挖掘机，用于配件检索教学；不对应任何企业设备或真实装配关系。",
        },
        {
            "code": "DEMO-EX-002",
            "model": "EX-DEMO-20",
            "name": "演示挖掘机 · 中型",
            "description": "虚构的中型挖掘机，与轻型设备存在同名异规格件以及少量共用紧固件。",
        },
        {
            "code": "DEMO-EX-003",
            "model": "EX-DEMO-35",
            "name": "演示挖掘机 · 重型",
            "description": "虚构的重型挖掘机，用于测试更换设备后旧检索结果失效。",
        },
    ]
    parts = []
    for device_index, machine in enumerate(equipment):
        for recipe_index, recipe in enumerate(RECIPES):
            (
                name,
                aliases,
                category,
                material,
                weight,
                dimensions,
                subsystem,
                assembly,
                kind,
                description,
            ) = recipe
            scale = [1.0, 1.35, 1.8][device_index]
            record = {
                "id": f"PP-{1001 + device_index * len(RECIPES) + recipe_index}",
                "name": name,
                "aliases": list(aliases),
                "category": category,
                "material": material,
                "weight_kg": None if weight is None else round(weight * scale, 3),
                "dimensions_mm": [
                    round(value * (1 + device_index * 0.15), 1) for value in dimensions
                ],
                "equipment_codes": [machine["code"]],
                "assembly_path": [machine["model"], subsystem]
                + ([assembly] if assembly else [])
                + [name],
                "description": description
                + " 本记录为自建合成数据，不可作为真实采购或维修依据。",
                "illustration": kind,
                "source": "synthetic",
            }
            # Name collisions and material differences are intentional evaluation cases.
            if device_index == 1 and recipe_index == 1:
                record["material"] = "玻璃纤维"
            if device_index == 2 and recipe_index == 0:
                record["material"] = "不锈钢"
            # Shared fasteners are explicit compatibility claims in this fictional dataset.
            if device_index == 0 and recipe_index in (11, 12, 13):
                record["equipment_codes"].append("DEMO-EX-002")
                record["description"] += " 演示设定：轻型和中型设备的检修盖板共用此件。"
            # A missing measurement is independent of the missing-weight cases above.
            if device_index == 2 and recipe_index == 6:
                record["dimensions_mm"] = None
                record["description"] += " 演示目录未登记外廓尺寸。"
            parts.append(record)
    return {
        "meta": {
            "synthetic": True,
            "description": "PartPilot 自建合成配件目录 v1：72 条虚构配件、3 台虚构设备；未使用企业数据。示意图均为通用图标，不是产品照片。",
            "version": "1.0.0",
        },
        "equipment": equipment,
        "parts": parts,
    }


def validate_catalog(catalog: dict) -> None:
    """Fail fast on unusable catalogue data using only the standard library."""
    assert catalog["meta"]["synthetic"] is True
    equipment_codes = {item["code"] for item in catalog["equipment"]}
    assert equipment_codes == {"DEMO-EX-001", "DEMO-EX-002", "DEMO-EX-003"}
    assert len(equipment_codes) == len(catalog["equipment"])
    required = {
        "id",
        "name",
        "aliases",
        "category",
        "material",
        "weight_kg",
        "dimensions_mm",
        "equipment_codes",
        "assembly_path",
        "description",
        "illustration",
        "source",
    }
    seen = set()
    for part in catalog["parts"]:
        assert set(part) == required, f"Unexpected schema for {part.get('id')}"
        assert part["id"] not in seen, f"Duplicate ID: {part['id']}"
        seen.add(part["id"])
        assert part["source"] == "synthetic"
        assert part["illustration"] in ILLUSTRATION_KINDS
        assert (
            part["equipment_codes"] and set(part["equipment_codes"]) <= equipment_codes
        )
        assert len(part["equipment_codes"]) == len(set(part["equipment_codes"]))
        for field in ("id", "name", "category", "material", "description"):
            assert isinstance(part[field], str) and part[field].strip()
        assert part["aliases"] and all(
            isinstance(item, str) and item.strip() for item in part["aliases"]
        )
        assert len(part["aliases"]) == len(set(part["aliases"]))
        assert len(part["assembly_path"]) >= 3
        assert part["assembly_path"][-1] == part["name"]
        weight = part["weight_kg"]
        assert weight is None or (type(weight) in (int, float) and weight > 0)
        dimensions = part["dimensions_mm"]
        assert dimensions is None or (
            len(dimensions) == 3
            and all(type(value) in (int, float) and value > 0 for value in dimensions)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate checked-in data and deterministic regeneration; do not write.",
    )
    args = parser.parse_args()
    catalog = build_catalog()
    validate_catalog(catalog)
    serialized = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        current_text = CATALOG_PATH.read_text(encoding="utf-8")
        validate_catalog(json.loads(current_text))
        if current_text != serialized:
            raise SystemExit(
                "catalog.json differs from deterministic generator; run scripts/generate_catalog.py"
            )
        print(
            "PASS: 72 synthetic parts, 3 equipment records; schema and deterministic regeneration verified."
        )
    else:
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_PATH.write_text(serialized, encoding="utf-8")
        print("Generated data/catalog.json: 72 synthetic parts, 3 equipment records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
