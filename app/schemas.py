from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

SlotName = Literal[
    "equipment_code",
    "name",
    "part_code",
    "material",
    "max_weight_kg",
    "min_weight_kg",
    "location",
]
SLOT_LABELS = {
    "equipment_code": "设备编码",
    "name": "配件名称",
    "part_code": "配件编码",
    "material": "材质",
    "max_weight_kg": "重量上限 (kg)",
    "min_weight_kg": "重量下限 (kg)",
    "location": "安装位置",
}


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | float
    evidence: str = Field(min_length=1, max_length=500)
    inferred: bool = False
    inclusive: bool = True


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict[SlotName, Change] = Field(default_factory=dict)
    clear: list[SlotName] = Field(default_factory=list)
    action: Literal["update", "search", "fallback", "ask"] = "update"
    conflicts: list[str] = Field(default_factory=list, max_length=5)
    conflict_fields: list[SlotName] = Field(default_factory=list)
    question: str | None = Field(default=None, max_length=300)


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["message", "search", "fallback", "clear_slot"] = "message"
    text: str = Field(default="", max_length=2000)
    slot: SlotName | None = None
    expected_revision: int = Field(ge=0)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part_id: str = Field(min_length=1, max_length=60)
    query_id: str = Field(min_length=1, max_length=60)
    expected_revision: int = Field(ge=0)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)

    @field_validator("title")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("标题不能为空")
        return value.strip()
