from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from . import SUTUNLAR
from .models import Project, Material
from .storage import DataStorage
from .utils import parse_date_yyyy_mm_dd


@dataclass
class FilterCriteria:
    musteri: str = ""
    proje_no: str = ""
    fat_bas: str = ""
    fat_bit: str = ""
    ara: str = ""


class AppController:
    def __init__(self, storage: DataStorage) -> None:
        self.storage = storage

    # CRUD operations
    def create_project(self, fields: dict, materials_rows: List[List[str]]) -> Project:
        project = Project(fields={k: str(v) for k, v in fields.items()}, materials=[Material.from_list(r) for r in materials_rows])
        self.storage.projects.append(project)
        logging.info("Project created: %s", project.get("PROJE NO", ""))
        return project

    def update_project(self, index: int, fields: dict, materials_rows: List[List[str]]) -> Project:
        project = self.storage.projects[index]
        project.fields = {k: str(v) for k, v in fields.items()}
        project.materials = [Material.from_list(r) for r in materials_rows]
        logging.info("Project updated: idx=%d, proje_no=%s", index, project.get("PROJE NO", ""))
        return project

    def delete_project(self, index: int) -> None:
        proj_no = self.storage.projects[index].get("PROJE NO", "") if 0 <= index < len(self.storage.projects) else ""
        del self.storage.projects[index]
        logging.info("Project deleted: idx=%d, proje_no=%s", index, proj_no)

    def update_material(self, project_index: int, material_index: int, values: List[str]) -> None:
        self.storage.projects[project_index].materials[material_index] = Material.from_list(values)
        logging.info("Material updated: pidx=%d midx=%d", project_index, material_index)

    def delete_material(self, project_index: int, material_index: int) -> None:
        del self.storage.projects[project_index].materials[material_index]
        logging.info("Material deleted: pidx=%d midx=%d", project_index, material_index)

    # Filtering
    def filter_projects(self, criteria: FilterCriteria) -> List[Project]:
        musteri = (criteria.musteri or "").strip().lower()
        proje_no = (criteria.proje_no or "").strip().lower()
        ara = (criteria.ara or "").strip().lower()
        fat_bas = parse_date_yyyy_mm_dd(criteria.fat_bas)
        fat_bit = parse_date_yyyy_mm_dd(criteria.fat_bit)

        result: List[Project] = []
        for project in self.storage.projects:
            # Customer filter
            if musteri and musteri not in str(project.get("MÜŞTERİ", "")).lower():
                continue
            # Project number filter
            if proje_no and proje_no not in str(project.get("PROJE NO", "")).lower():
                continue

            # FAT date range
            fat_str = str(project.get("FAT", ""))
            try:
                import datetime as _dt

                fat_date = _dt.datetime.strptime(fat_str, "%Y-%m-%d").date()
                if fat_bas and fat_date < fat_bas:
                    continue
                if fat_bit and fat_date > fat_bit:
                    continue
            except Exception:
                # ignore invalid dates
                pass

            if ara:
                matched = any(ara in str(project.get(col, "")).lower() for col in SUTUNLAR)
                if not matched:
                    for m in project.materials:
                        if any(ara in str(x).lower() for x in m.to_list()):
                            matched = True
                            break
                if not matched:
                    continue

            result.append(project)
        return result

