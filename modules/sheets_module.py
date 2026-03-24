"""
Sheets Module — XLSX/CSV/ODS: Convertir, Unir, Separar, Vista previa
"""

import os
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pandas as pd

from modules.base_module import (
    BaseModule, BG_DARK, BG_CARD, BG_ITEM,
    ACCENT, ACCENT_H, TEXT_PRI, TEXT_SEC, BORDER
)
from core.job_queue import JobStatus
from ui.widgets import DropZone, FileListWidget

TOOLS = [
    ("universal", "📊", "Convertir y Unir"),
    ("split",     "✂️", "Separar Hojas"),
    ("preview",   "👁️", "Vista Previa + Estadísticas"),
]

SHEET_EXTS = [".xlsx", ".xls", ".csv", ".ods"]


class _BaseSheetPanel(ctk.CTkFrame):
    title = ""
    description = ""
    multi_file = False
    allowed_exts = SHEET_EXTS

    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kwargs)
        self.app = app
        self.columnconfigure(0, weight=1)
        self._build_common()
        self._build_options()
        self._build_run_btn()

    def _build_common(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 4))
        ctk.CTkLabel(hdr, text=self.title,
                     font=("Segoe UI", 17, "bold"), text_color=TEXT_PRI).pack(anchor="w")
        ctk.CTkLabel(hdr, text=self.description,
                     font=("Segoe UI", 11), text_color=TEXT_SEC).pack(anchor="w", pady=(2,0))
        self._drop = DropZone(self, on_files=self._on_drop,
                              extensions=self.allowed_exts, height=100)
        self._drop.grid(row=1, column=0, sticky="ew", padx=24, pady=(12,8))
        self._file_list = FileListWidget(self)
        self._file_list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0,8))
        self.rowconfigure(2, weight=1)

    def _on_drop(self, paths):
        if not self.multi_file:
            self._file_list.clear()
        self._file_list.add_files(paths)

    def _build_options(self): pass

    def _build_run_btn(self):
        self._run_btn = ctk.CTkButton(self, text="▶  Ejecutar", height=42,
                                      fg_color=ACCENT, hover_color=ACCENT_H,
                                      font=("Segoe UI", 14, "bold"),
                                      corner_radius=10, command=self._run)
        self._run_btn.grid(row=10, column=0, sticky="ew", padx=24, pady=(8,20))

    def _run(self): raise NotImplementedError

    def _on_done(self, job):
        if job.status == JobStatus.DONE:
            r = job.result
            self.app.after(0, lambda: messagebox.showinfo("Listo", f"Completado:\n\n{r}"))
        elif job.status == JobStatus.ERROR:
            e = job.error
            self.app.after(0, lambda: messagebox.showerror("Error", e))

    def _section(self, text):
        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.grid(row=3, column=0, sticky="ew", padx=24, pady=(0,10))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 11, "bold"),
                     text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(10,6), sticky="w")
        return f

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        fmt = self._target_fmt.get().lower()
        out = filedialog.asksaveasfilename(defaultextension="."+fmt, initialfile="resultado."+fmt)
        if not out: return

        opts = {"clean_dupes": self._opt_dupes.get(), "clean_rows": self._opt_empty.get()}
        self.app.job_queue.submit(f"Pandas: {len(paths)} archivos", _heavy_sheet_task, paths, out, opts, on_done=self._on_done)


