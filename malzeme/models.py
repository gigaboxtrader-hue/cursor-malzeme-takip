from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any

from . import SUTUNLAR, MALZEME_ALANLARI


@dataclass
class Material:
    ag_code: str = ""
    ag_desc: str = ""
    ag_qty: str = ""
    yg_code: str = ""
    yg_desc: str = ""
    yg_qty: str = ""

    @staticmethod
    def from_list(values: List[str]) -> "Material":
        padded = (values + [""] * 6)[:6]
        return Material(
            ag_code=padded[0],
            ag_desc=padded[1],
            ag_qty=padded[2],
            yg_code=padded[3],
            yg_desc=padded[4],
            yg_qty=padded[5],
        )

    def to_list(self) -> List[str]:
        return [
            self.ag_code,
            self.ag_desc,
            self.ag_qty,
            self.yg_code,
            self.yg_desc,
            self.yg_qty,
        ]

    def to_dict(self) -> Dict[str, str]:
        return {
            "AG Kod": self.ag_code,
            "AG Tanım": self.ag_desc,
            "AG Miktar": self.ag_qty,
            "YG Kod": self.yg_code,
            "YG Tanım": self.yg_desc,
            "YG Miktar": self.yg_qty,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Material":
        return Material(
            ag_code=str(d.get("AG Kod", "")),
            ag_desc=str(d.get("AG Tanım", "")),
            ag_qty=str(d.get("AG Miktar", "")),
            yg_code=str(d.get("YG Kod", "")),
            yg_desc=str(d.get("YG Tanım", "")),
            yg_qty=str(d.get("YG Miktar", "")),
        )


@dataclass
class Project:
    fields: Dict[str, str] = field(default_factory=dict)
    materials: List[Material] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        return self.fields.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.fields[key] = value

    def to_rows_for_report(self) -> List[Dict[str, str]]:
        if not self.materials:
            row = {col: self.get(col, "") for col in SUTUNLAR}
            row.update({k: "" for k in MALZEME_ALANLARI})
            return [row]
        rows = []
        for m in self.materials:
            row = {col: self.get(col, "") for col in SUTUNLAR}
            row.update(m.to_dict())
            rows.append(row)
        return rows

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fields": {k: str(v) for k, v in self.fields.items()},
            "materials": [m.to_dict() for m in self.materials],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Project":
        fields = {k: str(v) for k, v in (data.get("fields") or {}).items()}
        materials = [Material.from_dict(m) for m in (data.get("materials") or [])]
        return Project(fields=fields, materials=materials)

    @staticmethod
    def from_tree_values(values: List[str], children_material_values: List[List[str]]) -> "Project":
        fields = {SUTUNLAR[i]: str(values[i]) for i in range(len(SUTUNLAR))}
        materials = [Material.from_list(m) for m in children_material_values]
        return Project(fields=fields, materials=materials)

