"""
PDF Module — Unir, Separar, Extraer, Rotar, Comprimir, Contraseña
"""

import os
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pypdf import PdfReader, PdfWriter
import zipfile

from modules.base_module import (
    BaseModule, BG_DARK, BG_CARD, BG_ITEM,
    ACCENT, ACCENT_H, TEXT_PRI, TEXT_SEC, SUCCESS, DANGER, BORDER
)
from core.job_queue import JobStatus
from ui.widgets import DropZone, FileListWidget

TOOLS = [
    ("merge",    "🔗", "Unir PDFs"),
    ("split",    "✂",  "Separar"),
    ("extract",  "📤", "Extraer páginas"),
    ("rotate",   "🔄", "Rotar"),
    ("compress", "📦", "Optimizar tamaño"),
    ("zip",      "🗜",  "Empaquetar ZIP"),
    ("password", "🔒", "Contraseña"),
]

class PdfModule(BaseModule):
    module_id = "pdf"

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
        self._switch_tool("merge")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(sb, text="Herramientas PDF",
                     font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(
                     row=0, column=0, padx=14, pady=(18, 10), sticky="w")
        for i, (tid, icon, name) in enumerate(TOOLS):
            btn = ctk.CTkButton(sb, text=f"  {icon}  {name}", anchor="w",
                                fg_color="transparent", hover_color=BG_ITEM,
                                text_color=TEXT_SEC, font=("Segoe UI", 13),
                                height=40, corner_radius=8,
                                command=lambda t=tid: self._switch_tool(t))
            btn.grid(row=i+1, column=0, padx=8, pady=2, sticky="ew")
            self._tool_btns[tid] = btn

    def _switch_tool(self, tool_id):
        if self._active_tool:
            self._panels[self._active_tool].grid_remove()
            self._tool_btns[self._active_tool].configure(
                fg_color="transparent", text_color=TEXT_SEC)
        self._panels[tool_id].grid()
        self._active_tool = tool_id
        self._tool_btns[tool_id].configure(fg_color=BG_ITEM, text_color=TEXT_PRI)

    def receive_files(self, paths):
        pdfs = [p for p in paths if p.lower().endswith(".pdf")]
        if not pdfs:
            return
        panel = self._panels.get(self._active_tool)
        if panel and hasattr(panel, "_file_list"):
            panel._file_list.add_files(pdfs)

    def _build_panels(self):
        builders = {"merge": MergePanel, "split": SplitPanel, "extract": ExtractPanel,
                    "rotate": RotatePanel, "compress": CompressPanel, "zip": ZipPanel, "password": PasswordPanel}
        for tid, cls in builders.items():
            panel = cls(self, app=self.app)
            panel.grid(row=0, column=2, sticky="nsew")
            panel.grid_remove()
            self._panels[tid] = panel


class _BasePdfPanel(ctk.CTkFrame):
    title = ""
    description = ""
    multi_file = False

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
                     font=("Segoe UI", 11), text_color=TEXT_SEC).pack(anchor="w", pady=(2, 0))
        self._drop = DropZone(self, on_files=self._on_drop, extensions=[".pdf"],
                              height=100, label="Arrastra PDF(s) aquí")
        self._drop.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 8))
        self._file_list = FileListWidget(self, on_change=self._on_list_change, show_pages=True)
        self._file_list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self.rowconfigure(2, weight=1)

    def _on_drop(self, paths):
        if not self.multi_file:
            self._file_list.clear()
        self._file_list.add_files(paths)

    def _on_list_change(self): pass
    def _build_options(self): pass

    def _build_run_btn(self):
        self._run_btn = ctk.CTkButton(self, text="▶  Ejecutar", height=42,
                                      fg_color=ACCENT, hover_color=ACCENT_H,
                                      font=("Segoe UI", 14, "bold"),
                                      corner_radius=10, command=self._run)
        self._run_btn.grid(row=10, column=0, sticky="ew", padx=24, pady=(8, 20))

    def _run(self): raise NotImplementedError

    def _ask_save(self, title="Guardar como", default="resultado.pdf"):
        return filedialog.asksaveasfilename(title=title, defaultextension=".pdf",
               filetypes=[("PDF", "*.pdf")], initialfile=default) or None

    def _ask_dir(self, title="Seleccionar carpeta"):
        return filedialog.askdirectory(title=title) or None

    def _on_done(self, job):
        if job.status == JobStatus.DONE:
            r = job.result
            self.app.after(0, lambda: messagebox.showinfo("Listo", f"Completado:\n\n{r}"))
        elif job.status == JobStatus.ERROR:
            e = job.error
            self.app.after(0, lambda: messagebox.showerror("Error", e))

    def _section(self, text):
        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 10))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 11, "bold"),
                     text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(10,6), sticky="w")
        return f


