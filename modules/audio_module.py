"""
Módulo de Procesamiento de Audio e IA (Audio Module)
Hereda de BaseModule.

Este módulo centraliza todas las operaciones de sonido:
- Transcripción IA nativa (Whisper) ejecutada en background.
- Extracción de pistas de audio desde contenedores de vídeo (.mp4, .mkv).
- Conversión, recorte, re-muestreo y limitación de volumen.

Dependencias clave:
- pydub (Fallback nativo si FFmpeg no está presente)
- FFmpeg (Vía _run_ffmpeg embebido)
- Whisper/PyTorch (Carga demorada en hilo fantasma `_preload_ai` para no bloquear GUI)

Clases y Funciones principales:
- `TranscriptionPanel`, `ConvertAudioPanel`: Sub-paneles gráficos con UI dedicada.
- `_ai_transcribe_task()`: Puntero de ejecución pesado para procesar Whisper en la JobQueue.
"""

import os
import sys
import subprocess
import customtkinter as ctk
from tkinter import messagebox, filedialog

# Importamos las bases y constantes del proyecto
from modules.base_module import (
    BaseModule, BasePanel, BG_DARK, BG_CARD, BG_ITEM,
    ACCENT, ACCENT_H, TEXT_PRI, TEXT_SEC, BORDER,
    resolve_tool_path
)
from core.job_queue import JobStatus
from ui.widgets import DropZone, FileListWidget

# --- CONFIGURACIÓN ---
AUDIO_EXTS = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".mkv", ".avi"]
VIDEO_EXTS = [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"]

TOOLS = [
    ("transcribe", "✍️", "Transcribir (IA)"),
    ("extract",    "🎵", "Extraer de Vídeo"),
    ("convert",    "🔄", "Convertir Formato"),
    ("cut",        "✂️", "Cortar Audio"),
    ("merge",      "🔗", "Unir Audios"),
    ("volume",     "🔊", "Ajustar Volumen"),
]

import threading
def _preload_ai():
    try:
        import torch
        import whisper
    except:
        pass
threading.Thread(target=_preload_ai, daemon=True).start()

# ── Widget de Vista Previa de Audio/Texto ─────────────────────────────────────

class AudioPreviewPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_DARK, width=300, corner_radius=0, **kwargs)
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="RESULTADO DE TRANSCRIPCIÓN", font=("Segoe UI", 11, "bold"), 
                     text_color=TEXT_SEC).grid(row=0, column=0, pady=(20, 10))
        
        # Caja de texto para mostrar un fragmento de la transcripción
        self.text_preview = ctk.CTkTextbox(self, fg_color=BG_CARD, corner_radius=8, 
                                            font=("Segoe UI", 12), text_color=TEXT_PRI)
        self.text_preview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        self.rowconfigure(1, weight=1)
        
        self.text_preview.insert("0.0", "Arrastra un audio y ejecuta la IA para ver el texto aquí...")
        self.text_preview.configure(state="disabled")

    def update_text(self, file_path):
        """Lee el inicio del archivo generado y lo muestra."""
        if not file_path or not os.path.exists(file_path): return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(1000) # Leemos los primeros 1000 caracteres
            self.text_preview.configure(state="normal")
            self.text_preview.delete("0.0", "end")
            self.text_preview.insert("0.0", content + "...")
            self.text_preview.configure(state="disabled")
        except Exception:
            pass

    def show_loading(self):
        """Muestra un mensaje de espera mientras Whisper procesa."""
        self.text_preview.configure(state="normal")
        self.text_preview.delete("0.0", "end")
        self.text_preview.insert("0.0", "⏳ PROCESANDO TRANSCRIPCIÓN...\n\nUsando IA local (Whisper Small). Esto puede tardar, váyase a por un café...")
        self.text_preview.configure(state="disabled")

# ── Panel Base y Herramientas ────────────────────────────────────────────────

