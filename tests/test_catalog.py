"""Dataset acceptance checks: protect meaningful demonstration edge cases."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_catalog", ROOT / "scripts" / "generate_catalog.py"
)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)
CATALOG = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
PARTS = {part["id"]: part for part in CATALOG["parts"]}


def test_catalogue_schema_and_regeneration():
    GENERATOR.validate_catalog(CATALOG)
    assert CATALOG == GENERATOR.build_catalog()
    assert len(PARTS) == 72


def test_stable_filter_and_assembly_examples_are_distinguishable():
    assert PARTS["PP-1001"]["name"] == PARTS["PP-1002"]["name"] == "液压回油滤芯"
    assert [PARTS[code]["weight_kg"] for code in ("PP-1001", "PP-1002", "PP-1003")] == [
        1.2,
        2.4,
        5.6,
    ]
    assert PARTS["PP-1001"]["material"] != PARTS["PP-1002"]["material"]
    assert PARTS["PP-1003"]["name"] == "液压滤清器总成"
    assert PARTS["PP-1001"]["assembly_path"][:-1] == PARTS["PP-1003"]["assembly_path"]
    assert PARTS["PP-1002"]["assembly_path"][:-1] == PARTS["PP-1003"]["assembly_path"]
    assert all(
        PARTS[code]["equipment_codes"] == ["DEMO-EX-001"]
        for code in ("PP-1001", "PP-1002", "PP-1003")
    )


def test_each_equipment_has_usable_aliases_and_required_component_families():
    for equipment in CATALOG["equipment"]:
        items = [
            part
            for part in PARTS.values()
            if equipment["code"] in part["equipment_codes"]
        ]
        assert len(items) >= 24
        aliases = {alias for part in items for alias in part["aliases"]}
        assert {
            "回油滤芯",
            "空气滤芯",
            "液压泵",
            "电磁阀",
            "密封圈",
            "紧固件",
        } <= aliases
        assert any(part["weight_kg"] is None for part in items)
        assert any(
            part["weight_kg"] is not None and part["weight_kg"] < 1 for part in items
        )
        assert any(
            part["weight_kg"] is not None and part["weight_kg"] > 10 for part in items
        )


def test_same_name_across_equipment_is_not_equivalent_to_same_part():
    filters = [part for part in PARTS.values() if part["name"] == "液压回油滤芯"]
    assert len(filters) == 6
    assert len({tuple(part["equipment_codes"]) for part in filters}) == 3
    assert len({part["weight_kg"] for part in filters}) > 3
    assert any(len(part["equipment_codes"]) > 1 for part in PARTS.values())


def test_unknown_measurements_are_explicit_not_zero_or_dummy_values():
    assert sum(part["weight_kg"] is None for part in PARTS.values()) == 9
    assert any(part["dimensions_mm"] is None for part in PARTS.values())
    assert not any(part["weight_kg"] == 0 for part in PARTS.values())
    assert all(part["source"] == "synthetic" for part in PARTS.values())
    # No product photo URL is present: illustrations are explicitly generic symbols.
    assert all(
        "http://" not in str(part) and "https://" not in str(part)
        for part in PARTS.values()
    )


def test_all_generic_illustrations_are_available_and_identified():
    for kind in GENERATOR.ILLUSTRATION_KINDS:
        svg = (ROOT / "static" / "illustrations" / f"{kind}.svg").read_text(
            encoding="utf-8"
        )
        assert "<svg" in svg and "<title" in svg
        assert "合成" in svg and "非产品照片" in svg
        assert "<script" not in svg and "http://" not in svg.replace(
            "http://www.w3.org/2000/svg", ""
        )