class MergePanel(_BasePdfPanel):
    title = "Unir PDFs"
    description = "Combina varios PDFs en uno. Reordena con ▲▼."
    multi_file = True

    def _run(self):
        paths = self._file_list.paths
        if len(paths) < 2:
            messagebox.showwarning("Pocos archivos", "Añade al menos 2 PDFs."); return
        out = self._ask_save(default="combinado.pdf")
        if not out: return
        self.app.job_queue.submit(f"Unir {len(paths)} PDFs", _merge_pdfs, paths, out, on_done=self._on_done)


class SplitPanel(_BasePdfPanel):
    title = "Separar PDF"
    description = "Divide un PDF en archivos individuales."

    def _build_options(self):
        f = self._section("Modo de separación")
        self._mode = ctk.StringVar(value="each")
        ctk.CTkRadioButton(f, text="Cada página en un archivo",
                           variable=self._mode, value="each",
                           text_color=TEXT_PRI, command=self._toggle_n).grid(
                           row=1, column=0, padx=14, pady=4, sticky="w")
        row_n = ctk.CTkFrame(f, fg_color="transparent")
        row_n.grid(row=2, column=0, padx=14, pady=(2,10), sticky="w")
        ctk.CTkRadioButton(row_n, text="Cada", variable=self._mode, value="n",
                           text_color=TEXT_PRI, command=self._toggle_n).pack(side="left")
        self._n_entry = ctk.CTkEntry(row_n, width=52, height=28, placeholder_text="N", state="disabled")
        self._n_entry.pack(side="left", padx=8)
        ctk.CTkLabel(row_n, text="páginas por archivo",
                     font=("Segoe UI", 12), text_color=TEXT_SEC).pack(side="left")

    def _toggle_n(self):
        self._n_entry.configure(state="normal" if self._mode.get() == "n" else "disabled")

    def _run(self):
        paths = self._file_list.paths
        if not paths: messagebox.showwarning("Sin archivo", "Añade un PDF."); return
        out_dir = self._ask_dir()
        if not out_dir: return
        mode = self._mode.get()
        n = 1
        if mode == "n":
            try: n = int(self._n_entry.get()); assert n >= 1
            except: messagebox.showerror("Error", "N debe ser un número >= 1."); return
        self.app.job_queue.submit(f"Separar {os.path.basename(paths[0])}", _split_pdf,
                                  paths[0], out_dir, mode, n, on_done=self._on_done)


class ExtractPanel(_BasePdfPanel):
    title = "Extraer páginas"
    description = "Extrae páginas concretas de un PDF."

    def _build_options(self):
        f = self._section("Páginas a extraer")
        f.columnconfigure(0, weight=1)

        row_opts = ctk.CTkFrame(f, fg_color="transparent")
        row_opts.grid(row=1, column=0, padx=14, pady=(5, 12), sticky="ew")

        self._pages_entry = ctk.CTkEntry(row_opts, width=200, height=32,
                                         placeholder_text="Ej: 1-3, 5, 8-10", font=("Segoe UI", 12))
        self._pages_entry.pack(side="left")

        ctk.CTkLabel(row_opts, text="Las páginas se numeran desde 1.",
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack(side="left", padx=(15, 0))

    def _run(self):
        paths = self._file_list.paths
        if not paths: messagebox.showwarning("Sin archivo", "Añade un PDF."); return
        rng = self._pages_entry.get().strip()
        if not rng: messagebox.showwarning("Sin rango", "Escribe qué páginas extraer."); return
        out = self._ask_save(default="extraido.pdf")
        if not out: return
        self.app.job_queue.submit(f"Extraer de {os.path.basename(paths[0])}", _extract_pages,
                                  paths[0], rng, out, on_done=self._on_done)


class RotatePanel(_BasePdfPanel):
    title = "Rotar páginas"
    description = "Gira las páginas de un PDF."

    def _build_options(self):
        f = self._section("Opciones de rotación")
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text="Ángulo:", font=("Segoe UI", 12), text_color=TEXT_PRI).grid(
                     row=1, column=0, padx=14, pady=(0,4), sticky="w")
        self._angle = ctk.CTkSegmentedButton(f, values=["90°", "180°", "270°"], font=("Segoe UI", 12))
        self._angle.set("90°")
        self._angle.grid(row=2, column=0, padx=14, pady=(0,10), sticky="w")
        ctk.CTkLabel(f, text="Páginas (vacío = todas):", font=("Segoe UI", 12),
                     text_color=TEXT_PRI).grid(row=3, column=0, padx=14, pady=(4,4), sticky="w")
        self._pages_entry = ctk.CTkEntry(f, height=32, placeholder_text="Ej: 1, 3, 5", font=("Segoe UI", 12))
        self._pages_entry.grid(row=4, column=0, padx=14, pady=(0,12), sticky="ew")

    def _run(self):
        paths = self._file_list.paths
        if not paths: messagebox.showwarning("Sin archivo", "Añade un PDF."); return
        angle = int(self._angle.get().replace("°", ""))
        pages_str = self._pages_entry.get().strip()
        out = self._ask_save(default="rotado.pdf")
        if not out: return
        self.app.job_queue.submit(f"Rotar {os.path.basename(paths[0])}", _rotate_pages,
                                  paths[0], angle, pages_str, out, on_done=self._on_done)


