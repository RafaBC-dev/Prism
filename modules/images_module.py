"""
Images Module — Prism Edition (IA Remove BG + GPU Support)
"""

"""
Módulo de Flujos Gráficos e IA Visual (Images Module)
Hereda de BaseModule.

Esta sección maneja transformaciones matriciales y de deep-learning de imágenes:
- Neural Background Removal (U2NET via Rembg) con pre-caching agresivo para no bloquear interfaz.
- Eliminación de canales Alfa.
- Generación y extracción de paletas HEX/RGB dominantes (K-Means heurístico / Pillow_heif).
- Renderizado de Marcas de Agua (escalado relativo a la resolución del host).
- Conversión universal (WebP, JPG, ICO, PNG) preservando ratio de compresión.

Dependencias:
- Pillow (Pil): Base rotacional y reescalados.
- Rembg/onnxruntime: IA de fondo.
- Pillow_heif: (Fallo silencioso opcional) Para leer fotogramas Apple HEIC.
"""
import customtkinter as ctk
from PIL import Image
import onnxruntime as ort
from tkinter import messagebox, filedialog 

# Importamos las bases y constantes del proyecto
from modules.base_module import (
    BaseModule, BG_DARK, BG_CARD, BG_ITEM,
    ACCENT, ACCENT_H, TEXT_PRI, TEXT_SEC, BORDER, DANGER
)
from core.job_queue import JobStatus
from ui.widgets import DropZone, FileListWidget

# --- CONFIGURACIÓN ---
IMG_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"]

# Lista de herramientas para el Sidebar lateral
TOOLS = [
    ("convert",   "🔄", "Convertir formato"),
    ("resize",    "📐", "Redimensionar"),
    ("compress",  "📦", "Comprimir"),
    ("remove_bg", "🪄", "Eliminar Fondo"), 
    ("to_pdf",    "📄", "Imágenes → PDF"),
    ("from_pdf",  "🖼",  "PDF → Imágenes"),
]

# ── Lógica de IA (Motor) ──────────────────────────────────────────────────────

import threading

# Pre-carga suave en segundo plano para evitar congelar la interfaz 
# pero mantener la IA pre-cachead en RAM para que no haga deadlock en la cola de trabajos.
def _preload_ai():
    try:
        import onnxruntime
        from rembg import remove, new_session
    except:
        pass
threading.Thread(target=_preload_ai, daemon=True).start()

def _get_ai_session():
    import onnxruntime as ort
    from rembg import new_session
    # Leemos de ONNX solo los providers viables para no trabarnos en DLLs rotas
    providers = ort.get_available_providers()
    if 'CUDAExecutionProvider' in providers:
        sel = ['CUDAExecutionProvider']
    elif 'DmlExecutionProvider' in providers:
        sel = ['DmlExecutionProvider']
    else:
        sel = ['CPUExecutionProvider']
    return new_session("u2net", providers=sel)

def _ai_remove_bg_task(input_path: str, output_path: str, progress_cb=None):
    from rembg import remove
    """Tarea principal de eliminación de fondo para la cola de trabajos."""
    try:
        session = _get_ai_session()
        with open(input_path, 'rb') as i:
            input_data = i.read()
            # Ya precargado, instántaneo
            output_data = remove(input_data, session=session)     
        with open(output_path, 'wb') as o:
            o.write(output_data)
        return output_path
    except Exception as e:
        return f"Error IA: {str(e)}"
    

# ── Widget de Vista Previa ───────────────────────────────────────────────────

class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, width=280, corner_radius=0, **kwargs)
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="VISTA PREVIA", font=("Segoe UI", 11, "bold"), 
                     text_color=TEXT_SEC).grid(row=0, column=0, pady=(20, 10))
        
        # Contenedor Original
        self.orig_box = self._create_preview_box("Original", 1)
        self.orig_img_lbl = ctk.CTkLabel(self.orig_box, text="Sin imagen", text_color=TEXT_SEC)
        self.orig_img_lbl.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Contenedor Resultado
        self.res_box = self._create_preview_box("Resultado", 2)
        self.res_img_lbl = ctk.CTkLabel(self.res_box, text="Esperando...", text_color=TEXT_SEC)
        self.res_img_lbl.pack(expand=True, fill="both", padx=5, pady=5)

    def _create_preview_box(self, title, row):
        f = ctk.CTkFrame(self, fg_color=BG_CARD, height=200, corner_radius=8)
        f.grid(row=row, column=0, padx=15, pady=10, sticky="ew")
        f.pack_propagate(False)
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 10), text_color=TEXT_SEC).place(x=10, y=5)
        return f

    def update_previews(self, original_path, result_path=None):
        """Actualiza las miniaturas de las imágenes."""
        for path, lbl in [(original_path, self.orig_img_lbl), (result_path, self.res_img_lbl)]:
            if not path or not os.path.exists(path): continue
            try:
                img = Image.open(path)
                img.thumbnail((250, 180))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                lbl.configure(image=ctk_img, text="")
            except Exception:
                lbl.configure(text="Error carga")


