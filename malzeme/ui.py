from __future__ import annotations

import logging
import os
from typing import List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pyperclip  # type: ignore
    HAS_PYPERCLIP = True
except Exception:  # pragma: no cover
    HAS_PYPERCLIP = False

from . import APP_TITLE, APP_WINDOW_SIZE, SUTUNLAR, MALZEME_ALANLARI
from .controller import AppController, FilterCriteria
from .models import Project, Material
from .storage import DataStorage, SettingsStorage


class MalzemeApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(APP_WINDOW_SIZE)

        self.data = DataStorage()
        self.settings = SettingsStorage()
        self.controller = AppController(self.data)

        # State
        self._build_menu()
        self._build_filters()
        self._build_toolbar()
        self._build_tree()

        # Load persisted data if exists
        self.data.load_json()
        self._refresh_tree(self.data.projects)

        # Closing hook to persist settings
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -----------------------------
    # UI builders
    # -----------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Yeni Proje", command=self._yeni_proje_ekle)
        file_menu.add_separator()
        file_menu.add_command(label="Raporu Kaydet (Excel/CSV)", command=self._excel_kaydet_rapor)
        file_menu.add_command(label="Excel'den Yükle", command=self._excelden_yukle)
        file_menu.add_separator()
        file_menu.add_command(label="Veriyi Kaydet (JSON)", command=self.data.save_json)
        file_menu.add_command(label="Veriyi Yükle (JSON)", command=self.data.load_json)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.root.quit)
        menubar.add_cascade(label="Dosya", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Sütun genişliklerini kaydet", command=self._save_column_widths)
        menubar.add_cascade(label="Görünüm", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Hakkında", command=lambda: messagebox.showinfo("Hakkında", APP_TITLE))
        menubar.add_cascade(label="Yardım", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_filters(self) -> None:
        frame_filt = tk.Frame(self.root)
        frame_filt.pack(padx=8, pady=6, fill="x")

        tk.Label(frame_filt, text="Müşteri:").grid(row=0, column=0, sticky="e")
        self.entry_musteri = tk.Entry(frame_filt, width=18)
        self.entry_musteri.grid(row=0, column=1, padx=6)

        tk.Label(frame_filt, text="Proje No:").grid(row=0, column=2, sticky="e")
        self.entry_proje = tk.Entry(frame_filt, width=18)
        self.entry_proje.grid(row=0, column=3, padx=6)

        tk.Label(frame_filt, text="FAT Baş (YYYY-MM-DD):").grid(row=0, column=4, sticky="e")
        self.entry_fat_bas = tk.Entry(frame_filt, width=14)
        self.entry_fat_bas.grid(row=0, column=5, padx=6)
        tk.Label(frame_filt, text="FAT Bit (YYYY-MM-DD):").grid(row=0, column=6, sticky="e")
        self.entry_fat_bit = tk.Entry(frame_filt, width=14)
        self.entry_fat_bit.grid(row=0, column=7, padx=6)

        tk.Label(frame_filt, text="Ara:").grid(row=0, column=8, sticky="e")
        self.entry_ara = tk.Entry(frame_filt, width=24)
        self.entry_ara.grid(row=0, column=9, padx=6)

        btn_filt = tk.Button(frame_filt, text="Filtreyi Uygula", command=self._filtrele)
        btn_filt.grid(row=0, column=10, padx=10)

    def _build_toolbar(self) -> None:
        frame_btn = tk.Frame(self.root)
        frame_btn.pack(padx=8, pady=6, fill="x")

        btn_yeni = tk.Button(frame_btn, text="Yeni Proje Ekle", command=self._yeni_proje_ekle)
        btn_yeni.pack(side="left", padx=5)

        btn_kaydet = tk.Button(frame_btn, text="Raporu Kaydet (Excel/CSV)", command=self._excel_kaydet_rapor)
        btn_kaydet.pack(side="left", padx=5)

        btn_yukle = tk.Button(frame_btn, text="Excel'den Yükle", command=self._excelden_yukle)
        btn_yukle.pack(side="left", padx=5)

    def _build_tree(self) -> None:
        self.tree = ttk.Treeview(self.root, columns=SUTUNLAR, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=34, anchor="center")
        for col in SUTUNLAR:
            self.tree.heading(col, text=col)
            default_width = 140
            width = self.settings.get_column_width(col, default_width)
            self.tree.column(col, width=width, anchor="center")

        ys = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(self.root, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=ys.set, xscroll=xs.set)

        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        ys.place(relx=1.0, rely=0.5, relheight=0.78, anchor="e")
        xs.pack(fill="x", padx=8, pady=(0, 8))

        self.tree.bind("<Double-1>", self._toggle_item)
        self.tree.bind("<Button-3>", self._sag_tik)

    # -----------------------------
    # Helpers
    # -----------------------------
    def _toggle_item(self, event) -> None:
        item_id = self.tree.focus()
        if not item_id:
            return
        if self.tree.get_children(item_id):
            self.tree.item(item_id, open=not self.tree.item(item_id, "open"))

    def _refresh_tree(self, projects: List[Project]) -> None:
        self.tree.delete(*self.tree.get_children())
        for idx, proj in enumerate(projects):
            self._ekle_tree(proj, index=idx)

    def _ekle_tree(self, proje: Project, index: int) -> None:
        proje_id = f"proje_{index}"
        self.tree.insert("", "end", iid=proje_id, text="+", values=[proje.get(col, "") for col in SUTUNLAR])
        for m_index, malzeme in enumerate(proje.materials):
            malzeme_id = f"{proje_id}_malzeme_{m_index}"
            values = ["", "", "", "", "", *malzeme.to_list(), ""]
            self.tree.insert(proje_id, "end", iid=malzeme_id, text="", values=values)
        self.tree.item(proje_id, open=True)

    # -----------------------------
    # Actions
    # -----------------------------
    def _filtrele(self) -> None:
        criteria = FilterCriteria(
            musteri=self.entry_musteri.get(),
            proje_no=self.entry_proje.get(),
            fat_bas=self.entry_fat_bas.get(),
            fat_bit=self.entry_fat_bit.get(),
            ara=self.entry_ara.get(),
        )
        sonuc = self.controller.filter_projects(criteria)
        self._refresh_tree(sonuc)

    def _yeni_proje_ekle(self) -> None:
        form = tk.Toplevel(self.root)
        form.title("Yeni Proje Ekle")
        form.geometry("560x640")

        entries = {}
        for i, col in enumerate(SUTUNLAR):
            tk.Label(form, text=col).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            ent = tk.Entry(form, width=44)
            ent.grid(row=i, column=1, pady=2)
            entries[col] = ent

        tk.Label(
            form,
            text="Malzeme Listesi (Excel’den yapıştır):\nAG Kod | AG Tanım | AG Miktar | YG Kod | YG Tanım | YG Miktar",
        ).grid(row=len(SUTUNLAR), column=0, columnspan=2, sticky="w", padx=6, pady=(8, 2))
        malzeme_text = tk.Text(form, width=64, height=12)
        malzeme_text.grid(row=len(SUTUNLAR) + 1, column=0, columnspan=2, padx=6, pady=4)

        def kaydet() -> None:
            fields = {col: entries[col].get() for col in SUTUNLAR}
            satirlar = [s for s in malzeme_text.get("1.0", tk.END).strip().split("\n") if s.strip()]
            materials_rows = []
            for s in satirlar:
                prc = [x.strip() for x in s.split("|")]
                if len(prc) == 6:
                    materials_rows.append(prc)
            self.controller.create_project(fields, materials_rows)
            self._refresh_tree(self.data.projects)
            form.destroy()

        tk.Button(form, text="Kaydet", width=18, command=kaydet).grid(row=len(SUTUNLAR) + 2, column=0, columnspan=2, pady=10)

    def _duzenle_projeyi(self, proje_id: str) -> None:
        index = int(proje_id.split("_")[1])
        proje = self.data.projects[index]

        form = tk.Toplevel(self.root)
        form.title("Proje Düzenle")
        form.geometry("560x640")

        entries = {}
        for i, col in enumerate(SUTUNLAR):
            tk.Label(form, text=col).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            ent = tk.Entry(form, width=44)
            ent.insert(0, proje.get(col, ""))
            ent.grid(row=i, column=1, pady=2)
            entries[col] = ent

        tk.Label(
            form,
            text="Malzeme Listesi (Excel’den yapıştır / düzenle):\nAG Kod | AG Tanım | AG Miktar | YG Kod | YG Tanım | YG Miktar",
        ).grid(row=len(SUTUNLAR), column=0, columnspan=2, sticky="w", padx=6, pady=(8, 2))
        malzeme_text = tk.Text(form, width=64, height=12)
        malzeme_text.grid(row=len(SUTUNLAR) + 1, column=0, columnspan=2, padx=6, pady=4)
        for m in proje.materials:
            malzeme_text.insert(tk.END, " | ".join(m.to_list()) + "\n")

        def kaydet() -> None:
            fields = {col: entries[col].get() for col in SUTUNLAR}
            satirlar = [s for s in malzeme_text.get("1.0", tk.END).strip().split("\n") if s.strip()]
            materials_rows = []
            for s in satirlar:
                prc = [x.strip() for x in s.split("|")]
                if len(prc) == 6:
                    materials_rows.append(prc)
            self.controller.update_project(index, fields, materials_rows)
            self._refresh_tree(self.data.projects)
            form.destroy()

        tk.Button(form, text="Kaydet", width=18, command=kaydet).grid(row=len(SUTUNLAR) + 2, column=0, columnspan=2, pady=10)

    def _sil_projeyi(self, proje_id: str) -> None:
        index = int(proje_id.split("_")[1])
        if messagebox.askyesno("Silme Onayı", "Projeyi ve tüm malzemelerini silmek istiyor musunuz?"):
            self.controller.delete_project(index)
            self._refresh_tree(self.data.projects)

    def _duzenle_malzeme(self, malzeme_id: str) -> None:
        proje_id = "_".join(malzeme_id.split("_")[:2])
        pidx = int(proje_id.split("_")[1])
        midx = int(malzeme_id.split("_")[-1])
        proje = self.data.projects[pidx]
        mlz = proje.materials[midx]

        form = tk.Toplevel(self.root)
        form.title("Malzeme Düzenle")
        form.geometry("420x320")

        entries = {}
        for i, a in enumerate(MALZEME_ALANLARI):
            tk.Label(form, text=a).grid(row=i, column=0, sticky="w", padx=6, pady=2)
            ent = tk.Entry(form, width=28)
            ent.insert(0, mlz.to_dict()[a])
            ent.grid(row=i, column=1, pady=2)
            entries[a] = ent

        def kaydet() -> None:
            values = [entries[a].get() for a in MALZEME_ALANLARI]
            self.controller.update_material(pidx, midx, values)
            self._refresh_tree(self.data.projects)
            form.destroy()

        tk.Button(form, text="Kaydet", width=16, command=kaydet).grid(row=len(MALZEME_ALANLARI), column=0, columnspan=2, pady=10)

    def _sil_malzeme(self, malzeme_id: str) -> None:
        proje_id = "_".join(malzeme_id.split("_")[:2])
        pidx = int(proje_id.split("_")[1])
        midx = int(malzeme_id.split("_")[-1])
        if messagebox.askyesno("Silme Onayı", "Bu malzemeyi silmek istiyor musunuz?"):
            self.controller.delete_material(pidx, midx)
            self._refresh_tree(self.data.projects)

    def _kopyala_malzeme(self, malzeme_id: str) -> None:
        if not HAS_PYPERCLIP:
            self._info_missing_pyperclip()
            return
        proje_id = "_".join(malzeme_id.split("_")[:2])
        pidx = int(proje_id.split("_")[1])
        midx = int(malzeme_id.split("_")[-1])
        mlz = self.data.projects[pidx].materials[midx]
        import pyperclip  # type: ignore

        pyperclip.copy(" | ".join(mlz.to_list()))
        messagebox.showinfo("Kopyalandı", "Malzeme panoya kopyalandı!")

    def _kopyala_secili_malzemeler(self) -> None:
        if not HAS_PYPERCLIP:
            self._info_missing_pyperclip()
            return
        secilenler = self.tree.selection()
        satirlar = []
        for iid in secilenler:
            if "_malzeme_" in iid:
                proje_id = "_".join(iid.split("_")[:2])
                pidx = int(proje_id.split("_")[1])
                midx = int(iid.split("_")[-1])
                satirlar.append(" | ".join(self.data.projects[pidx].materials[midx].to_list()))
        if not satirlar:
            messagebox.showinfo("Bilgi", "Kopyalanacak malzeme seçilmedi.")
            return
        import pyperclip  # type: ignore

        pyperclip.copy("\n".join(satirlar))
        messagebox.showinfo("Kopyalandı", f"{len(satirlar)} satır panoya kopyalandı!")

    def _sag_tik(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        menu = tk.Menu(self.root, tearoff=0)
        if "_malzeme_" in item_id:
            menu.add_command(label="Düzenle", command=lambda iid=item_id: self._duzenle_malzeme(iid))
            menu.add_command(label="Sil", command=lambda iid=item_id: self._sil_malzeme(iid))
            menu.add_separator()
            menu.add_command(label="Kopyala", command=lambda iid=item_id: self._kopyala_malzeme(iid))
            menu.add_command(label="Seçilenleri Kopyala", command=self._kopyala_secili_malzemeler)
        else:
            menu.add_command(label="Düzenle", command=lambda iid=item_id: self._duzenle_projeyi(iid))
            menu.add_command(label="Sil", command=lambda iid=item_id: self._sil_projeyi(iid))
        menu.post(event.x_root, event.y_root)

    def _excel_kaydet_rapor(self) -> None:
        # Build a temporary project list from the currently visible tree
        gorunen: List[Project] = []
        for pid in self.tree.get_children(""):
            values = self.tree.item(pid, "values")
            children: List[List[str]] = []
            for mid in self.tree.get_children(pid):
                mvals = self.tree.item(mid, "values")
                children.append([mvals[5], mvals[6], mvals[7], mvals[8], mvals[9], mvals[10]])
            gorunen.append(Project.from_tree_values(list(values), children))

        # Temporarily replace data for export
        original = self.data.projects
        try:
            self.data.projects = gorunen
            dosya = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Dosyası (*.xlsx)", "*.xlsx"), ("CSV (*.csv)", "*.csv")],
            )
            if not dosya:
                return
            self.data.export_report(dosya)
            messagebox.showinfo("Rapor Kaydedildi", f"Dosya oluşturuldu:\n{dosya}")
        except Exception as exc:
            logging.exception("Rapor kaydetme hatası: %s", exc)
            messagebox.showerror("Hata", str(exc))
        finally:
            self.data.projects = original

    def _excelden_yukle(self) -> None:
        dosya = filedialog.askopenfilename(filetypes=[("Excel Dosyası (*.xlsx)", "*.xlsx")])
        if not dosya:
            return
        try:
            self.data.import_from_excel(dosya)
            self._refresh_tree(self.data.projects)
        except Exception as exc:
            logging.exception("Excel yükleme hatası: %s", exc)
            messagebox.showerror("Hata", str(exc))

    def _save_column_widths(self) -> None:
        for col in SUTUNLAR:
            width = self.tree.column(col, width=None)
            try:
                self.settings.set_column_width(col, int(width))
            except Exception:
                pass
        self.settings.save()
        messagebox.showinfo("Kaydedildi", "Sütun genişlikleri kaydedildi.")

    def _info_missing_pyperclip(self) -> None:
        messagebox.showwarning(
            "Kopyalama için öneri",
            "Panoya kopyalamak için 'pyperclip' modülünü kurabilirsiniz:\n\npip install pyperclip",
        )

    def _on_close(self) -> None:
        try:
            self._save_column_widths()
            self.data.save_json()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()