class CompressPanel(_BasePdfPanel):
    title = "Comprimir PDF"
    description = "Reduce el tamaño del archivo recomprimiendo sus imágenes internas."

    def _build_options(self):
        f = self._section("Nivel de compresión")
        f.columnconfigure(0, weight=1)

        row_opts = ctk.CTkFrame(f, fg_color="transparent")
        row_opts.grid(row=1, column=0, padx=14, pady=(5, 12), sticky="ew")

        self._quality = ctk.CTkSegmentedButton(
            row_opts, values=["Alta (90)", "Media (72)", "Baja (50)"],
            font=("Segoe UI", 12),
        )
        self._quality.set("Media (72)")
        self._quality.pack(side="left")

        ctk.CTkLabel(row_opts, text="Afecta a la calidad de las imágenes (JPEG).",
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack(side="left", padx=(15, 0))

    def _run(self):
        paths = self._file_list.paths
        if not paths: messagebox.showwarning("Sin archivo", "Añade un PDF."); return

        q_map = {"Alta (90)": 90, "Media (72)": 72, "Baja (50)": 50}
        q_val = q_map.get(self._quality.get(), 72)

        out = filedialog.asksaveasfilename(
            title="Guardar PDF comprimido", defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], initialfile="comprimido.pdf"
        )
        if not out: return
        self.app.job_queue.submit(
            f"Comprimir {os.path.basename(paths[0])}",
            _compress_pdf, paths[0], out, q_val,
            on_done=self._on_done,
        )


class PasswordPanel(_BasePdfPanel):
    title = "Contraseña PDF"
    description = "Añade o quita protección por contraseña."

    def _build_options(self):
        f = self._section("Acción")
        f.columnconfigure(0, weight=1)
        self._action = ctk.StringVar(value="add")
        ctk.CTkRadioButton(f, text="Añadir contraseña", variable=self._action, value="add",
                           text_color=TEXT_PRI).grid(row=1, column=0, padx=14, pady=(0,4), sticky="w")
        ctk.CTkRadioButton(f, text="Quitar contraseña (requiere la actual)",
                           variable=self._action, value="remove",
                           text_color=TEXT_PRI).grid(row=2, column=0, padx=14, pady=(0,10), sticky="w")
        ctk.CTkLabel(f, text="Contraseña:", font=("Segoe UI", 12), text_color=TEXT_PRI).grid(
                     row=3, column=0, padx=14, pady=(0,4), sticky="w")
        self._pw_entry = ctk.CTkEntry(f, height=32, show="*",
                                       placeholder_text="Introduce la contraseña", font=("Segoe UI", 12))
        self._pw_entry.grid(row=4, column=0, padx=14, pady=(0,12), sticky="ew")

    def _run(self):
        paths = self._file_list.paths
        if not paths: messagebox.showwarning("Sin archivo", "Añade un PDF."); return
        pw = self._pw_entry.get()
        if not pw: messagebox.showwarning("Sin contraseña", "Introduce una contraseña."); return
        out = self._ask_save(default="protegido.pdf")
        if not out: return
        self.app.job_queue.submit(f"Contraseña {os.path.basename(paths[0])}", _password_pdf,
                                  paths[0], self._action.get(), pw, out, on_done=self._on_done)


# ── Funciones de operación (hilo separado) ────────────────────────────────────