# ── Panel Base para Imágenes ──────────────────────────────────────────────────

class _BaseImgPanel(ctk.CTkFrame):
    title = ""
    description = ""
    multi_file = False
    allowed_exts = IMG_EXTS

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
        ctk.CTkLabel(hdr, text=self.title, font=("Segoe UI", 17, "bold"), text_color=TEXT_PRI).pack(anchor="w")
        ctk.CTkLabel(hdr, text=self.description, font=("Segoe UI", 11), text_color=TEXT_SEC).pack(anchor="w", pady=(2, 0))
        
        self._drop = DropZone(self, on_files=self._on_drop, extensions=self.allowed_exts, height=100)
        self._drop.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 8))
        
        self._file_list = FileListWidget(self)
        self._file_list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self.rowconfigure(2, weight=1)

    def _on_drop(self, paths):
        if not self.multi_file: self._file_list.clear()
        self._file_list.add_files(paths)
        # Al soltar, actualizamos la vista previa del original
        if paths and hasattr(self.master, 'preview'):
            self.master.preview.update_previews(paths[0])

    def _build_options(self): pass

    def _build_run_btn(self):
        self._run_btn = ctk.CTkButton(
            self, text="▶  Ejecutar", height=42, fg_color=ACCENT, hover_color=ACCENT_H,
            font=("Segoe UI", 14, "bold"), corner_radius=10, command=self._run)
        self._run_btn.grid(row=10, column=0, sticky="ew", padx=24, pady=(8, 20))

    def _run(self): raise NotImplementedError

    def _on_done(self, job):
        if job.status == JobStatus.DONE:
            # Si hay un resultado de imagen, lo mostramos en el preview
            if os.path.exists(str(job.result)) and hasattr(self.master, 'preview'):
                self.master.preview.update_previews(self._file_list.paths[0], job.result)
            self.app.after(0, lambda: messagebox.showinfo("Listo", f"Guardado en:\n{job.result}"))
        elif job.status == JobStatus.ERROR:
            self.app.after(0, lambda: messagebox.showerror("Error", job.error))

    def _section(self, text, row=3):
        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 8))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(10, 6), sticky="w")
        return f
    
# ── Herramienta: Eliminar Fondo (IA) ──────────────────────────────────────────