class SheetUniversalPanel(_BaseSheetPanel):
    title = "Procesamiento Universal"
    description = "Convierte, combina y limpia bases de datos masivas en segundos."
    multi_file = True

    def _build_options(self):
        f = self._section("Ajustes de Procesamiento")
        
        # Formato de salida
        self._target_fmt = ctk.CTkSegmentedButton(f, values=["XLSX", "CSV", "JSON"])
        self._target_fmt.set("XLSX")
        self._target_fmt.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        # Opciones de Limpieza (El valor añadido de la Fase 6)
        self._opt_dupes = ctk.CTkCheckBox(f, text="Eliminar duplicados", font=("Segoe UI", 12))
        self._opt_dupes.grid(row=2, column=0, padx=14, pady=2, sticky="w")
        self._opt_dupes.select()

        self._opt_empty = ctk.CTkCheckBox(f, text="Eliminar filas totalmente vacías", font=("Segoe UI", 12))
        self._opt_empty.grid(row=3, column=0, padx=14, pady=2, sticky="w")
        self._opt_empty.select()

        self._opt_strip = ctk.CTkCheckBox(f, text="Limpiar espacios en blanco (Trim)", font=("Segoe UI", 12))
        self._opt_strip.grid(row=4, column=0, padx=14, pady=(2, 12), sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        
        fmt = self._target_fmt.get().lower()
        out = filedialog.asksaveasfilename(defaultextension="."+fmt, initialfile="resultado."+fmt)
        if not out: return

        opts = {
            "clean_dupes": self._opt_dupes.get(),
            "clean_rows": self._opt_empty.get(),
            "strip_spaces": self._opt_strip.get()
        }

        self.app.job_queue.submit(f"Pandas: {len(paths)} archivos",
                                 _heavy_sheet_task, paths, out, opts,
                                 on_done=self._on_done)

class SplitSheetsPanel(_BaseSheetPanel):
    title = "Separar Hojas"
    description = "Exporta cada pestaña de un Excel como un archivo independiente."
    multi_file = False
    allowed_exts = [".xlsx", ".xls"]

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivo", "Añade un Excel para separar.")
            return
            
        out_dir = filedialog.askdirectory(title="Carpeta de salida")
        if not out_dir: return
        
        # Llamamos a la función de Pandas que tienes al final
        self.app.job_queue.submit(
            f"Separar: {os.path.basename(paths[0])}",
            _split_sheets_pandas, paths[0], out_dir,
            on_done=self._on_done
        )

class PreviewPanel(_BaseSheetPanel):
    title = "Vista Previa Pro"
    description = "Muestra los datos y genera estadísticas automáticas del archivo."
    multi_file = False

    def _build_options(self):
        # Creamos una sección con un cuadro de texto para el análisis
        f = self._section("Análisis de datos")
        self._text_box = ctk.CTkTextbox(f, height=400, font=("Consolas", 11),
                                         fg_color=BG_DARK, text_color=TEXT_PRI)
        self._text_box.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivo", "Añade un archivo para analizar.")
            return

        def _update_ui(job):
            if job.status == JobStatus.DONE:
                # Limpiamos e insertamos el resultado de Pandas
                self.app.after(0, lambda: (
                    self._text_box.delete("1.0", "end"),
                    self._text_box.insert("1.0", job.result)
                ))

        # Llamamos a la función de estadísticas de Pandas
        self.app.job_queue.submit(
            f"Analizando {os.path.basename(paths[0])}",
            _get_enhanced_preview, paths[0],
            on_done=_update_ui
        )

class SheetsModule(BaseModule):
    module_id = "sheets"

    def __init__(self, master, app, **kwargs):
        super().__init__(master, app, **kwargs)
        self.rowconfigure(0, weight=1)

        self.columnconfigure(0, weight=0, minsize=210) # 1. Menú lateral (fijo a 210px)
        self.columnconfigure(1, weight=0)              # 2. Hueco vacío (antiguo divisor)
        self.columnconfigure(2, weight=1)              # 3. PANEL CENTRAL (se estira a tope)

        self._panels = {}
        self._tool_btns = {}
        self._active_tool = ""
        self._build_sidebar()
        self._build_panels()
        self._switch_tool("universal")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(sb, text="Hojas de cálculo",
                     font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(
                     row=0, column=0, padx=14, pady=(18, 10), sticky="w")
        for i, (tid, icon, name) in enumerate(TOOLS):
            btn = ctk.CTkButton(sb, text=f"  {icon} {name}", anchor="w",
                                fg_color="transparent", hover_color=BG_ITEM,
                                text_color=TEXT_SEC, font=("Segoe UI", 13),
                                height=40, corner_radius=8,
                                command=lambda t=tid: self._switch_tool(t))
            btn.grid(row=i+1, column=0, padx=8, pady=2, sticky="ew")
            self._tool_btns[tid] = btn

    def _switch_tool(self, tool_id):
        if self._active_tool:
            self._panels[self._active_tool].grid_remove()
            self._tool_btns[self._active_tool].configure(fg_color="transparent", text_color=TEXT_SEC)
        self._panels[tool_id].grid()
        self._active_tool = tool_id
        self._tool_btns[tool_id].configure(fg_color=BG_ITEM, text_color=TEXT_PRI)

    def receive_files(self, paths):
        sheets = [p for p in paths if os.path.splitext(p)[1].lower() in SHEET_EXTS]
        if not sheets:
            return
        panel = self._panels.get(self._active_tool)
        if panel and hasattr(panel, "_file_list"):
            panel._file_list.add_files(sheets)

    def _build_panels(self):
        builders = {
                    "universal": SheetUniversalPanel,
                    "split":     SplitSheetsPanel, 
                    "preview":   PreviewPanel,
        }
        for tid, cls in builders.items():
            panel = cls(self, app=self.app)
            panel.grid(row=0, column=2, sticky="nsew")
            panel.grid_remove()
            self._panels[tid] = panel


# ── Funciones de operación ────────────────────────────────────────────────────

def _heavy_sheet_task(paths: list, output_path: str, options: dict, progress_cb=None):
    """Motor Pandas: Carga, limpia y une datos masivos."""
    try:
        dfs = []
        for i, p in enumerate(paths):
            ext = os.path.splitext(p)[1].lower()
            # Lectura automática (detecta delimitadores en CSV)
            df = pd.read_csv(p, sep=None, engine='python', encoding='utf-8-sig') if ext == ".csv" else pd.read_excel(p)
            
            # Limpieza profesional bajo demanda
            if options.get("clean_rows"): df.dropna(how='all', inplace=True)
            if options.get("clean_dupes"): df.drop_duplicates(inplace=True)
            
            dfs.append(df)
            if progress_cb: progress_cb((i + 0.5) / len(paths))

        final_df = pd.concat(dfs, ignore_index=True)
        
        ext_out = os.path.splitext(output_path)[1].lower()
        if ext_out == ".csv":
            final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        elif ext_out == ".json":
            final_df.to_json(output_path, orient='records', indent=4)
        else:
            final_df.to_excel(output_path, index=False)
        return f"Éxito. Filas totales: {len(final_df)}"
    except Exception as e: return f"Error: {str(e)}"

def _split_sheets_pandas(path: str, out_dir: str, progress_cb=None):
    """Separación de hojas 10x más rápida con Pandas."""
    try:
        # sheet_name=None carga todas las hojas en un diccionario
        df_dict = pd.read_excel(path, sheet_name=None)
        for i, (name, df) in enumerate(df_dict.items()):
            df.to_excel(os.path.join(out_dir, f"{name}.xlsx"), index=False)
            if progress_cb: progress_cb((i+1)/len(df_dict))
        return f"{len(df_dict)} archivos en {out_dir}"
    except Exception as e: return f"Error: {str(e)}"


def _get_enhanced_preview(path):
    """Genera vista previa y estadísticas del archivo."""
    ext = os.path.splitext(path)[1].lower()
    df = pd.read_csv(path, nrows=20) if ext == ".csv" else pd.read_excel(path, nrows=20)
    
    # Estadísticas básicas
    info = f"Filas totales (aprox): {len(df)}\nColumnas: {list(df.columns)}\n"
    stats = df.describe(include='all').to_string() # Resumen estadístico
    
    return f"{info}\n--- Primeras 20 filas ---\n{df.to_string(index=False)}\n\n--- Resumen Estadístico ---\n{stats}"