from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

try:
    import openpyxl  # noqa: F401  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    openpyxl = None  # type: ignore

from . import SUTUNLAR, MALZEME_ALANLARI
from .models import Project, Material


class SettingsStorage:
    """Persist simple app settings like theme or column widths."""

    def __init__(self, path: str = "settings.json") -> None:
        self.path = path
        self._data = {
            "theme": "light",
            "column_widths": {},
        }
        self.load()

    @property
    def theme(self) -> str:
        return str(self._data.get("theme", "light"))

    @theme.setter
    def theme(self, value: str) -> None:
        self._data["theme"] = value

    def get_column_width(self, column: str, default: int) -> int:
        try:
            return int(self._data.get("column_widths", {}).get(column, default))
        except Exception:
            return default

    def set_column_width(self, column: str, width: int) -> None:
        self._data.setdefault("column_widths", {})[column] = int(width)

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logging.warning("Settings save failed: %s", exc)

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception as exc:
            logging.warning("Settings load failed: %s", exc)


class DataStorage:
    """In-memory project list with JSON persistence and Excel import/export."""

    def __init__(self, data_path: str = "data.json") -> None:
        self.data_path = data_path
        self.projects: List[Project] = []

    # -------------------
    # JSON persistence
    # -------------------
    def save_json(self) -> None:
        tmp_path = self.data_path + ".tmp"
        data = [p.to_dict() for p in self.projects]
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.data_path)
            logging.info("Saved %d projects to %s", len(self.projects), self.data_path)
        except Exception as exc:
            logging.exception("Failed to save data: %s", exc)

    def load_json(self) -> None:
        if not os.path.exists(self.data_path):
            self.projects = []
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.projects = [Project.from_dict(p) for p in raw]
            logging.info("Loaded %d projects from %s", len(self.projects), self.data_path)
        except Exception as exc:
            logging.exception("Failed to load data: %s", exc)
            self.projects = []

    # -------------------
    # Excel/CSV export
    # -------------------
    def _to_dataframe(self):  # type: ignore[override]
        if pd is None:
            raise RuntimeError("Pandas is not installed. Install 'pandas' for Excel export.")
        rows = []
        for proj in self.projects:
            rows.extend(proj.to_rows_for_report())
        return pd.DataFrame(rows)

    def export_report(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            # Write CSV without pandas
            import csv

            rows: List[dict] = []
            for proj in self.projects:
                rows.extend(proj.to_rows_for_report())
            fieldnames = list(SUTUNLAR) + list(MALZEME_ALANLARI)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            logging.info("Report saved to CSV: %s", path)
            return

        # Excel preferred path
        if pd is None:
            raise RuntimeError("Pandas is required to export Excel (.xlsx). Install 'pandas openpyxl'.")
        df = self._to_dataframe()
        df.to_excel(path, index=False)
        logging.info("Report saved to Excel: %s", path)

    # -------------------
    # Excel import
    # -------------------
    def import_from_excel(self, path: str) -> None:
        if pd is None:
            raise RuntimeError("Pandas is required to import Excel (.xlsx). Install 'pandas openpyxl'.")
        df = pd.read_excel(path)
        if "PROJE NO" not in df.columns:
            raise ValueError("Excel format is invalid. 'PROJE NO' column is missing.")

        self.projects.clear()
        grouped = df.groupby("PROJE NO", dropna=False)
        for _, grp in grouped:
            fields = {}
            for col in SUTUNLAR:
                fields[col] = str(grp.iloc[0][col]) if col in grp.columns else ""
            materials: List[Material] = []
            for _, row in grp.iterrows():
                materials.append(
                    Material(
                        ag_code=str(row.get("AG Kod", "")),
                        ag_desc=str(row.get("AG Tanım", "")),
                        ag_qty=str(row.get("AG Miktar", "")),
                        yg_code=str(row.get("YG Kod", "")),
                        yg_desc=str(row.get("YG Tanım", "")),
                        yg_qty=str(row.get("YG Miktar", "")),
                    )
                )
            self.projects.append(Project(fields=fields, materials=materials))
        logging.info("Imported %d projects from %s", len(self.projects), path)