class RemoveBgPanel(_BaseImgPanel):
    title = "Eliminar Fondo (IA)"
    description = "Usa redes neuronales para separar el sujeto del fondo y crear un PNG transparente."

    def _build_options(self):
        f = self._section("Motor de IA")
        ctk.CTkLabel(f, text="Aceleración: Automática (Selección del sistema)", 
                     font=("Segoe UI", 11), text_color=TEXT_SEC).grid(
                     row=1, column=0, padx=14, pady=(0, 2), sticky="w")
        ctk.CTkLabel(f, text="(La 1ª vez descargará los modelos de IA localmente. Puede tardar varios minutos)", 
                     font=("Segoe UI", 10), text_color=ACCENT).grid(
                     row=2, column=0, padx=14, pady=(0, 12), sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        
        # Ahora preguntamos dónde guardar
        out = filedialog.asksaveasfilename(
            title="Guardar imagen sin fondo",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile=os.path.splitext(os.path.basename(paths[0]))[0] + "_no_bg.png"
        )
        if not out: return

        self.app.job_queue.submit(
            f"IA: Procesando {os.path.basename(paths[0])}",
            _ai_remove_bg_task, paths[0], out,
            on_done=self._on_done,
        )


# ── Módulo Principal ──────────────────────────────────────────────────────────

class ImagesModule(BaseModule):
    module_id = "images"

    def __init__(self, master, app, **kwargs):
        super().__init__(master, app, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, minsize=210)
        
        # Layout
        self.columnconfigure(0, weight=0) # Sidebar
        self.columnconfigure(1, weight=0) # Divider
        self.columnconfigure(2, weight=1) # Panel Central 
        self.columnconfigure(3, weight=0) # Divider 2
        self.columnconfigure(4, weight=0) # Preview Sidebar

        self._panels = {}
        self._tool_btns = {}
        self._active_tool = ""
        
        self._build_sidebar()

        # El Panel de Vista Previa
        self.preview = PreviewPanel(self)
        self.preview.grid(row=0, column=4, sticky="ns")

        self._build_panels()
        self._switch_tool("convert")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(sb, text="Herramientas Imagen", font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(18, 10), sticky="w")
        for i, (tid, icon, name) in enumerate(TOOLS):
            btn = ctk.CTkButton(sb, text=f"  {icon}  {name}", anchor="w", fg_color="transparent", 
                                hover_color=BG_ITEM, text_color=TEXT_SEC, font=("Segoe UI", 13), 
                                height=40, corner_radius=8, command=lambda t=tid: self._switch_tool(t))
            btn.grid(row=i+1, column=0, padx=8, pady=2, sticky="ew")
            self._tool_btns[tid] = btn

    def _switch_tool(self, tool_id):
        if self._active_tool:
            self._panels[self._active_tool].grid_remove()
            self._tool_btns[self._active_tool].configure(fg_color="transparent", text_color=TEXT_SEC)
        self._panels[tool_id].grid()
        self._active_tool = tool_id
        self._tool_btns[tool_id].configure(fg_color=BG_ITEM, text_color=TEXT_PRI)

    def _build_panels(self):
        builders = {
            "convert":   ConvertPanel, 
            "resize":    ResizePanel,
            "compress":  CompressPanel,
            "remove_bg": RemoveBgPanel,
            "to_pdf":    ToPdfPanel,
            "from_pdf":  FromPdfPanel,
        }
        for tid, cls in builders.items():
            panel = cls(self, app=self.app)
            panel.grid(row=0, column=2, sticky="nsew") # Pegado al centro expandible
            panel.grid_remove()
            self._panels[tid] = panel
        
# ── Convertir formato ─────────────────────────────────────────────────────────

class ConvertPanel(_BaseImgPanel):
    title = "Convertir formato"
    description = "Convierte imágenes entre PNG, JPG, WEBP, BMP, TIFF y GIF."
    multi_file = True

    def _build_options(self):
        f = self._section("Formato de salida")
        self._fmt = ctk.CTkSegmentedButton(
            f, values=["PNG", "JPG", "WEBP", "BMP", "TIFF", "ICO"],
            font=("Segoe UI", 12))
        self._fmt.set("PNG")
        self._fmt.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        row_q = ctk.CTkFrame(f, fg_color="transparent")
        row_q.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="w")
        ctk.CTkLabel(row_q, text="Calidad JPG/WEBP:",
                     font=("Segoe UI", 11), text_color=TEXT_SEC).pack(side="left")
        self._quality_val = ctk.CTkLabel(row_q, text="85",
                                          font=("Segoe UI", 11), text_color=TEXT_PRI, width=30)
        self._quality_val.pack(side="right", padx=(8, 0))
        self._quality = ctk.CTkSlider(row_q, from_=10, to=100, number_of_steps=18,
                                       width=160, command=self._update_q)
        self._quality.set(85)
        self._quality.pack(side="left", padx=8)

    def _update_q(self, val):
        self._quality_val.configure(text=str(int(val)))

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivos", "Añade imágenes."); return
        fmt = self._fmt.get().lower()
        quality = int(self._quality.get())
        if len(paths) == 1:
            ext = ".jpg" if fmt == "jpg" else f".{fmt}"
            out = filedialog.asksaveasfilename(
                title="Guardar imagen",
                defaultextension=ext,
                filetypes=[(fmt.upper(), f"*{ext}")],
                initialfile=os.path.splitext(os.path.basename(paths[0]))[0] + ext)
            if not out: return
            self.app.job_queue.submit(
                f"Convertir → {fmt.upper()}",
                _convert_single, paths[0], out, fmt, quality,
                on_done=self._on_done)
        else:
            out_dir = filedialog.askdirectory(title="Carpeta de salida")
            if not out_dir: return
            self.app.job_queue.submit(
                f"Convertir {len(paths)} imágenes → {fmt.upper()}",
                _convert_batch, paths, out_dir, fmt, quality,
                on_done=self._on_done)


