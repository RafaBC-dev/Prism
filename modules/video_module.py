"""
Video Module — Prism (Layout 3 Columnas + Info Técnica)
"""

import os
import subprocess
import json
import shutil
from tkinter import filedialog, messagebox
import customtkinter as ctk

from modules.base_module import (
    BaseModule, BG_DARK, BG_CARD, BG_ITEM,
    ACCENT, ACCENT_H, TEXT_PRI, TEXT_SEC, BORDER
)
from core.job_queue import JobStatus
from ui.widgets import DropZone, FileListWidget

# --- CONFIGURACIÓN ---
VIDEO_EXTS = [".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".m4v"]

TOOLS = [
    ("convert",   "🎬", "Convertir y Escalar"),
    ("audio",     "🔊", "Normalizar Audio"),
    ("subs",      "💬", "Pegar Subtítulos"),
    ("gif",       "🎞️", "Vídeo a GIF "), 
]
# ── Widget de Vista Previa Técnica ──────────────────────────────────────────

class VideoPreviewPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, width=280, corner_radius=0, **kwargs)
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

        # ─── CAJA 1: ORIGINAL ───
        ctk.CTkLabel(self, text="ARCHIVO ORIGINAL", font=("Segoe UI", 11, "bold"), 
                     text_color=TEXT_SEC).grid(row=0, column=0, pady=(20, 5))
        
        self.info_before = ctk.CTkTextbox(self, fg_color=BG_CARD, corner_radius=10,
                                          font=("Consolas", 11), text_color=TEXT_PRI,
                                          border_width=1, border_color=BORDER)
        self.info_before.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.info_before.insert("0.0", "Arrastra un vídeo...")
        self.info_before.configure(state="disabled")

        # ─── CAJA 2: RESULTADO ───
        ctk.CTkLabel(self, text="RESULTADO", font=("Segoe UI", 11, "bold"), 
                     text_color=TEXT_SEC).grid(row=2, column=0, pady=(10, 5))
        
        self.info_after = ctk.CTkTextbox(self, fg_color=BG_CARD, corner_radius=10,
                                         font=("Consolas", 11), text_color=TEXT_PRI,
                                         border_width=1, border_color=BORDER)
        self.info_after.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 20))
        self.info_after.insert("0.0", "Esperando ejecución...")
        self.info_after.configure(state="disabled")

    def _get_video_specs(self, path):
        """Helper centralizado para sacar la ficha técnica de un vídeo con ffprobe."""
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path]
            raw = subprocess.check_output(cmd, text=True)
            data = json.loads(raw)
            
            fmt = data.get("format", {})
            v_stream = next((s for s in data.get("streams", []) if s['codec_type'] == 'video'), {})
            
            size_mb = int(fmt.get('size', 0)) / (1024*1024)
            
            return [
                f"Archivo: {os.path.basename(path)}",
                f"Tamaño:  {size_mb:.2f} MB",
                f"Durac.:  {float(fmt.get('duration', 0)):.1f}s",
                f"",
                f"Codec:   {v_stream.get('codec_name', '?')}",
                f"Res:     {v_stream.get('width')}x{v_stream.get('height')}",
                f"FPS:     {v_stream.get('r_frame_rate')}"
            ]
        except Exception:
            return None

    def update_info(self, path):
        """Actualiza la caja superior con el archivo original."""
        if not path or not os.path.exists(path): return
        
        lines = self._get_video_specs(path)
        self.info_before.configure(state="normal")
        self.info_before.delete("1.0", "end")
        
        if lines:
            self.info_before.insert("1.0", "\n".join(lines))
        else:
            self.info_before.insert("1.0", "No se pudo analizar el archivo original.")
            
        self.info_before.configure(state="disabled")
        self.update_result("Esperando ejecución...")

    def update_result(self, text):
        """Actualiza la caja inferior. Si el texto es una ruta, extrae sus datos."""
        self.info_after.configure(state="normal")
        self.info_after.delete("1.0", "end")
        
        # Magia: Si el texto que recibe es una ruta de archivo válida, le sacamos la ficha técnica
        if os.path.isfile(text):
            lines = self._get_video_specs(text)
            if lines:
                self.info_after.insert("1.0", "\n".join(lines))
            else:
                self.info_after.insert("1.0", f"Guardado en:\n{text}")
        else:
            # Si no es un archivo (ej: un mensaje de error o aviso), lo imprime normal
            self.info_after.insert("1.0", text)
            
        self.info_after.configure(state="disabled")

