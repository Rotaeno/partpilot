"""Tools over a versioned, licensed public BOM. No invented device fitment."""

import json
import re
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .config import ROOT


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="", max_length=180)


class Search(Arguments):
    query: str = Field(min_length=1, max_length=200)


class ReadPart(Arguments):
    part_id: str = Field(min_length=1, max_length=100)


class ReadDocument(Arguments):
    document_id: str = Field(min_length=1, max_length=100)


class Compare(Arguments):
    part_ids: list[str] = Field(min_length=2, max_length=4)


class Ask(Arguments):
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=4, max_length=700)


class Finish(Arguments):
    summary: str = Field(min_length=1, max_length=600)
    claims: list[Citation] = Field(default_factory=list, max_length=6)
    part_ids: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=5)
    outcome: Literal["completed", "insufficient"] = "completed"


TOOL_MODELS = {
    "search_catalog": Search,
    "search_documents": Search,
    "read_part": ReadPart,
    "read_document": ReadDocument,
    "compare_parts": Compare,
    "ask_user": Ask,
    "finish_report": Finish,
}
DESCRIPTIONS = {
    "search_catalog": "检索公开Prusa MINI BOM零件。支持原文型号、英文术语、中文基础别名。返回候选ID/数量/装配位置。搜索不等于阅读证据；回答前read_part。",
    "search_documents": "按术语检索公开原文段落。返回文档ID与摘要；需要read_document才能引用全文证据。",
    "read_part": "读取已检索到的零件记录和原始BOM证据，保留型号、数量、出处。数量是该装配段落数量，非整机汇总。",
    "read_document": "读取已检索到的原文段落，作为带来源的证据。",
    "compare_parts": "比较2-4个已检索零件的型号、数量、所属装配；自动读取各自证据，不推断替换兼容性。",
    "ask_user": "范围不明确且会影响答案时，提出一个具体问题并等待用户；不得在问题中声称已保存。",
    "finish_report": "结束本轮查证。只引用本轮read/compare已观察到的evidence_id和其中连续原文quote。summary用中文回答；不存在或不能确认时outcome=insufficient。不会下单或保存报告。",
}
FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": DESCRIPTIONS[name],
            "parameters": model.model_json_schema(),
        },
    }
    for name, model in TOOL_MODELS.items()
]


def normalize(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def tokens(text):
    text = normalize(text)
    # This small transparent vocabulary is shared by Agent tools and baseline.
    mapping = {
        "轴承": "bearing",
        "皮带": "belt",
        "电机": "motor",
        "螺丝": "screw",
        "螺栓": "screw",
        "螺母": "nut",
        "垫圈": "washer",
        "挤出": "extruder",
        "喷嘴": "nozzle",
        "热端": "hotend",
        "线性": "linear",
        "滑轮": "pulley",
        "导杆": "rod",
        "x轴": "x axis",
        "y轴": "y axis",
        "z轴": "z axis",
    }
    for cn, en in mapping.items():
        if cn in text:
            text += " " + en
    terms = re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text)
    terms += [x for x in re.findall(r"[\u4e00-\u9fff]+", text) if len(x) < 7]
    stop = {
        "the",
        "a",
        "of",
        "for",
        "and",
        "original",
        "prusa",
        "mini",
        "有哪些",
        "多少",
        "什么",
        "这个设备",
        "请查找",
    }
    return list(dict.fromkeys(x for x in terms if x not in stop))


def term_matches(term, text):
    if term.isascii():
        return bool(
            re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text)
        )
    return term in text


class PublicCorpus:
    def __init__(self, directory=None):
        self.directory = Path(directory or ROOT / "data/public_sources")

        def read(filename, default):
            p = self.directory / filename
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

        self.part_data = read("normalized_parts.json", {"parts": []})
        self.parts = {p["id"]: p for p in self.part_data.get("parts", [])}
        self.doc_data = read("evidence_docs.json", {"documents": []})
        self.docs = {d["id"]: d for d in self.doc_data.get("documents", [])}
        self.manifest = read("source_manifest.json", {})

    @property
    def sources(self):
        if not self.parts:
            return []
        return [
            {
                "id": "prusa-mini",
                "title": "Original Prusa MINI · 官方开源 BOM",
                "url": "https://github.com/prusa3d/Original-Prusa-MINI/tree/853bc30c4b10190f1d669ed6d0a567e333c28f21",
                "license": "GPL-3.0（原始资料）；中文名称为派生翻译",
            }
        ]

    @staticmethod
    def part_summary(p):
        return {
            k: p.get(k)
            for k in (
                "id",
                "name_original",
                "name_zh",
                "assembly",
                "quantity",
                "raw_specification",
                "source_url",
            )
        }

    def search_catalog(self, query):
        ts = tokens(query)
        ranked = []
        for p in self.parts.values():
            text = normalize(
                " ".join(
                    str(p.get(k, ""))
                    for k in (
                        "name_original",
                        "name_zh",
                        "aliases",
                        "assembly",
                        "raw_specification",
                        "category_original",
                    )
                )
            )
            score = sum(1 for t in ts if term_matches(t, text))
            if score:
                ranked.append((score, p))
        ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
        return {
            "query": query,
            "total": len(ranked),
            "items": [self.part_summary(p) for _, p in ranked[:12]],
            "truncated": len(ranked) > 12,
        }

    def search_documents(self, query):
        ts = tokens(query)
        ranked = []
        for d in self.docs.values():
            text = normalize(d.get("title", "") + " " + d["text"])
            score = sum(1 for t in ts if term_matches(t, text))
            if score:
                ranked.append((score, d))
        ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
        return {
            "query": query,
            "items": [
                {
                    "id": d["id"],
                    "title": d["title"],
                    "preview": d["text"][:240],
                    "source_url": d["source_url"],
                }
                for _, d in ranked[:6]
            ],
            "total": len(ranked),
        }

    def read_part(self, part_id):
        p = self.parts[part_id]
        original = p.get("raw_specification") or p["name_original"]
        # Prefer the complete original BOM block rather than a regenerated fact sentence.
        linked = [d for d in self.docs.values() if part_id in d.get("part_ids", [])]
        if linked:
            d = linked[0]
            evidence = {
                "id": f"part:{part_id}",
                "title": p["name_original"] + " · " + str(p["assembly"]),
                "text": d["text"][:6000],
                "source_url": d["source_url"],
                "kind": "public_bom",
                "part_ids": [part_id],
            }
        else:
            evidence = {
                "id": f"part:{part_id}",
                "title": p["name_original"],
                "text": str(original),
                "source_url": p["source_url"],
                "kind": "public_bom",
                "part_ids": [part_id],
            }
        return {
            "part": self.part_summary(p),
            "evidence": evidence,
            "citation": {
                "evidence_id": evidence["id"],
                "quote": p.get("raw_row", str(original)),
            },
            "scope": "数量属于该装配BOM段落；未知重量/材料未填充，不能推定兼容替代。",
        }

    def read_document(self, document_id):
        d = self.docs[document_id]
        return {
            "evidence": {
                "id": f"doc:{document_id}",
                "title": d["title"],
                "text": d["text"][:6000],
                "source_url": d["source_url"],
                "kind": "public_document",
                "part_ids": d.get("part_ids", []),
            }
        }

    def compare_parts(self, part_ids):
        readings = [self.read_part(pid) for pid in part_ids]
        return {
            "items": [r["part"] for r in readings],
            "evidence": [r["evidence"] for r in readings],
            "citations": [r["citation"] for r in readings],
            "compatibility": "not_established",
            "note": "BOM差异是可查事实；互换适配需要额外厂家/尺寸/载荷证据。",
        }