# ── Redimensionar ─────────────────────────────────────────────────────────────

class ResizePanel(_BaseImgPanel):
    title = "Redimensionar"
    description = "Cambia el tamaño manteniendo la proporción."
    multi_file = True

    def _build_options(self):
        f = self._section("Modo")
        f.columnconfigure(0, weight=1)

        self._mode = ctk.StringVar(value="percent")
        ctk.CTkRadioButton(f, text="Por porcentaje", variable=self._mode,
                           value="percent", text_color=TEXT_PRI,
                           command=self._toggle_mode).grid(
                           row=1, column=0, padx=14, pady=(0, 4), sticky="w")
        ctk.CTkRadioButton(f, text="Por píxeles (ancho)", variable=self._mode,
                           value="pixels", text_color=TEXT_PRI,
                           command=self._toggle_mode).grid(
                           row=2, column=0, padx=14, pady=(0, 10), sticky="w")

        row_v = ctk.CTkFrame(f, fg_color="transparent")
        row_v.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="w")
        self._val_label = ctk.CTkLabel(row_v, text="Porcentaje:",
                                        font=("Segoe UI", 12), text_color=TEXT_PRI)
        self._val_label.pack(side="left")
        self._val_entry = ctk.CTkEntry(row_v, width=72, height=30,
                                        placeholder_text="50", font=("Segoe UI", 12))
        self._val_entry.pack(side="left", padx=8)
        ctk.CTkCheckBox(f, text="Mantener relación de aspecto",
                        text_color=TEXT_PRI, font=("Segoe UI", 11),
                        variable=ctk.BooleanVar(value=True)).grid(
                        row=4, column=0, padx=14, pady=(0, 12), sticky="w")

    def _toggle_mode(self):
        if self._mode.get() == "percent":
            self._val_label.configure(text="Porcentaje:")
            self._val_entry.configure(placeholder_text="50")
        else:
            self._val_label.configure(text="Ancho (px):")
            self._val_entry.configure(placeholder_text="1280")

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivos", "Añade imágenes."); return
        try:
            val = float(self._val_entry.get())
            assert val > 0
        except Exception:
            messagebox.showerror("Valor inválido", "Introduce un número válido."); return

        mode = self._mode.get()
        if len(paths) == 1:
            src = paths[0]
            ext = os.path.splitext(src)[1]
            out = filedialog.asksaveasfilename(
                title="Guardar imagen", defaultextension=ext,
                filetypes=[("Imagen", f"*{ext}")],
                initialfile=os.path.splitext(os.path.basename(src))[0] + "_resized" + ext)
            if not out: return
            self.app.job_queue.submit(
                f"Redimensionar {os.path.basename(src)}",
                _resize_single, src, out, mode, val,
                on_done=self._on_done)
        else:
            out_dir = filedialog.askdirectory(title="Carpeta de salida")
            if not out_dir: return
            self.app.job_queue.submit(
                f"Redimensionar {len(paths)} imágenes",
                _resize_batch, paths, out_dir, mode, val,
                on_done=self._on_done)


# ── Comprimir ─────────────────────────────────────────────────────────────────