# ── Panel base ────────────────────────────────────────────────────────────────

class _BaseVideoPanel(ctk.CTkFrame):
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
        ctk.CTkLabel(hdr, text=self.title, font=("Segoe UI", 17, "bold"), text_color=TEXT_PRI).pack(anchor="w")
        ctk.CTkLabel(hdr, text=self.description, font=("Segoe UI", 11), text_color=TEXT_SEC).pack(anchor="w", pady=(2, 0))

        self._drop = DropZone(self, on_files=self._on_drop, extensions=VIDEO_EXTS, height=100)
        self._drop.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 8))

        self._file_list = FileListWidget(self)
        self._file_list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self.rowconfigure(2, weight=1)

    def _on_drop(self, paths):
        if not self.multi_file: self._file_list.clear()
        self._file_list.add_files(paths)
        # Actualizar Preview automáticamente
        if paths and hasattr(self.master, 'preview'):
            self.master.preview.update_info(paths[0])

    def _build_options(self): pass

    def _build_run_btn(self):
        self._run_btn = ctk.CTkButton(self, text="▶  Ejecutar", height=42, fg_color=ACCENT, 
                                      hover_color=ACCENT_H, font=("Segoe UI", 14, "bold"),
                                      corner_radius=10, command=self._run)
        self._run_btn.grid(row=10, column=0, sticky="ew", padx=24, pady=(8, 20))

    def _on_done(self, job):
        if job.status == JobStatus.DONE:
            # 1. Enviar el texto de resultado al panel de la derecha
            if hasattr(self.master, 'preview'):
                self.master.preview.update_result(job.result)
            
            # 2. Mostrar la ventana emergente habitual
            messagebox.showinfo("Listo", f"Completado:\n\n{job.result}")
            
        elif job.status == JobStatus.ERROR:
            if hasattr(self.master, 'preview'):
                self.master.preview.update_result(f"Error:\n{job.error}")
            messagebox.showerror("Error", job.error)

    def _section(self, text, row=3):
        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 10))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(10, 6), sticky="w")
        return f

# ── Herramientas Específicas ──────────────────────────────────────────────────

class ConvertPanel(_BaseVideoPanel):
    title = "Convertir vídeo"
    description = "Cambia el formato y ajusta la calidad usando hardware de vídeo."
    multi_file = True

    def _build_options(self):
        f = self._section("Ajustes")
        self._fmt = ctk.CTkSegmentedButton(f, values=["MP4", "MKV", "MOV", "WEBM"])
        self._fmt.set("MP4")
        self._fmt.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")
        
        self._quality = ctk.CTkSegmentedButton(f, values=["Alta", "Normal", "Baja"])
        self._quality.set("Normal")
        self._quality.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        
        gpu_codec = self.app.backend.gpu_codec if self.app.backend else "libx264"
        fmt = self._fmt.get().lower()
        crf = {"Alta": "18", "Normal": "23", "Baja": "28"}[self._quality.get()]
        
        if len(paths) == 1:
            out = filedialog.asksaveasfilename(defaultextension=f".{fmt}", initialfile="convertido."+fmt)
            if not out: return
            self.app.job_queue.submit(f"Vídeo: Convertir {os.path.basename(paths[0])}",
                                      _convert_single_video, paths[0], out, fmt, crf, gpu_codec,
                                      on_done=self._on_done)
        else:
            out_dir = filedialog.askdirectory()
            if not out_dir: return
            self.app.job_queue.submit(f"Vídeo: Batch {len(paths)} archivos",
                                      _convert_batch_video, paths, out_dir, fmt, crf, gpu_codec,
                                      on_done=self._on_done)

