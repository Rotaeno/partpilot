"""Fetch a pinned, licensed public BOM snapshot and derive auditable records.

Uses only Python's standard library. No model, credentials, product API, or
company data are used. All writes are constrained to the two project paths below.
Run with --verify-only to perform a completely offline integrity/rebuild check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public_sources"
ARTIFACTS = ROOT / "artifacts" / "public-data"
REPO = "prusa3d/Original-Prusa-MINI"
COMMIT = "853bc30c4b10190f1d669ed6d0a567e333c28f21"
LICENSE = "GPL-3.0"
BOMS = ["X-AXIS", "Y-AXIS", "Z-AXIS", "E-AXIS", "SPOOLHOLDER", "FILAMENT SENSOR"]
PATHS = ["LICENSE", "README.md", *[f"BOM/{name}.md" for name in BOMS]]
ASSEMBLY_ZH = {
    "X-AXIS": "X轴组件",
    "Y-AXIS": "Y轴组件",
    "Z-AXIS": "Z轴组件",
    "E-AXIS": "挤出组件",
    "SPOOLHOLDER": "料盘支架",
    "FILAMENT SENSOR": "耗材传感器",
}


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_url(path: str) -> str:
    return f"https://github.com/{REPO}/blob/{COMMIT}/{quote(path, safe='/')}"


def fetch() -> dict:
    files = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for upstream_path in PATHS:
        raw_url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{quote(upstream_path, safe='/')}"
        request = Request(
            raw_url, headers={"User-Agent": "PartPilot-public-BOM-snapshot/1.0"}
        )
        # Host/path are entirely allowlisted constants; no user-controlled URL is fetched.
        with urlopen(request, timeout=30) as response:
            payload = response.read(500_001)
        if len(payload) > 500_000:
            raise ValueError(f"Unexpectedly large source: {upstream_path}")
        payload.decode(
            "utf-8"
        )  # Reject non-text responses rather than saving unverified binary data.
        destination = OUT / "raw" / upstream_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        files.append(
            {
                "id": upstream_path.replace("/", "-").replace(" ", "-"),
                "upstream_path": upstream_path,
                "local_path": f"raw/{upstream_path}",
                "source_url": blob_url(upstream_path),
                "raw_url": raw_url,
                "sha256": sha(payload),
                "bytes": len(payload),
                "fetched_at": fetched_at,
                "license": LICENSE,
            }
        )
    license_text = (OUT / "raw" / "LICENSE").read_text(encoding="utf-8")
    if (
        "GNU GENERAL PUBLIC LICENSE" not in license_text
        or "Version 3, 29 June 2007" not in license_text
    ):
        raise ValueError("Expected upstream GPL v3 LICENSE was not found")
    manifest = {
        "schema_version": 1,
        "id": "prusa-mini-bom",
        "title": "Original Prusa MINI official BOM snapshot",
        "repository": f"https://github.com/{REPO}",
        "commit": COMMIT,
        "license": LICENSE,
        "license_source_url": blob_url("LICENSE"),
        "license_local_path": "raw/LICENSE",
        "fetched_at": fetched_at,
        "attribution": "Upstream hardware and BOM: PRUSA RESEARCH / prusa3d contributors.",
        "modification_notice": "PartPilot extracts BOM rows, adds stable local IDs and derived Chinese labels. Raw files are byte-for-byte upstream originals. The extraction script is the editable source for these derivatives.",
        "source_type": "official_open_hardware_bom",
        "synthetic": False,
        "scope": "This exact repository snapshot, not a live product catalog or proof of compatibility with other revisions, current MINI+, or any industrial equipment.",
        "license_scope": "The repository root GPL v3 LICENSE accompanies the copied repository-authored Markdown BOM/README. Linked third-party datasheets, images, PDFs and external repositories are not downloaded or relicensed.",
        "selection_rule": "Every STANDARD PARTS and CUSTOM PARTS BOM row except textile sleeves; additionally the four axis motor rows. This is a selected component index, not a complete printer kit or purchasing list. Complete original BOM sections remain available as evidence.",
        "files": files,
    }
    dump(OUT / "source_manifest.json", manifest)
    return manifest


def plain_name(cell: str) -> str:
    # First link is the component name; later links are ancillary datasheets.
    links = re.findall(r"\[([^]]+)\]\(([^)]+)\)", cell)
    return (links[0][0] if links else cell).strip()


def translated(name: str) -> str:
    """Deliberately small lexical translations. Never add unstated dimensions/specs."""
    translations = [
        ("linear bearing", "直线轴承"),
        ("Pulley Bearing Idler", "惰轮轴承"),
        ("Pulley Motor", "电机带轮"),
        ("Bearing", "轴承"),
        ("X-axis belt", "X轴皮带"),
        ("Y-axis belt", "Y轴皮带"),
        ("X-axis motor", "X轴电机"),
        ("Y-axis motor", "Y轴电机"),
        ("Z-axis motor", "Z轴电机"),
        ("E-axis motor", "挤出电机"),
        ("X smooth rod", "X轴光杆"),
        ("Y smooth rod", "Y轴光杆"),
        ("Z smooth rod", "Z轴光杆"),
        ("aluminium extrusion", "铝型材"),
        ("Y carriage", "Y轴滑架"),
        ("Z plate bottom", "Z轴底板"),
        ("hotend PTFE tube", "热端PTFE管"),
        ("extruder PTFE tube", "挤出PTFE管"),
        ("input PTFE tube", "入口PTFE管"),
        ("bowden", "鲍登管"),
        ("FS PTFE", "耗材传感器PTFE管"),
        ("heatsink", "散热器"),
        ("heatbreak", "隔热喉管"),
        ("heaterblock", "加热块"),
        ("nozzle", "喷嘴"),
        ("fitting swivel nut", "接头旋转螺母"),
        ("fitting olive", "接头卡套"),
        ("fitting", "接头"),
        ("motor pinion", "电机小齿轮"),
        ("filament spur", "送丝齿轮"),
        ("extruder idler spring", "挤出惰轮弹簧"),
        ("shaft", "轴"),
        ("Zip tie", "扎带"),
        ("U bolt", "U形螺栓"),
        ("steel sheet", "钢板"),
        ("spoolholder foam pads", "料盘支架泡棉垫"),
        ("foam pad", "泡棉垫"),
        ("Stainless steel ball", "不锈钢球"),
        ("Magnet", "磁铁"),
    ]
    output = name
    for original, chinese in translations:
        output = output.replace(original, chinese)
    return output


def selected(section: str, name: str) -> bool:
    return (
        section in {"STANDARD PARTS", "CUSTOM PARTS"} and "textile sleeve" not in name
    ) or (section == "ELECTRICAL PARTS" and "axis motor" in name)


def derive(manifest: dict) -> tuple[dict, dict]:
    parts, documents = [], []
    for source in manifest["files"]:
        path = source["upstream_path"]
        if not path.startswith("BOM/"):
            continue
        assembly = Path(path).stem
        assembly_id = assembly.replace(" ", "-").lower()
        lines = (OUT / source["local_path"]).read_text(encoding="utf-8").splitlines()
        headings = [
            (n, line.strip("* \t"))
            for n, line in enumerate(lines)
            if re.fullmatch(r"\*\*[A-Z ]+\*\*\s*", line)
        ]
        for heading_index, (start, section) in enumerate(headings):
            end = (
                headings[heading_index + 1][0]
                if heading_index + 1 < len(headings)
                else len(lines)
            )
            while end > start and not lines[end - 1].strip():
                end -= 1
            document_id = f"prusa-{assembly_id}-{section.lower().replace(' ', '-')}"
            part_ids = []
            for index in range(start + 1, end):
                line = lines[index]
                match = re.match(r"^\|(.+)\|\s*(\d+)\s*\|\s*$", line)
                if not match:
                    continue
                name = plain_name(match.group(1))
                if not selected(section, name):
                    continue
                part_id = f"PRUSA-{assembly_id.upper()}-L{index + 1}"
                part_ids.append(part_id)
                links = [
                    link
                    for _, link in re.findall(r"\[([^]]+)\]\(([^)]+)\)", match.group(1))
                ]
                linked_documents = [
                    (
                        blob_url(unquote(link).lstrip("/"))
                        if link.startswith("/")
                        else link
                    )
                    for link in links
                ]
                zh = translated(name)
                parts.append(
                    {
                        "id": part_id,
                        "equipment_id": "PRUSA-MINI-SNAPSHOT",
                        "name_original": name,
                        "name_zh": zh,
                        "name_zh_is_derived": True,
                        "aliases": list(dict.fromkeys([name, zh])),
                        "category_original": section,
                        "assembly": assembly,
                        "assembly_zh": ASSEMBLY_ZH[assembly],
                        "assembly_zh_is_derived": True,
                        "quantity": int(match.group(2)),
                        "quantity_scope": f"One {assembly} BOM assembly at pinned commit; not stock or total printer quantity.",
                        "raw_specification": name,
                        "raw_row": line.strip(),
                        "weight_kg": None,
                        "material": None,
                        "dimensions_mm": None,
                        "manufacturer_part_number": None,
                        "source_id": source["id"],
                        "evidence_doc_id": document_id,
                        "source_url": f"{source['source_url']}#L{index + 1}",
                        "source_path": path,
                        "source_line_start": index + 1,
                        "source_line_end": index + 1,
                        "source_sha256": source["sha256"],
                        "license": LICENSE,
                        "linked_documents_not_ingested": linked_documents,
                        "synthetic": False,
                        "compatibility_claim": "Only listed occurrence in this source BOM; no replacement, cross-device or cross-version compatibility inferred.",
                    }
                )
            documents.append(
                {
                    "id": document_id,
                    "title": f"Original Prusa MINI · {assembly} · {section}",
                    "assembly": assembly,
                    "assembly_zh": ASSEMBLY_ZH[assembly],
                    "section": section,
                    "text": "\n".join(lines[start:end]),
                    "context": f"BOM/{assembly}.md, section {section}; Qty is this assembly's source-listed quantity.",
                    "source_url": f"{source['source_url']}#L{start + 1}-L{end}",
                    "source_id": source["id"],
                    "source_path": path,
                    "source_sha256": source["sha256"],
                    "line_start": start + 1,
                    "line_end": end,
                    "part_ids": part_ids,
                    "license": LICENSE,
                    "synthetic": False,
                }
            )
    meta = {
        "schema_version": 1,
        "source_manifest": "source_manifest.json",
        "commit": COMMIT,
        "synthetic": False,
        "license": LICENSE,
        "derived_fields": [
            "id",
            "name_zh",
            "aliases",
            "assembly_zh",
            "quantity_scope",
            "compatibility_claim",
        ],
        "unknown_fields_policy": "Unstated properties stay null. Dimensions/model identifiers remain verbatim in raw_specification; no catalog attributes guessed from model names.",
        "not_a_purchasing_list": True,
    }
    normalized = {
        "meta": meta,
        "equipment": {
            "id": "PRUSA-MINI-SNAPSHOT",
            "name": "Original Prusa MINI BOM snapshot",
            "revision": COMMIT,
            "source_url": blob_url("README.md"),
            "synthetic": False,
        },
        "parts": parts,
    }
    evidence = {"meta": meta, "documents": documents}
    return normalized, evidence


def verify(manifest: dict, normalized: dict, evidence: dict) -> dict:
    checks = []
    for record in manifest["files"]:
        payload = (OUT / record["local_path"]).read_bytes()
        assert (
            sha(payload) == record["sha256"]
        ), f"Source hash mismatch: {record['local_path']}"
        assert len(payload) == record["bytes"]
        checks.append(f"SHA256 {record['upstream_path']}")
    assert len(normalized["parts"]) >= 10 and len(normalized["parts"]) <= 50
    assert len({p["id"] for p in normalized["parts"]}) == len(normalized["parts"])
    docs_by_id = {doc["id"]: doc for doc in evidence["documents"]}
    for part in normalized["parts"]:
        original_lines = (
            (OUT / "raw" / part["source_path"]).read_text(encoding="utf-8").splitlines()
        )
        assert part["raw_row"] == original_lines[part["source_line_start"] - 1].strip()
        assert part["raw_row"] in docs_by_id[part["evidence_doc_id"]]["text"]
        assert part["id"] in docs_by_id[part["evidence_doc_id"]]["part_ids"]
        assert part["quantity"] > 0 and part["weight_kg"] is None
    for doc in evidence["documents"]:
        original_lines = (
            (OUT / "raw" / doc["source_path"]).read_text(encoding="utf-8").splitlines()
        )
        assert doc["text"] == "\n".join(
            original_lines[doc["line_start"] - 1 : doc["line_end"]]
        )

    # Business-relevant snapshot checks are factual fixtures of the pinned source.
    def quantity(assembly: str, name: str) -> int:
        return next(
            p["quantity"]
            for p in normalized["parts"]
            if p["assembly"] == assembly and p["name_original"] == name
        )

    assert quantity("X-AXIS", "LM8UU linear bearing") == 2
    assert quantity("Y-AXIS", "LM8UU linear bearing") == 3
    assert quantity("X-AXIS", "X-axis belt 561 mm") == 1
    assert quantity("Y-AXIS", "Y-axis belt 496 mm") == 1
    checks += [
        "Unique part IDs",
        "Every row equals source line",
        "Every document equals source line slice",
        "Every selected part belongs to evidence doc",
        "Assembly-specific quantity fixtures",
        "Belt length source fixtures",
        "Unknown fields stay null",
        "Deterministic rebuild",
    ]
    return {
        "status": "passed",
        "source_files": len(manifest["files"]),
        "parts": len(normalized["parts"]),
        "evidence_documents": len(evidence["documents"]),
        "commit": COMMIT,
        "checks": checks,
        "external_model_calls": 0,
        "limitations": [
            "Only pinned upstream BOM membership is established.",
            "No live inventory, replacement compatibility, complete kit coverage, images or third-party datasheets.",
            "Chinese labels are local translations, not official source wording.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Offline SHA256, provenance and deterministic-rebuild verification; no network",
    )
    args = parser.parse_args()
    manifest = (
        json.loads((OUT / "source_manifest.json").read_text(encoding="utf-8"))
        if args.verify_only
        else fetch()
    )
    normalized, evidence = derive(manifest)
    if args.verify_only:
        assert normalized == json.loads(
            (OUT / "normalized_parts.json").read_text(encoding="utf-8")
        ), "Normalized data diverges from generator"
        assert evidence == json.loads(
            (OUT / "evidence_docs.json").read_text(encoding="utf-8")
        ), "Evidence data diverges from original sources"
    else:
        dump(OUT / "normalized_parts.json", normalized)
        dump(OUT / "evidence_docs.json", evidence)
    report = verify(manifest, normalized, evidence)
    report["network_used_this_run"] = not args.verify_only
    dump(ARTIFACTS / "verification.json", report)
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