class CompressPanel(_BaseImgPanel):
    title = "Comprimir imágenes"
    description = "Reduce el peso del archivo ajustando la calidad."
    multi_file = True

    def _build_options(self):
        f = self._section("Calidad de salida")
        f.columnconfigure(0, weight=1)

        row_q = ctk.CTkFrame(f, fg_color="transparent")
        row_q.grid(row=1, column=0, padx=14, pady=(10, 12), sticky="ew")

        ctk.CTkLabel(row_q, text="Calidad:", font=("Segoe UI", 12),
                     text_color=TEXT_PRI).pack(side="left")

        self._q = ctk.CTkSlider(row_q, from_=10, to=95, number_of_steps=17, width=150,
                                command=lambda v: self._q_lbl.configure(text=str(int(v))))
        self._q.set(75)
        self._q.pack(side="left", padx=8)

        self._q_lbl = ctk.CTkLabel(row_q, text="75", font=("Segoe UI", 12, "bold"),
                                   text_color=TEXT_PRI, width=25)
        self._q_lbl.pack(side="left")

        ctk.CTkLabel(row_q, text="(Menor valor = más compresión y menos peso)",
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack(side="left", padx=(15, 0))

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivos", "Añade imágenes."); return
        quality = int(self._q.get())
        if len(paths) == 1:
            src = paths[0]
            ext = os.path.splitext(src)[1]
            out = filedialog.asksaveasfilename(
                title="Guardar imagen comprimida", defaultextension=ext,
                filetypes=[("Imagen", f"*{ext}")],
                initialfile=os.path.splitext(os.path.basename(src))[0] + "_compressed" + ext)
            if not out: return
            self.app.job_queue.submit(
                f"Comprimir {os.path.basename(src)}",
                _compress_single, src, out, quality,
                on_done=self._on_done)
        else:
            out_dir = filedialog.askdirectory(title="Carpeta de salida")
            if not out_dir: return
            self.app.job_queue.submit(
                f"Comprimir {len(paths)} imágenes",
                _compress_batch, paths, out_dir, quality,
                on_done=self._on_done)


# ── Imágenes → PDF ────────────────────────────────────────────────────────────

class ToPdfPanel(_BaseImgPanel):
    title = "Imágenes → PDF"
    description = "Combina una o varias imágenes en un PDF."
    multi_file = True

    def _build_options(self):
        f = self._section("Tamaño de página")

        row_opts = ctk.CTkFrame(f, fg_color="transparent")
        row_opts.grid(row=1, column=0, padx=14, pady=(5, 12), sticky="w")

        self._page_size = ctk.CTkSegmentedButton(
            row_opts, values=["A4", "A3", "Letter", "Original"],
            font=("Segoe UI", 12))
        self._page_size.set("A4")
        self._page_size.pack(side="left")

        ctk.CTkLabel(row_opts, text="'Original' usa el tamaño exacto de la imagen.",
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack(side="left", padx=(15, 0))

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivos", "Añade imágenes."); return
        out = filedialog.asksaveasfilename(
            title="Guardar PDF", defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], initialfile="imagenes.pdf")
        if not out: return
        page_size = self._page_size.get()
        self.app.job_queue.submit(
            f"Imágenes → PDF ({len(paths)} imgs)",
            _images_to_pdf, paths, out, page_size,
            on_done=self._on_done)


# ── PDF → Imágenes ────────────────────────────────────────────────────────────

class FromPdfPanel(_BaseImgPanel):
    title = "PDF → Imágenes"
    description = "Exporta cada página de un PDF como imagen."
    allowed_exts = [".pdf"]

    def _build_options(self):
        f = self._section("Opciones de exportación")
        f.columnconfigure(0, weight=1)

        row_fmt = ctk.CTkFrame(f, fg_color="transparent")
        row_fmt.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")
        ctk.CTkLabel(row_fmt, text="Formato:", font=("Segoe UI", 12),
                     text_color=TEXT_PRI).pack(side="left")
        self._fmt = ctk.CTkSegmentedButton(row_fmt, values=["PNG", "JPG", "WEBP"],
                                            font=("Segoe UI", 12))
        self._fmt.set("PNG")
        self._fmt.pack(side="left", padx=8)

        row_dpi = ctk.CTkFrame(f, fg_color="transparent")
        row_dpi.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="w")
        ctk.CTkLabel(row_dpi, text="DPI:", font=("Segoe UI", 12),
                     text_color=TEXT_PRI).pack(side="left")
        self._dpi = ctk.CTkSegmentedButton(row_dpi, values=["72", "150", "300"],
                                            font=("Segoe UI", 12))
        self._dpi.set("150")
        self._dpi.pack(side="left", padx=8)
        ctk.CTkLabel(row_dpi, text="(mayor DPI = mejor calidad, más peso)",
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack(side="left", padx=4)

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivo", "Añade un PDF."); return
        out_dir = filedialog.askdirectory(title="Carpeta de salida")
        if not out_dir: return
        fmt = self._fmt.get().lower()
        dpi = int(self._dpi.get())
        self.app.job_queue.submit(
            f"PDF → Imágenes: {os.path.basename(paths[0])}",
            _pdf_to_images, paths[0], out_dir, fmt, dpi,
            on_done=self._on_done)


# ══════════════════════════════════════════════════════════════════════════════
# Funciones de operación
# ══════════════════════════════════════════════════════════════════════════════

def _save_img(img, path: str, fmt: str, quality: int):
    """Guarda imagen normalizando el formato y alpha channel."""
    
    fmt = fmt.lower()
    
    if fmt == "jpg":
        fmt = "jpeg"
        
    # JPEG/BMP no soportan alpha
    if fmt in ("jpeg", "bmp") and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
        
    # ICO funciona mejor con canal alpha para las transparencias
    if fmt == "ico" and img.mode != "RGBA":
        img = img.convert("RGBA")
        
    save_kwargs = {}
    
    if fmt in ("jpeg", "webp"):
        save_kwargs["quality"] = quality
    if fmt == "png":
        save_kwargs["optimize"] = True
    if fmt == "ico":
        # Empaquetamos los tamaños estándar de Windows en el mismo archivo
        save_kwargs["sizes"] = [(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]
        
    img.save(path, format=fmt.upper(), **save_kwargs)

# ── Convertir ─────────────────────────────────────────────────────────────────

def _convert_single(src: str, out: str, fmt: str, quality: int, progress_cb=None) -> str:
    
    img = Image.open(src)
    _save_img(img, out, fmt, quality)
    if progress_cb: progress_cb(1.0)
    return out


def _convert_batch(paths: list, out_dir: str, fmt: str, quality: int, progress_cb=None) -> str:
    
    ext = ".jpg" if fmt == "jpg" else f".{fmt}"
    for i, src in enumerate(paths):
        img = Image.open(src)
        stem = os.path.splitext(os.path.basename(src))[0]
        out = os.path.join(out_dir, stem + ext)
        _save_img(img, out, fmt, quality)
        if progress_cb: progress_cb((i + 1) / len(paths))
    return f"{len(paths)} imágenes en:\n{out_dir}"


# ── Redimensionar ─────────────────────────────────────────────────────────────

def _calc_size(orig_w, orig_h, mode: str, val: float):
    if mode == "percent":
        factor = val / 100.0
        return max(1, int(orig_w * factor)), max(1, int(orig_h * factor))
    else:  # pixels = ancho fijo, alto proporcional
        new_w = int(val)
        new_h = max(1, int(orig_h * (new_w / orig_w)))
        return new_w, new_h


def _resize_single(src: str, out: str, mode: str, val: float, progress_cb=None) -> str:
    
    img = Image.open(src)
    new_w, new_h = _calc_size(img.width, img.height, mode, val)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    ext = os.path.splitext(out)[1].lstrip(".")
    _save_img(img, out, ext, 90)
    if progress_cb: progress_cb(1.0)
    return f"{out}\n\n{img.width}×{img.height} px"


def _resize_batch(paths: list, out_dir: str, mode: str, val: float, progress_cb=None) -> str:
    
    for i, src in enumerate(paths):
        img = Image.open(src)
        new_w, new_h = _calc_size(img.width, img.height, mode, val)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        stem = os.path.splitext(os.path.basename(src))[0]
        ext = os.path.splitext(src)[1].lstrip(".")
        out = os.path.join(out_dir, stem + "_resized." + ext)
        _save_img(img, out, ext, 90)
        if progress_cb: progress_cb((i + 1) / len(paths))
    return f"{len(paths)} imágenes en:\n{out_dir}"


# ── Comprimir ─────────────────────────────────────────────────────────────────

def _compress_single(src: str, out: str, quality: int, progress_cb=None) -> str:
    
    img = Image.open(src)
    ext = os.path.splitext(out)[1].lstrip(".")
    _save_img(img, out, ext, quality)
    orig = os.path.getsize(src) // 1024
    new  = os.path.getsize(out) // 1024
    if progress_cb: progress_cb(1.0)
    return f"{out}\n\nOriginal: {orig} KB  →  Resultado: {new} KB  (−{max(0, orig-new)} KB)"


def _compress_batch(paths: list, out_dir: str, quality: int, progress_cb=None) -> str:
    
    total_saved = 0
    for i, src in enumerate(paths):
        img = Image.open(src)
        stem = os.path.splitext(os.path.basename(src))[0]
        ext  = os.path.splitext(src)[1].lstrip(".")
        out  = os.path.join(out_dir, stem + "_compressed." + ext)
        _save_img(img, out, ext, quality)
        total_saved += max(0, os.path.getsize(src) - os.path.getsize(out))
        if progress_cb: progress_cb((i + 1) / len(paths))
    saved_kb = total_saved // 1024
    return f"{len(paths)} imágenes en:\n{out_dir}\n\nAhorro total: {saved_kb} KB"


# ── Imágenes → PDF ────────────────────────────────────────────────────────────

PAGE_SIZES = {
    "A4":     (595, 842),
    "A3":     (842, 1191),
    "Letter": (612, 792),
}


def _images_to_pdf(paths: list, output: str, page_size_name: str, progress_cb=None) -> str:
    from reportlab.lib.pagesizes import portrait
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader  # <-- ESTO ERA LO QUE FALTABA
    from pypdf import PdfReader
    
    try:
        from pypdf import PdfWriter
        import io
    except ImportError:
        raise RuntimeError("Instala pypdf: pip install pypdf")

    writer = PdfWriter()

    for i, src in enumerate(paths):
        img = Image.open(src).convert("RGB")

        if page_size_name == "Original":
            pw, ph = img.width, img.height
        else:
            pw, ph = PAGE_SIZES.get(page_size_name, (595, 842))
            scale = min(pw / img.width, ph / img.height)
            new_w, new_h = int(img.width * scale), int(img.height * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(pw, ph))
        img_buf = io.BytesIO()
        img.save(img_buf, format="JPEG", quality=92)
        img_buf.seek(0)

        x_off, y_off = (pw - img.width) / 2, (ph - img.height) / 2
        
        # Envolvemos el BytesIO en un ImageReader para que ReportLab no se queje
        img_reader = ImageReader(img_buf)
        c.drawImage(img_reader, x_off, y_off, width=img.width, height=img.height)
        
        c.save()
        buf.seek(0)
        
        page_reader = PdfReader(buf)
        writer.add_page(page_reader.pages[0])
        if progress_cb: progress_cb((i + 1) / len(paths))

    with open(output, "wb") as f:
        writer.write(f)
    return f"{output}\n\n{len(paths)} página(s)"


# ── PDF → Imágenes ────────────────────────────────────────────────────────────

def _pdf_to_images(path: str, out_dir: str, fmt: str, dpi: int, progress_cb=None) -> str:
    """Convierte PDF a imágenes usando PyMuPDF (nativo, rápido, sin Poppler)."""
    import fitz  # PyMuPDF
    import io
    from PIL import Image

    try:
        stem = os.path.splitext(os.path.basename(path))[0]
        # Abrimos el PDF directamente (a fitz le dan igual las tildes en la ruta)
        doc = fitz.open(path)
        
        # El DPI estándar de PDF es 72. Calculamos el factor de zoom.
        # DPI 72 = Zoom 1.0 | DPI 150 = Zoom ~2.08 | DPI 300 = Zoom ~4.16
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        total_pages = len(doc)
        
        for i in range(total_pages):
            page = doc.load_page(i)
            # Renderizamos la página a una imagen cruda (pixmap) con el zoom aplicado
            pix = page.get_pixmap(matrix=mat)
            
            # Definimos la ruta de salida
            out_path = os.path.join(out_dir, f"{stem}_p{i + 1:04d}.{fmt}")
            
            # Convertimos el pixmap a bytes PNG (formato intermedio sin pérdida)
            img_data = pix.tobytes("png")
            
            # Usamos PIL para abrir esos bytes y guardarlo con tu formateador estándar (_save_img)
            # Esto asegura que se aplique la compresión/calidad que eligió el usuario en la interfaz.
            with Image.open(io.BytesIO(img_data)) as img:
                # _save_img es tu función auxiliar que ya maneja JPG/PNG/WEBP
                _save_img(img, out_path, fmt, 92)
            
            # Actualizamos progreso
            if progress_cb: progress_cb((i + 1) / total_pages)
            
        doc.close()
        return f"Conversión exitosa.\n{total_pages} imágenes guardadas en:\n{out_dir}"
        
    except Exception as e:
        return f"Error crítico en la conversión de PDF: {str(e)}"