class CompressPanel(_BaseVideoPanel):
    title = "Comprimir vídeo"
    description = "Reduce el peso del vídeo optimizando el bitrate."

    def _build_options(self):
        f = self._section("Nivel de compresión")
        
        # Sub-contenedor agrupado a la izquierda
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.grid(row=1, column=0, padx=14, pady=(5, 15), sticky="w")
        
        # Etiqueta de porcentaje
        self._pct_label = ctk.CTkLabel(opts, text="50%", font=("Segoe UI", 12, "bold"), text_color=ACCENT)
        self._pct_label.grid(row=0, column=0, pady=(0, 5), sticky="w")

        # Slider con anchura fija para que no se encoja
        self._crf = ctk.CTkSlider(opts, from_=18, to=32, number_of_steps=14, command=self._update_label, width=350)
        self._crf.set(26)
        self._crf.grid(row=1, column=0, pady=(0, 5), sticky="w")

    def _update_label(self, val):
        # Mapeo directo: 18 (0%) a 32 (100%)
        pct = int(((val - 18) / (32 - 18)) * 100)
        self._pct_label.configure(text=f"{pct}%")

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        gpu_codec = self.app.backend.gpu_codec if self.app.backend else "libx264"
        crf = str(int(self._crf.get()))
        out = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile="comprimido.mp4")
        if not out: return
        self.app.job_queue.submit(f"Vídeo: Comprimiendo {os.path.basename(paths[0])}",
                                  _compress_video, paths[0], out, crf, gpu_codec,
                                  on_done=self._on_done)

class VideoSubsPanel(_BaseVideoPanel):
    title = "Incrustar Subtítulos"
    description = "Pega un archivo .srt permanentemente en el vídeo."

    def _build_options(self):
        f = self._section("Archivo de Subtítulos")
        self._srt_path = ctk.StringVar(value="No seleccionado...")
        lbl = ctk.CTkLabel(f, textvariable=self._srt_path, font=("Segoe UI", 11), text_color=ACCENT)
        lbl.grid(row=1, column=0, padx=14, pady=(0, 5), sticky="w")
        
        btn = ctk.CTkButton(f, text="Seleccionar .srt", height=28, 
                           command=lambda: self._srt_path.set(filedialog.askopenfilename(filetypes=[("Subtítulos", "*.srt")]) or "No seleccionado..."))
        btn.grid(row=2, column=0, padx=14, pady=(0, 15), sticky="w")

    def _run(self):
        path = self._file_list.paths[0] if self._file_list.paths else None
        srt = self._srt_path.get()
        if not path or srt == "No seleccionado...": return
        
        out = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile="con_subtitulos.mp4")
        if not out: return

        self.app.job_queue.submit(f"Incrustando subs", 
                                 _video_task, path, out, "subs", {"srt_path": srt},
                                 on_done=self._on_done)
        

# ── Módulo Principal ──────────────────────────────────────────────────────────

class VideoModule(BaseModule):
    module_id = "video"

    def __init__(self, master, app, **kwargs):
        super().__init__(master, app, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, minsize=210)
        
        # Layout
        self.columnconfigure(0, weight=0) # Sidebar
        self.columnconfigure(1, weight=0) # Div
        self.columnconfigure(2, weight=1) # HERRAMIENTAS 
        self.columnconfigure(3, weight=0) # Div
        self.columnconfigure(4, weight=0) # Preview

        self._panels = {}
        self._tool_btns = {}
        self._active_tool = ""
        
        self._build_sidebar()
        
        self.preview = VideoPreviewPanel(self)
        self.preview.grid(row=0, column=4, sticky="ns")

        self._build_panels()
        self._switch_tool("convert")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(sb, text="Herramientas Vídeo", font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(18, 10), sticky="w")
        for i, (tid, icon, name) in enumerate(TOOLS):
            btn = ctk.CTkButton(sb, text=f"  {icon} {name}", anchor="w", fg_color="transparent", 
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
            "audio": VideoAudioPanel,
            "subs":      VideoSubsPanel,
            "gif":       GifPanel  # <--- Lo reconectamos aquí
        }
        for tid, cls in builders.items():
            panel = cls(self, app=self.app)
            panel.grid(row=0, column=2, sticky="nsew")
            panel.grid_remove()
            self._panels[tid] = panel