def _merge_pdfs(paths, output, progress_cb=None):
    writer = PdfWriter()
    for i, path in enumerate(paths):
        writer.append(path)
        if progress_cb: progress_cb((i + 1) / len(paths))

    with open(output, "wb") as f:
        writer.write(f)
    writer.close()
    return output

def _split_pdf(path, out_dir, mode, n, progress_cb=None):
    reader = PdfReader(path)
    total = len(reader.pages)
    stem = os.path.splitext(os.path.basename(path))[0]
    created = []
    if mode == "each":
        for i, page in enumerate(reader.pages):
            w = PdfWriter(); w.add_page(page)
            out = os.path.join(out_dir, f"{stem}_p{i+1:04d}.pdf")
            with open(out, "wb") as f: w.write(f)
            created.append(out)
            if progress_cb: progress_cb((i+1)/total)
    else:
        chunk = 0
        for start in range(0, total, n):
            chunk += 1; w = PdfWriter()
            for i in range(start, min(start+n, total)): w.add_page(reader.pages[i])
            out = os.path.join(out_dir, f"{stem}_parte{chunk:03d}.pdf")
            with open(out, "wb") as f: w.write(f)
            created.append(out)
            if progress_cb: progress_cb(min(start+n, total)/total)
    return f"{len(created)} archivos en:\n{out_dir}"

def _parse_ranges(s, total):
    idxs = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            idxs.extend(range(max(1,int(a.strip()))-1, min(total,int(b.strip()))))
        else:
            idx = int(part.strip())-1
            if 0 <= idx < total: idxs.append(idx)
    return sorted(set(idxs))

def _extract_pages(path, ranges_str, output, progress_cb=None):
    reader = PdfReader(path)
    idxs = _parse_ranges(ranges_str, len(reader.pages))
    if not idxs: raise ValueError("Rango de páginas inválido.")
    writer = PdfWriter()
    for i, idx in enumerate(idxs):
        writer.add_page(reader.pages[idx])
        if progress_cb: progress_cb((i+1)/len(idxs))
    with open(output, "wb") as f: writer.write(f)
    return output

def _rotate_pages(path, angle, pages_str, output, progress_cb=None):
    reader = PdfReader(path)
    writer = PdfWriter()
    total = len(reader.pages)
    target = set(_parse_ranges(pages_str, total)) if pages_str.strip() else set(range(total))
    for i, page in enumerate(reader.pages):
        if i in target: page.rotate(angle)
        writer.add_page(page)
        if progress_cb: progress_cb((i+1)/total)
    with open(output, "wb") as f: writer.write(f)
    return output