class _BaseAudioPanel(BasePanel):
    title = ""
    description = ""
    allowed_exts = AUDIO_EXTS

    def __init__(self, master, app, **kwargs):
        super().__init__(master, app=app, **kwargs)
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
        self._file_list.clear() # Audio suele ser de uno en uno para transcripción
        self._file_list.add_files(paths)

    def _build_options(self): pass

    def _build_run_btn(self):
        self._run_btn = ctk.CTkButton(
            self, text="▶  Ejecutar", height=42, fg_color=ACCENT, hover_color=ACCENT_H,
            font=("Segoe UI", 14, "bold"), corner_radius=10, command=self._run)
        self._run_btn.grid(row=10, column=0, sticky="ew", padx=24, pady=(8, 20))

    def _on_done(self, job):
        if job.status == JobStatus.DONE:
            # Si es una transcripción, actualizamos el panel lateral
            if str(job.result).endswith(".txt") and hasattr(self.master, 'preview'):
                self.master.preview.update_text(job.result)
            messagebox.showinfo("Listo", f"Proceso completado:\n{job.result}")
        elif job.status == JobStatus.ERROR:
            messagebox.showerror("Error", job.error)

    def _section(self, text, row=3):
        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 8))
        f.columnconfigure(0, weight=1)
        ctk.CTkLabel(f, text=text, font=("Segoe UI", 11, "bold"), text_color=TEXT_SEC).grid(row=0, column=0, padx=14, pady=(10, 6), sticky="w")
        return f
    
    def _backend_info(self, row: int = 4):
        self._backend_lbl = ctk.CTkLabel(self, text="Comprobando motor FFmpeg...",
                                         font=("Segoe UI", 10), text_color=TEXT_SEC)
        self._backend_lbl.grid(row=row, column=0, padx=26, pady=(0, 6), sticky="w")
        self._update_backend_lbl()

    def _update_backend_lbl(self):
        backend = self.app.backend
        if backend is None:
            self.after(500, self._update_backend_lbl)
            return

        if backend.ffmpeg:
            self._backend_lbl.configure(text=f"Backend: FFmpeg {backend.ffmpeg_version} ✓",
                                        text_color="#22C55E")
        else:
            self._backend_lbl.configure(text="⚠ FFmpeg no detectado", text_color="#F59E0B")

# ── Paneles Específicos ───────────────────────────────────────────────────────

