from __future__ import annotations

import io
import os
import tempfile
from typing import List, Tuple

import gradio as gr
import pandas as pd

from . import APP_TITLE, SUTUNLAR, MALZEME_ALANLARI
from .controller import AppController, FilterCriteria
from .models import Project, Material
from .storage import DataStorage


class MalzemeWebApp:
    def __init__(self) -> None:
        self.data = DataStorage()
        self.data.load_json()
        self.controller = AppController(self.data)
        # filtered holds indices into storage.projects
        self.filtered_indices: List[int] = list(range(len(self.data.projects)))

    # -----------------------------
    # Helpers to convert data
    # -----------------------------
    def _projects_to_df(self, indices: List[int]) -> pd.DataFrame:
        rows = []
        for i, storage_idx in enumerate(indices):
            proj = self.data.projects[storage_idx]
            row = {col: proj.get(col, "") for col in SUTUNLAR}
            row["_SEÇİM_"] = f"{i}"
            rows.append(row)
        # Put selection column first
        df = pd.DataFrame(rows)
        if not df.empty:
            cols = ["_SEÇİM_"] + [c for c in df.columns if c != "_SEÇİM_"]
            df = df[cols]
        return df

    def _materials_to_df(self, project: Project) -> pd.DataFrame:
        return pd.DataFrame([m.to_dict() for m in project.materials], columns=MALZEME_ALANLARI)

    def _df_to_material_rows(self, df: pd.DataFrame) -> List[List[str]]:
        if df is None or df.empty:
            return []
        df = df.fillna("")
        return df[MALZEME_ALANLARI].astype(str).values.tolist()

    # -----------------------------
    # Actions bound to UI
    # -----------------------------
    def action_filter(self, musteri: str, proje_no: str, fat_bas: str, fat_bit: str, ara: str):
        criteria = FilterCriteria(musteri=musteri, proje_no=proje_no, fat_bas=fat_bas, fat_bit=fat_bit, ara=ara)
        filtered_projects = self.controller.filter_projects(criteria)
        # rebuild indices mapping
        storage_index_map = {id(p): idx for idx, p in enumerate(self.data.projects)}
        self.filtered_indices = [storage_index_map.get(id(p), -1) for p in filtered_projects]
        self.filtered_indices = [i for i in self.filtered_indices if i >= 0]
        proj_df = self._projects_to_df(self.filtered_indices)
        choices = [f"{i} - {self.data.projects[idx].get('PROJE NO','')}" for i, idx in enumerate(self.filtered_indices)]
        return proj_df, gr.update(choices=choices, value=None), pd.DataFrame(columns=MALZEME_ALANLARI), ["" for _ in SUTUNLAR]

    def action_select_project(self, selected: str):
        if not selected:
            return pd.DataFrame(columns=MALZEME_ALANLARI), ["" for _ in SUTUNLAR]
        try:
            local_idx = int(str(selected).split("-", 1)[0].strip())
        except Exception:
            return pd.DataFrame(columns=MALZEME_ALANLARI), ["" for _ in SUTUNLAR]
        if local_idx < 0 or local_idx >= len(self.filtered_indices):
            return pd.DataFrame(columns=MALZEME_ALANLARI), ["" for _ in SUTUNLAR]
        storage_idx = self.filtered_indices[local_idx]
        proj = self.data.projects[storage_idx]
        fields = [proj.get(col, "") for col in SUTUNLAR]
        return self._materials_to_df(proj), fields

    def action_new_project(self, *field_values, materials_df: pd.DataFrame):
        fields_dict = {SUTUNLAR[i]: str(field_values[i] or "") for i in range(len(SUTUNLAR))}
        rows = self._df_to_material_rows(materials_df)
        self.controller.create_project(fields_dict, rows)
        # refresh filter to include new project
        proj_df = self._projects_to_df(list(range(len(self.data.projects))))
        self.filtered_indices = list(range(len(self.data.projects)))
        choices = [f"{i} - {self.data.projects[idx].get('PROJE NO','')}" for i, idx in enumerate(self.filtered_indices)]
        return gr.update(value=proj_df), gr.update(choices=choices, value=None), pd.DataFrame(columns=MALZEME_ALANLARI), ["" for _ in SUTUNLAR]

    def action_update_project(self, selected: str, *field_values, materials_df: pd.DataFrame):
        if not selected:
            return gr.Warning("Lütfen bir proje seçin."), gr.update(), gr.update(), gr.update()
        try:
            local_idx = int(str(selected).split("-", 1)[0].strip())
        except Exception:
            return gr.Warning("Geçersiz seçim."), gr.update(), gr.update(), gr.update()
        if local_idx < 0 or local_idx >= len(self.filtered_indices):
            return gr.Warning("Geçersiz seçim."), gr.update(), gr.update(), gr.update()
        storage_idx = self.filtered_indices[local_idx]
        fields_dict = {SUTUNLAR[i]: str(field_values[i] or "") for i in range(len(SUTUNLAR))}
        rows = self._df_to_material_rows(materials_df)
        self.controller.update_project(storage_idx, fields_dict, rows)
        # refresh current view
        proj_df = self._projects_to_df(self.filtered_indices)
        return gr.update(value=proj_df), gr.update(), gr.update(), gr.update()

    def action_delete_project(self, selected: str):
        if not selected:
            return gr.Warning("Lütfen bir proje seçin."), gr.update()
        try:
            local_idx = int(str(selected).split("-", 1)[0].strip())
        except Exception:
            return gr.Warning("Geçersiz seçim."), gr.update()
        if local_idx < 0 or local_idx >= len(self.filtered_indices):
            return gr.Warning("Geçersiz seçim."), gr.update()
        storage_idx = self.filtered_indices[local_idx]
        self.controller.delete_project(storage_idx)
        # Re-apply filter as indices shift
        all_indices = list(range(len(self.data.projects)))
        self.filtered_indices = all_indices
        proj_df = self._projects_to_df(self.filtered_indices)
        choices = [f"{i} - {self.data.projects[idx].get('PROJE NO','')}" for i, idx in enumerate(self.filtered_indices)]
        return gr.update(value=proj_df), gr.update(choices=choices, value=None)

    def action_save_json(self):
        self.data.save_json()
        return gr.Info("Veri kaydedildi (data.json)")

    def action_load_json(self):
        self.data.load_json()
        self.filtered_indices = list(range(len(self.data.projects)))
        proj_df = self._projects_to_df(self.filtered_indices)
        choices = [f"{i} - {self.data.projects[idx].get('PROJE NO','')}" for i, idx in enumerate(self.filtered_indices)]
        return gr.update(value=proj_df), gr.update(choices=choices, value=None)

    def action_import_excel(self, file_obj: gr.File | None):
        if not file_obj:
            return gr.Warning("Lütfen bir .xlsx dosyası yükleyin."), gr.update(), gr.update()
        self.data.import_from_excel(file_obj.name)
        self.filtered_indices = list(range(len(self.data.projects)))
        proj_df = self._projects_to_df(self.filtered_indices)
        choices = [f"{i} - {self.data.projects[idx].get('PROJE NO','')}" for i, idx in enumerate(self.filtered_indices)]
        return gr.update(value=proj_df), gr.update(choices=choices, value=None), gr.Info("Excel yüklendi")

    def action_export_report(self, fmt: str):
        # create a temporary file and return path for download
        suffix = ".xlsx" if fmt == "xlsx" else ".csv"
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self.data.export_report(path)
        return path

    # -----------------------------
    # Build UI
    # -----------------------------
    def build(self) -> gr.Blocks:
        with gr.Blocks(title=APP_TITLE) as demo:
            gr.Markdown(f"**{APP_TITLE} (Web/Colab Arayüzü)**")

            with gr.Row():
                t_musteri = gr.Textbox(label="Müşteri", scale=1)
                t_proje = gr.Textbox(label="Proje No", scale=1)
                t_fat_bas = gr.Textbox(label="FAT Baş (YYYY-MM-DD)", scale=1)
                t_fat_bit = gr.Textbox(label="FAT Bit (YYYY-MM-DD)", scale=1)
                t_ara = gr.Textbox(label="Ara", scale=2)
                btn_filter = gr.Button("Filtreyi Uygula", scale=0)

            proj_df = gr.Dataframe(headers=["_SEÇİM_"] + SUTUNLAR, label="Projeler (filtreli)", interactive=False, wrap=True, height=300)
            dd_select = gr.Dropdown(label="Proje Seç", choices=[])

            with gr.Accordion("Proje Detayları", open=True):
                with gr.Row():
                    proj_fields = [gr.Textbox(label=col) for col in SUTUNLAR]
                materials_df = gr.Dataframe(headers=MALZEME_ALANLARI, row_count=5, col_count=len(MALZEME_ALANLARI), interactive=True, label="Malzemeler")
                with gr.Row():
                    btn_new = gr.Button("Yeni Proje Kaydet")
                    btn_update = gr.Button("Seçili Projeyi Güncelle")
                    btn_delete = gr.Button("Seçili Projeyi Sil")

            with gr.Row():
                btn_save_json = gr.Button("Veriyi Kaydet (JSON)")
                btn_load_json = gr.Button("Veriyi Yükle (JSON)")
                up_excel = gr.File(file_types=[".xlsx"], label="Excel'den Yükle (.xlsx)")
                fmt = gr.Radio(["xlsx", "csv"], value="xlsx", label="Rapor Formatı")
                btn_export = gr.Button("Raporu Dışa Aktar")
                download_file = gr.File(label="İndirilecek Rapor", interactive=False)

            # wire
            btn_filter.click(self.action_filter, [t_musteri, t_proje, t_fat_bas, t_fat_bit, t_ara], [proj_df, dd_select, materials_df] + proj_fields)
            dd_select.change(self.action_select_project, [dd_select], [materials_df] + proj_fields)

            btn_new.click(self.action_new_project, proj_fields + [materials_df], [proj_df, dd_select, materials_df] + proj_fields)
            btn_update.click(self.action_update_project, [dd_select] + proj_fields + [materials_df], [proj_df, materials_df] + proj_fields)
            btn_delete.click(self.action_delete_project, [dd_select], [proj_df, dd_select])

            btn_save_json.click(self.action_save_json, [], [])
            btn_load_json.click(self.action_load_json, [], [proj_df, dd_select])
            up_excel.upload(self.action_import_excel, [up_excel], [proj_df, dd_select, up_excel])
            btn_export.click(self.action_export_report, [fmt], [download_file])

            # initial fill
            init_df = self._projects_to_df(self.filtered_indices)
            proj_df.value = init_df
            dd_select.choices = [f"{i} - {self.data.projects[idx].get('PROJE NO','')}" for i, idx in enumerate(self.filtered_indices)]

        return demo

    def run(self, share: bool = True, server_port: int = 7860) -> None:
        demo = self.build()
        demo.queue().launch(share=share, server_port=server_port)