def _compress_pdf(path: str, out: str, quality: int = 72, progress_cb=None) -> str:
    from PIL import Image

    reader = PdfReader(path)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        writer.add_page(page)
        if "/Resources" in page and "/XObject" in page["/Resources"]:
            xobj = page["/Resources"]["/XObject"].get_object()
            for obj in xobj:
                if xobj[obj]["/Subtype"] == "/Image":
                    try:
                        img_data = xobj[obj].get_data()
                        img = Image.open(io.BytesIO(img_data))

                        # JPEGs no soportan transparencia ni paletas, forzamos RGB puro
                        if img.mode != "RGB":
                            img = img.convert("RGB")

                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
                        new_data = img_byte_arr.getvalue()

                        if len(new_data) < len(img_data):
                            xobj[obj]._data = new_data

                            xobj[obj][NameObject("/Filter")] = NameObject("/DCTDecode")
                            xobj[obj][NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
                            xobj[obj][NameObject("/BitsPerComponent")] = NumberObject(8)

                            # Borramos rastros de la imagen original (transparencias, decodificadores antiguos)
                            for key in ["/DecodeParms", "/SMask", "/Mask", "/ColorTransform"]:
                                if key in xobj[obj]:
                                    del xobj[obj][key]

                    except Exception:
                        # Si una imagen está corrupta o es rara, la ignoramos y el PDF no se rompe
                        pass

        if progress_cb: progress_cb((i + 1) / len(reader.pages))

    writer.compress_identical_objects()
    with open(out, "wb") as f:
        writer.write(f)

    orig = os.path.getsize(path) // 1024
    new = os.path.getsize(out) // 1024
    saved = max(0, orig - new)
    ratio = int(saved / orig * 100) if orig else 0
    return f"{out}\n\nOriginal: {orig} KB  →  Resultado: {new} KB (−{ratio}%)"

def _password_pdf(path, action, password, output, progress_cb=None):
    reader = PdfReader(path)
    writer = PdfWriter()
    if action == "remove":
        if reader.is_encrypted: reader.decrypt(password)
        writer.append(reader); writer.remove_encryption()
    else:
        writer.append(reader); writer.encrypt(password)
    if progress_cb: progress_cb(0.9)
    with open(output, "wb") as f: writer.write(f)
    if progress_cb: progress_cb(1.0)
    return output


# ── ZipPanel ──────────────────────────────────────────────────────────────────

class ZipPanel(ctk.CTkFrame):
    """Empaqueta cualquier tipo de archivo en un ZIP."""
    title = "Empaquetar ZIP"
    description = "Comprime varios archivos (de cualquier tipo) en un .zip."

    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kwargs)
        self.app = app
        self.columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self):
        # Cabecera
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 4))
        ctk.CTkLabel(hdr, text=self.title,
                     font=("Segoe UI", 17, "bold"), text_color=TEXT_PRI).pack(anchor="w")
        ctk.CTkLabel(hdr, text=self.description,
                     font=("Segoe UI", 11), text_color=TEXT_SEC).pack(anchor="w", pady=(2, 0))

        # DropZone sin filtro de extensión — acepta cualquier archivo
        from ui.widgets import DropZone, FileListWidget
        self._drop = DropZone(self, on_files=self._on_drop,
                              extensions=[], height=100,
                              label="Arrastra cualquier archivo aquí")
        self._drop.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 8))

        self._file_list = FileListWidget(self)
        self._file_list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self.rowconfigure(2, weight=1)

        # Opciones
        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 10))
        f.columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Opciones", font=("Segoe UI", 11, "bold"),
                     text_color=TEXT_SEC).grid(row=0, column=0, columnspan=2,
                     padx=14, pady=(10, 6), sticky="w")

        ctk.CTkLabel(f, text="Nivel de compresión:",
                     font=("Segoe UI", 12), text_color=TEXT_PRI).grid(
                     row=1, column=0, padx=14, pady=(0, 12), sticky="w")
        self._level = ctk.CTkSegmentedButton(
            f, values=["Rápido", "Normal", "Máximo"],
            font=("Segoe UI", 12))
        self._level.set("Normal")
        self._level.grid(row=1, column=1, padx=14, pady=(0, 12), sticky="w")

        # Botón ejecutar
        ctk.CTkButton(self, text="▶  Crear ZIP", height=42,
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      font=("Segoe UI", 14, "bold"),
                      corner_radius=10, command=self._run).grid(
                      row=10, column=0, sticky="ew", padx=24, pady=(8, 20))

    def _on_drop(self, paths):
        self._file_list.add_files(paths)

    def _on_done(self, job):
        if job.status == JobStatus.DONE:
            r = job.result
            self.app.after(0, lambda: messagebox.showinfo("Listo", f"ZIP creado:\n\n{r}"))
        elif job.status == JobStatus.ERROR:
            e = job.error
            self.app.after(0, lambda: messagebox.showerror("Error", e))

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivos", "Añade al menos un archivo."); return
        out = filedialog.asksaveasfilename(
            title="Guardar ZIP", defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")], initialfile="archivos.zip")
        if not out: return
        level_map = {"Rápido": 1, "Normal": 6, "Máximo": 9}
        level = level_map.get(self._level.get(), 6)
        self.app.job_queue.submit(
            f"ZIP ({len(paths)} archivos)",
            _create_zip, paths, out, level,
            on_done=self._on_done,
        )


def _create_zip(paths: list, output: str, compression_level: int, progress_cb=None) -> str:
    total_size = sum(os.path.getsize(p) for p in paths if os.path.exists(p))
    done_size = 0

    with zipfile.ZipFile(output, "w",
                         compression=zipfile.ZIP_DEFLATED,
                         compresslevel=compression_level) as zf:
        for path in paths:
            zf.write(path, arcname=os.path.basename(path))
            done_size += os.path.getsize(path) if os.path.exists(path) else 0
            if progress_cb and total_size:
                progress_cb(done_size / total_size)

    orig_kb = total_size // 1024
    zip_kb  = os.path.getsize(output) // 1024
    ratio   = int((1 - zip_kb / orig_kb) * 100) if orig_kb else 0
    return f"{output}\n\n{len(paths)} archivos  ·  {orig_kb} KB → {zip_kb} KB  (−{ratio}%)"