class TranscriptionPanel(_BaseAudioPanel):
    title = "Transcripción de Voz (IA)"
    description = "Usa Whisper para convertir grabaciones a texto con alta precisión."

    def _build_options(self):
        f = self._section("Configuración de IA")
        try:
            import torch
            status = "GPU Acelerada (CUDA)" if torch.cuda.is_available() else "Modo CPU (Estándar)"
        except ImportError:
            status = "PyTorch no detectado (instala torch)"
        ctk.CTkLabel(f, text=f"Hardware detectado: {status}", font=("Segoe UI", 11), text_color=TEXT_SEC).grid(
                     row=1, column=0, padx=14, pady=(0, 12), sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            from tkinter import messagebox
            messagebox.showwarning("Aviso", "Primero debes arrastrar al menos un archivo al recuadro superior antes de hacer clic en Ejecutar.")
            return
        
        out = filedialog.asksaveasfilename(
            title="Guardar transcripción", defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile=os.path.splitext(os.path.basename(paths[0]))[0] + "_trans.txt"
        )
        if not out: return

        if hasattr(self.master, 'preview'):
            self.master.preview.show_loading()

        self.submit_job(
            f"IA Audio: Transcribiendo {os.path.basename(paths[0])}",
            _ai_transcribe_task, paths[0], out,
            on_done=self._on_done
        )


# ── Convertir ─────────────────────────────────────────────────────────────────

class ConvertAudioPanel(_BaseAudioPanel):
    title = "Convertir Audio"
    description = "Cambia el formato de tus archivos de audio a MP3, WAV o OGG."

    def _build_options(self):
        f = self._section("Formato de salida")
        self._fmt = ctk.CTkSegmentedButton(
            f, values=["MP3", "WAV", "OGG"],
            font=("Segoe UI", 12))
        self._fmt.set("MP3")
        self._fmt.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            from tkinter import messagebox
            messagebox.showwarning("Aviso", "Primero debes arrastrar al menos un archivo al recuadro superior antes de hacer clic en Ejecutar.")
            return
        
        fmt = self._fmt.get().lower()
        out_dir = filedialog.askdirectory(title="Selecciona carpeta de salida")
        if not out_dir: return

        self.submit_job(
            f"Audio: Convertir a {fmt.upper()}",
            _convert_audio, paths, out_dir, fmt, "192k", self.app.backend,
            on_done=self._on_done
        )


# ── Cortar ────────────────────────────────────────────────────────────────────

class CutPanel(_BaseAudioPanel):
    title = "Cortar audio"
    description = "Extrae un fragmento entre dos marcas de tiempo."

    def _build_options(self):
        f = self._section("Fragmento a extraer")
        
        # Agrupamos los elementos en un frame transparente para que se peguen a la izquierda
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.grid(row=1, column=0, padx=14, pady=(5, 15), sticky="w")

        ctk.CTkLabel(opts, text="Inicio (mm:ss):", font=("Segoe UI", 12),
                     text_color=TEXT_PRI).grid(row=0, column=0, pady=5, sticky="w")
        self._start = ctk.CTkEntry(opts, width=90, height=32,
                                   placeholder_text="0:00", font=("Segoe UI", 12))
        self._start.grid(row=0, column=1, padx=(15, 0), pady=5, sticky="w")

        ctk.CTkLabel(opts, text="Fin (mm:ss):", font=("Segoe UI", 12),
                     text_color=TEXT_PRI).grid(row=1, column=0, pady=5, sticky="w")
        self._end = ctk.CTkEntry(opts, width=90, height=32,
                                 placeholder_text="1:30", font=("Segoe UI", 12))
        self._end.grid(row=1, column=1, padx=(15, 0), pady=5, sticky="w")

        # El indicador de FFmpeg lo ponemos debajo del grupo
        self._backend_info(row=4)

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivo", "Añade un archivo de audio."); return
        start_str = self._start.get().strip() or "0:00"
        end_str   = self._end.get().strip()
        if not end_str:
            messagebox.showwarning("Falta el fin", "Introduce el tiempo de fin."); return

        try:
            start_ms = _parse_time(start_str)
            end_ms   = _parse_time(end_str)
            assert end_ms > start_ms, "El fin debe ser mayor que el inicio."
        except Exception as e:
            messagebox.showerror("Tiempo inválido", str(e)); return

        ext = os.path.splitext(paths[0])[1]
        out = filedialog.asksaveasfilename(
            title="Guardar fragmento",
            defaultextension=ext,
            filetypes=[(ext.upper().strip("."), f"*{ext}")],
            initialfile=f"fragmento{ext}",
        )
        if not out: return
        backend = self.app.backend
        self.submit_job(
            f"Cortar {os.path.basename(paths[0])}",
            _cut_audio, paths[0], out, start_ms, end_ms, backend,
            on_done=self._on_done,
        )


# ── Unir ──────────────────────────────────────────────────────────────────────

class MergeAudioPanel(_BaseAudioPanel):
    title = "Unir audios"
    description = "Concatena varios archivos en uno. Reordena con ▲▼."
    multi_file = True

    def _build_options(self):
        f = self._section("Formato de salida")
        f.columnconfigure(0, weight=1)

        self._fmt = ctk.CTkSegmentedButton(
            f, values=["MP3", "WAV", "OGG", "FLAC"],
            font=("Segoe UI", 12),
        )
        self._fmt.set("MP3")
        self._fmt.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")

        self._backend_info(row=4)

    def _run(self):
        paths = self._file_list.paths
        if len(paths) < 2:
            messagebox.showwarning("Pocos archivos", "Añade al menos 2 audios."); return
        fmt = self._fmt.get().lower()
        out = filedialog.asksaveasfilename(
            title="Guardar audio combinado",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")],
            initialfile=f"combinado.{fmt}",
        )
        if not out: return
        backend = self.app.backend
        self.submit_job(
            f"Unir {len(paths)} audios",
            _merge_audio, paths, out, fmt, backend,
            on_done=self._on_done,
        )


# ── Volumen ───────────────────────────────────────────────────────────────────

class VolumePanel(_BaseAudioPanel):
    title = "Ajustar volumen"
    description = "Sube o baja el volumen en decibelios."

    def _build_options(self):
        f = self._section("Ajuste de volumen")
        f.columnconfigure(0, weight=1)

        slider_row = ctk.CTkFrame(f, fg_color="transparent")
        slider_row.grid(row=1,
                        column=0,
                        padx=14,
                        pady=(10, 12),
                        sticky="ew")

        self._db_lbl = ctk.CTkLabel(slider_row,
                                    text="+0 dB",
                                    font=("Segoe UI", 13, "bold"),
                                    text_color=TEXT_PRI, width=50)

        self._db_lbl.pack(side="left", padx=(0, 10))

        self._slider = ctk.CTkSlider(
            slider_row, from_=-20, to=20, width=180,
            number_of_steps=40,
            command=self._update_db_label,
        )
        self._slider.set(0)
        self._slider.pack(side="left")

        ctk.CTkLabel(slider_row, text="Rango: −20 dB (silenciar) a +20 dB (amplificar)",
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack(side="left", padx=(15, 0))

        self._backend_info(row=4)

    def _update_db_label(self, val):
        db = round(val)
        sign = "+" if db >= 0 else ""
        self._db_lbl.configure(text=f"{sign}{db} dB")

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivo", "Añade un archivo de audio."); return
        db = round(self._slider.get())
        ext = os.path.splitext(paths[0])[1]
        sign = "mas" if db >= 0 else "menos"
        out = filedialog.asksaveasfilename(
            title="Guardar con volumen ajustado",
            defaultextension=ext,
            filetypes=[(ext.upper().strip("."), f"*{ext}")],
            initialfile=f"volumen_{sign}{abs(db)}dB{ext}",
        )
        if not out: return
        backend = self.app.backend
        self.submit_job(
            f"Volumen {'+' if db>=0 else ''}{db}dB: {os.path.basename(paths[0])}",
            _adjust_volume, paths[0], out, db, backend,
            on_done=self._on_done,
        )


# ── Extraer audio de vídeo ────────────────────────────────────────────────────

class ExtractAudioPanel(_BaseAudioPanel):
    title = "Extraer audio de vídeo"
    description = "Extrae la pista de audio de un archivo de vídeo."
    drop_exts = VIDEO_EXTS
    multi_file = True

    def _build_options(self):
        f = self._section("Formato de salida")
        f.columnconfigure(0, weight=1)

        self._fmt = ctk.CTkSegmentedButton(
            f, values=["MP3", "WAV", "OGG", "FLAC", "AAC"],
            font=("Segoe UI", 12),
        )
        self._fmt.set("MP3")
        self._fmt.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")

        self._bitrate = ctk.CTkSegmentedButton(
            f, values=["128k", "192k", "320k"],
            font=("Segoe UI", 12), width=200,
        )
        self._bitrate.set("192k")
        self._bitrate.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="w")

        self._backend_info(row=4)

    def _run(self):
        paths = self._file_list.paths
        if not paths:
            messagebox.showwarning("Sin archivo", "Añade un archivo de vídeo."); return
        out_dir = filedialog.askdirectory(title="Carpeta de salida")
        if not out_dir: return
        fmt = self._fmt.get().lower()
        bitrate = self._bitrate.get()
        backend = self.app.backend
        self.submit_job(
            f"Extraer audio de {len(paths)} vídeo(s)",
            _extract_audio_from_video, paths, out_dir, fmt, bitrate, backend,
            on_done=self._on_done,
        )


# ── Módulo Principal ──────────────────────────────────────────────────────────

class AudioModule(BaseModule):
    module_id = "audio"

    def __init__(self, master, app, **kwargs):
        super().__init__(master, app, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, minsize=210)
        
        # Diseño de 3 columnas
        self.columnconfigure(0, weight=0) # Sidebar
        self.columnconfigure(1, weight=0) # Divider
        self.columnconfigure(2, weight=1) # Main
        self.columnconfigure(3, weight=0) # Divider
        self.columnconfigure(4, weight=0) # Preview

        self._panels = {}
        self._tool_btns = {}
        self._active_tool = ""
        
        self._build_sidebar()
        self._build_divider(1)
        
        # Panel de Vista Previa de Texto
        self._build_divider(3)
        self.preview = AudioPreviewPanel(self)
        self.preview.grid(row=0, column=4, sticky="ns")

        self._build_panels()
        self._switch_tool("transcribe")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(sb, text="Herramientas Audio", 
                     font=("Segoe UI", 11, "bold"), 
                     text_color=TEXT_SEC).grid(
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

    def _build_panels(self):
        builders = {
            "transcribe": TranscriptionPanel,
            "extract":    ExtractAudioPanel,
            "convert":    ConvertAudioPanel,
            "cut":        CutPanel,
            "merge":      MergeAudioPanel,
            "volume":     VolumePanel
        }
        for tid, cls in builders.items():
            panel = cls(self, app=self.app)
            panel.grid(row=0, column=2, sticky="nsew")
            panel.grid_remove()
            self._panels[tid] = panel

    def _build_divider(self, col):
        ctk.CTkFrame(self, width=1, fg_color=BORDER).grid(row=0, column=col, sticky="ns")
    

# ── Lógica de IA y Procesamiento ─────────────────────────────────────────────

def _ai_transcribe_task(input_path: str, output_path: str, model_type="small", progress_cb=None):
    """Tarea de transcripción con limpieza de memoria garantizada."""
    import torch
    import whisper
    model = None
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Cargamos el modelo seleccionado (base o small)
        model = whisper.load_model(model_type, device=device)
        
        result = model.transcribe(
            input_path, 
            verbose=False, 
            language="es",
            fp16=(device == "cuda")
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result["text"].strip())
            
        return output_path

    except Exception as e:
        return f"Error IA: {str(e)}"
    
    finally:
        # Esto se ejecuta SIEMPRE, incluso si hay un error o un return
        if model is not None:
            del model
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        import gc
        gc.collect() # Liberación forzada de RAM

def _parse_time(s: str) -> int:
    """'mm:ss' o 'hh:mm:ss' → milisegundos."""
    parts = s.strip().split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        return (parts[0] * 60 + parts[1]) * 1000
    elif len(parts) == 3:
        return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000
    raise ValueError(f"Formato de tiempo inválido: '{s}'. Usa mm:ss o hh:mm:ss.")


def _has_ffmpeg(backend) -> bool:
    return backend is not None and backend.ffmpeg


def _run_ffmpeg(args: list, timeout: int = 300) -> None:
    """Ejecuta FFmpeg de forma totalmente invisible en Windows."""
    import subprocess
    import os
    
    # Bandera mágica de Windows para ocultar la consola del subproceso
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    
    # Intentamos localizar el ffmpeg local si existe
    ffmpeg_exe = resolve_tool_path("ffmpeg", "ffmpeg.exe")

    # Ejecutamos FFmpeg
    result = subprocess.run(
        [ffmpeg_exe, "-y"] + args,
        capture_output=True, # Capturamos la salida para que no salga en terminal
        text=True,
        timeout=timeout,
        creationflags=creationflags 
    )
    
    # Si falla, lanzamos el error con los últimos detalles
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-500:] if result.stderr else "FFmpeg falló en silencio.")
    