class VideoAudioPanel(_BaseVideoPanel):
    title = "Normalización de Audio Profesional"
    description = "Ajusta el volumen al estándar EBU R128 (ideal para YouTube/TV)."

    def _build_options(self):
        f = self._section("Info de Audio")
        info = ("Aplica un filtro 'Loudnorm' para evitar saltos de volumen.\n"
                "El vídeo no se recodifica (es rápido), solo el audio.")
        ctk.CTkLabel(f, text=info, font=("Segoe UI", 11), text_color=TEXT_SEC, justify="left").grid(row=1, column=0, padx=14, pady=(0,15))

    def _run(self):
        path = self._file_list.paths[0] if self._file_list.paths else None
        if not path: return
        
        out = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile="audio_normalizado.mp4")
        if not out: return

        self.app.job_queue.submit(
            f"Normalizando: {os.path.basename(path)}",
            _video_task, path, out, mode="audio",
            on_done=self._on_done
        )


    # ── Panel: Recortar Vídeo ─────────────────────────────────────────────────────

class CutPanel(_BaseVideoPanel):
    title = "Recortar vídeo"
    description = "Extrae un fragmento sin perder calidad (Stream Copy)."

    def _build_options(self):
        f = self._section("Tiempos (hh:mm:ss)")
        
        # Sub-contenedor agrupado a la izquierda
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.grid(row=1, column=0, padx=14, pady=(5, 15), sticky="w")
        
        # Fila 0: Inicio
        ctk.CTkLabel(opts, text="Inicio:", font=("Segoe UI", 12)).grid(row=0, column=0, pady=5, sticky="w")
        self._start = ctk.CTkEntry(opts, placeholder_text="00:00:00", width=100)
        self._start.grid(row=0, column=1, padx=(15, 0), pady=5, sticky="w")

        # Fila 1: Fin
        ctk.CTkLabel(opts, text="Fin:", font=("Segoe UI", 12)).grid(row=1, column=0, pady=5, sticky="w")
        self._end = ctk.CTkEntry(opts, placeholder_text="00:00:10", width=100)
        self._end.grid(row=1, column=1, padx=(15, 0), pady=5, sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        
        start = self._start.get() or "00:00:00"
        end = self._end.get()
        if not end:
            messagebox.showwarning("Faltan datos", "Indica el tiempo de fin.")
            return

        out = filedialog.asksaveasfilename(defaultextension=".mp4", initialfile="recorte.mp4")
        if not out: return

        self.app.job_queue.submit(
            f"Vídeo: Recortando {os.path.basename(paths[0])}",
            _cut_video_task, paths[0], out, start, end,
            on_done=self._on_done
        )

# ── Panel: Vídeo a GIF ────────────────────────────────────────────────────────

class GifPanel(_BaseVideoPanel):
    title = "Convertir a GIF"
    description = "Crea una animación optimizada a partir de un fragmento."

    def _build_options(self):
        f = self._section("Ajustes del GIF")
        
        # Sub-contenedor alineado a la izquierda para mantener todo el bloque unido
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.grid(row=1, column=0, padx=14, pady=(5, 15), sticky="w")

        # Fila 0: FPS
        ctk.CTkLabel(opts, text="FPS (Fluidez):", font=("Segoe UI", 12)).grid(row=0, column=0, pady=5, sticky="w")
        self._fps = ctk.CTkSegmentedButton(opts, values=["10", "15", "24"])
        self._fps.set("15")
        self._fps.grid(row=0, column=1, padx=(15, 0), pady=5, sticky="w")

        # Fila 1: Ancho
        ctk.CTkLabel(opts, text="Ancho (px):", font=("Segoe UI", 12)).grid(row=1, column=0, pady=5, sticky="w")
        self._width = ctk.CTkEntry(opts, placeholder_text="480", width=80)
        self._width.insert(0, "480")
        self._width.grid(row=1, column=1, padx=(15, 0), pady=5, sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths: return
        
        fps = self._fps.get()
        width = self._width.get()
        out = filedialog.asksaveasfilename(defaultextension=".gif", initialfile="animacion.gif")
        if not out: return

        self.app.job_queue.submit(
            f"Vídeo: Generando GIF",
            _video_to_gif_task, paths[0], out, fps, width,
            on_done=self._on_done
        )

# ── Tareas de FFmpeg ───────────────

def _run_ffmpeg(args):
    subprocess.run(["ffmpeg", "-y"] + args, check=True, capture_output=True)

def _cut_video_task(path, out, start, end, progress_cb=None):
    """Corta vídeo instantáneamente usando 'copy' para no recodificar."""
    try:
        # Usamos -ss ANTES de -i para que sea mucho más rápido en archivos grandes
        args = ["ffmpeg", "-ss", start, "-to", end, "-i", path, "-c", "copy", "-y", out]
        subprocess.run(args, check=True, capture_output=True)
        return out
    except Exception as e:
        return f"Error al recortar: {str(e)}"

def _video_to_gif_task(path, out, fps, width, progress_cb=None):
    """Genera un GIF de alta calidad usando una paleta de colores optimizada."""
    try:
        # Paso 1: Generar paleta de colores para que el GIF no se vea con manchas
        palette = "palette.png"
        filters = f"fps={fps},scale={width}:-1:flags=lanczos"
        subprocess.run(["ffmpeg", "-i", path, "-vf", f"{filters},palettegen", "-y", palette], check=True)
        
        # Paso 2: Crear el GIF usando la paleta
        subprocess.run(["ffmpeg", "-i", path, "-i", palette, "-filter_complex", f"{filters}[x];[x][1:v]paletteuse", "-y", out], check=True)
        
        if os.path.exists(palette): os.remove(palette)
        return out
    except Exception as e:
        return f"Error al crear GIF: {str(e)}"
    
def _video_task(input_path: str, output_path: str, mode="convert", params=None, progress_cb=None):
    """Motor FFmpeg para reescalado, normalización y subtítulos."""
    try:
        # Buscamos el ejecutable de FFmpeg en tu carpeta core o sistema
        ffmpeg_exe = r"ffmpeg\bin\ffmpeg.exe" # Ajusta a tu ruta real
        
        cmd = [ffmpeg_exe, "-i", input_path]

        # --- MODO 1: CONVERTIR Y ESCALAR (Ej: 4K a 1080p) ---
        if mode == "convert":
            scale = params.get("scale", "1920:-1") # Por defecto 1080p
            cmd += ["-vf", f"scale={scale}", "-c:v", "libx264", "-crf", "23", "-preset", "veryfast"]

        # --- MODO 2: NORMALIZACIÓN DE AUDIO (Estándar EBU R128) ---
        elif mode == "audio":
            # Esto iguala el volumen de todos tus vídeos para que suenen igual de fuerte
            cmd += ["-af", "loudnorm=I=-23:LRA=7:tp=-2", "-c:v", "copy", "-c:a", "aac"]

        # --- MODO 3: INCRUSTAR SUBTÍTULOS (.srt a .mp4) ---
        elif mode == "subs":
            srt_path = params.get("srt_path")
            # Importante: FFmpeg requiere escapar las rutas en el filtro de subtítulos
            clean_srt = srt_path.replace("\\", "/").replace(":", "\\:")
            cmd += ["-vf", f"subtitles='{clean_srt}'", "-c:a", "copy"]

        cmd += [output_path, "-y"]

        # Ejecutamos sin bloquear la UI
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if progress_cb: progress_cb(1.0)
        return f"Proceso completado:\n{output_path}"
        
    except subprocess.CalledProcessError as e:
        return f"Error en FFmpeg: {e.stderr}"
    except Exception as e:
        return f"Error inesperado: {str(e)}"