# ══════════════════════════════════════════════════════════════════════════════
# Funciones de operación (hilo separado, reciben progress_cb)
# ══════════════════════════════════════════════════════════════════════════════

def _convert_audio(paths: list, out_dir: str, fmt: str, bitrate: str,
                   backend, progress_cb=None) -> str:
    total = len(paths)
    created = []

    for i, path in enumerate(paths):
        stem = os.path.splitext(os.path.basename(path))[0]
        out  = os.path.join(out_dir, f"{stem}.{fmt}")

        if _has_ffmpeg(backend):
            extra = ["-b:a", bitrate] if fmt in ("mp3", "ogg", "m4a", "aac") else []
            _run_ffmpeg(["-i", path] + extra + [out])
        else:
            try:
                from pydub import AudioSegment
            except ImportError:
                raise RuntimeError("pydub no instalado. Ejecuta: pip install pydub")
            audio = AudioSegment.from_file(path)
            export_kwargs = {}
            if fmt in ("mp3", "ogg", "m4a"):
                export_kwargs["bitrate"] = bitrate
            audio.export(out, format=fmt, **export_kwargs)

        created.append(out)
        if progress_cb:
            progress_cb((i + 1) / total)

    return f"{len(created)} archivo(s) en:\n{out_dir}"


def _cut_audio(path: str, out: str, start_ms: int, end_ms: int,
               backend, progress_cb=None) -> str:
    if _has_ffmpeg(backend):
        def ms_to_ts(ms):
            s = ms // 1000
            return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
        _run_ffmpeg([
            "-ss", ms_to_ts(start_ms),
            "-to", ms_to_ts(end_ms),
            "-i", path,
            "-c", "copy",
            out,
        ])
    else:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(path)
        fragment = audio[start_ms:end_ms]
        ext = os.path.splitext(out)[1].lstrip(".")
        fragment.export(out, format=ext)

    if progress_cb:
        progress_cb(1.0)

    dur_s = (end_ms - start_ms) // 1000
    return f"{out}\n\nDuración: {dur_s // 60}:{dur_s % 60:02d}"


def _merge_audio(paths: list, out: str, fmt: str,
                 backend, progress_cb=None) -> str:
    if _has_ffmpeg(backend):
        import tempfile
        # Crear lista temporal de ficheros para ffmpeg concat
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            for p in paths:
                f.write(f"file '{p}'\n")
            list_file = f.name
        try:
            _run_ffmpeg([
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                out,
            ])
        finally:
            os.unlink(list_file)
    else:
        from pydub import AudioSegment
        combined = AudioSegment.empty()
        total = len(paths)
        for i, path in enumerate(paths):
            combined += AudioSegment.from_file(path)
            if progress_cb:
                progress_cb((i + 1) / total * 0.9)
        combined.export(out, format=fmt)

    if progress_cb:
        progress_cb(1.0)
    return out


def _adjust_volume(path: str, out: str, db: float,
                   backend, progress_cb=None) -> str:
    if _has_ffmpeg(backend):
        _run_ffmpeg([
            "-i", path,
            "-filter:a", f"volume={db}dB",
            out,
        ])
    else:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(path)
        adjusted = audio + db  # pydub usa + para subir dB
        ext = os.path.splitext(out)[1].lstrip(".")
        adjusted.export(out, format=ext)

    if progress_cb:
        progress_cb(1.0)

    sign = "+" if db >= 0 else ""
    return f"{out}\n\nVolumen ajustado: {sign}{db} dB"


def _extract_audio_from_video(paths: list, out_dir: str, fmt: str, bitrate: str,
                               backend, progress_cb=None) -> str:
    total = len(paths)
    created = []

    for i, path in enumerate(paths):
        stem = os.path.splitext(os.path.basename(path))[0]
        out  = os.path.join(out_dir, f"{stem}.{fmt}")

        if _has_ffmpeg(backend):
            extra = ["-b:a", bitrate] if fmt in ("mp3", "ogg", "aac") else []
            _run_ffmpeg(["-i", path, "-vn"] + extra + [out])
        else:
            try:
                from moviepy.editor import VideoFileClip
            except ImportError:
                raise RuntimeError(
                    "moviepy no instalado. Ejecuta: pip install moviepy\n"
                    "O instala FFmpeg para mejor compatibilidad."
                )
            clip = VideoFileClip(path)
            clip.audio.write_audiofile(out, logger=None)
            clip.close()

        created.append(out)
        if progress_cb:
            progress_cb((i + 1) / total)

    return f"{len(created)} archivo(s) en:\n{out_dir}"
