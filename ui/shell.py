"""
Módulo de Ventana Principal (Shell UI)
Contiene la estructura base de la aplicación (Sidebar, Barra de estado y panel central).
Hereda de TkinterDnD para permitir funcionalidad nativa de arrastrar y soltar 
archivos desde el sistema operativo en cualquier parte de la ventana.
"""

import os
import threading
import customtkinter as ctk
import pystray
from PIL import Image
from tkinterdnd2 import TkinterDnD, DND_FILES

from core.detector import detect_module, MODULE_ICONS, MODULE_NAMES, MODULE_ORDER
from core.job_queue import JobQueue, JobStatus
import core.config as cfg
import plyer

# ── Colores ───────────────────────────────────────────────────────────────────
BG_DARK    = "#0F172A"
BG_SIDEBAR = "#0D1526"
BG_CARD    = "#1E293B"
BG_ITEM    = "#334155"
ACCENT     = "#3B82F6"
TEXT_PRI   = "#F1F5F9"
TEXT_SEC   = "#94A3B8"
SUCCESS    = "#22C55E"
DANGER     = "#EF4444"
WARNING    = "#F59E0B"
BORDER     = "#334155"


class PrismShell(TkinterDnD.Tk):
    """
    Controlador maestro de la interfaz gráfica. Instancia los sub-módulos y gestiona
    el enrutamiento visual, las notificaciones del sistema operativo y los eventos globales.
    """
    def __init__(self):
        super().__init__()
        
        # Cargar configuración y aplicar tema
        self._notified_jobs = set()
        ctk.set_appearance_mode(cfg.get("theme", "Dark"))
        
        self.title("Prism")
        self.geometry("1150x720")
        self.minsize(900, 580)
        self.state('zoomed')
        self.configure(bg=BG_DARK)

        # Forzar barra superior oscura
        self.after(10, self._set_dark_titlebar)

        # ─── Cargar imagen del Logo (icon.png) ───
        try:
            self.logo_image = ctk.CTkImage(
                light_image=Image.open("icon.png"),
                dark_image=Image.open("icon.png"),
                size=(60, 60)  # Tamaño de la imagen
            )
        except Exception:
            self.logo_image = None
        # ──────────────────────────────────────────────

        # Icono de la ventana (para la barra de tareas de Windows)
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        # Interceptar el botón de la 'X' para minimizar en lugar de cerrar
        self.protocol('WM_DELETE_WINDOW', self._hide_window)

        self.job_queue = JobQueue(max_workers=2)
        self.backend = None

        self._modules: dict[str, ctk.CTkFrame] = {}
        self._sidebar_btns: dict[str, ctk.CTkButton] = {}
        self._active_id: str | None = None
        self._active_module = "pdf"
        self._job_panel_visible = False

        self._build_ui()
        self._register_modules()
        self._setup_global_drop()

        self.job_queue.on_update(self._on_queue_update)
        threading.Thread(target=self._check_backends, daemon=True).start()

        self.switch_module("pdf")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_statusbar()
    
    def _set_dark_titlebar(self):
        """Fuerza la barra de título de Windows a modo oscuro."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            # 20 es el atributo DWMWA_USE_IMMERSIVE_DARK_MODE en Windows 11
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(2)), 4)
        except Exception:
            pass

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, width=195, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew", rowspan=2)
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(10, weight=1)

        # ─── CABECERA: Logo de Imagen y Nombre ───
        header_frame = ctk.CTkFrame(sb, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=16, pady=(22, 2), sticky="w")

        if hasattr(self, 'logo_image') and self.logo_image:
            ctk.CTkLabel(header_frame, image=self.logo_image, text="").pack(side="left", padx=(0, 10))
        else:
            ctk.CTkLabel(header_frame, text="▲", font=("Segoe UI", 24), text_color=TEXT_PRI).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(header_frame, text="Prism",
                     font=("Segoe UI", 20, "bold"), text_color=TEXT_PRI).pack(side="left")

        # ─── SUBTÍTULO ───
        ctk.CTkLabel(sb, text="Gestor de formatos",
                     font=("Segoe UI", 13), text_color=TEXT_PRI).grid(
                     row=1, column=0, padx=16, pady=(0, 16), sticky="w")

        # ─── LÍNEA Y MÓDULOS ───
        ctk.CTkFrame(sb, height=1, fg_color=BORDER).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        ctk.CTkLabel(sb, text="MÓDULOS", font=("Segoe UI", 10, "bold"),
                     text_color=TEXT_SEC).grid(row=3, column=0, padx=16, pady=(0, 6), sticky="w")

        for i, mod_id in enumerate(MODULE_ORDER):
            icon = MODULE_ICONS[mod_id]
            name = MODULE_NAMES[mod_id]
            btn = ctk.CTkButton(
                sb, text=f"  {icon}  {name}", anchor="w",
                fg_color="transparent", hover_color=BG_ITEM, text_color=TEXT_SEC,
                font=("Segoe UI", 13), height=38, corner_radius=8,
                command=lambda m=mod_id: self.switch_module(m),
            )
            btn.grid(row=4 + i, column=0, padx=8, pady=2, sticky="ew")
            self._sidebar_btns[mod_id] = btn

        # Spacer
        ctk.CTkFrame(sb, height=1, fg_color=BORDER).grid(row=11, column=0, sticky="ew", padx=12, pady=(0, 8))

        # ─── AJUSTES Y COLA DE TRABAJOS ───
        self._settings_btn = ctk.CTkButton(
            sb, text="  ⚙  Ajustes", anchor="w",
            fg_color="transparent", hover_color=BG_ITEM, text_color=TEXT_SEC, 
            font=("Segoe UI", 12), height=34, corner_radius=8,
            command=self._open_settings,
        )
        self._settings_btn.grid(row=12, column=0, padx=8, pady=(2, 2), sticky="ew")

        self._jobs_btn = ctk.CTkButton(
            sb, text="  🕒  Cola de trabajos", anchor="w",
            fg_color="transparent", hover_color=BG_ITEM, text_color=TEXT_SEC, 
            font=("Segoe UI", 12), height=34, corner_radius=8,
            command=self._toggle_job_panel,
        )
        self._jobs_btn.grid(row=13, column=0, padx=8, pady=(2, 20), sticky="ew")
        self._backend_lbl = ctk.CTkLabel(sb, text="")

    def _build_main(self):
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0, border_color=ACCENT)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(0, weight=1)

        # Job panel (initially hidden, column 1)
        from ui.widgets import JobPanel
        self._job_panel = JobPanel(self._main, self.job_queue, width=260)
        self._job_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        self._job_panel.grid_remove()

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, height=28, corner_radius=0)
        bar.grid(row=1, column=1, sticky="ew")
        bar.grid_propagate(False)

        self._status_lbl = ctk.CTkLabel(bar, text="Listo",
                                        font=("Segoe UI", 10), text_color=TEXT_SEC)
        self._status_lbl.pack(side="left", padx=12)

        self._jobs_status = ctk.CTkLabel(bar, text="",
                                         font=("Segoe UI", 10), text_color=TEXT_SEC)
        self._jobs_status.pack(side="right", padx=12)

    # ── Module registration ───────────────────────────────────────────────────

    def _register_modules(self):
        from modules.pdf_module import PdfModule

        from modules.doc_module import DocsModule
        from modules.sheets_module import SheetsModule
        from modules.images_module import ImagesModule
        from modules.audio_module import AudioModule
        from modules.video_module import VideoModule

        available = {
            "pdf":    PdfModule,
            "docs":   DocsModule,
            "sheets": SheetsModule,
            "images": ImagesModule,
            "audio":  AudioModule,
            "video":  VideoModule,
        }

        placeholders = {}

        for mod_id in MODULE_ORDER:
            if mod_id in available:
                frame = available[mod_id](self._main, app=self)
            else:
                frame = ctk.CTkFrame(self._main, fg_color=BG_DARK)
                ctk.CTkLabel(frame, text=placeholders.get(mod_id, ""),
                             font=("Segoe UI", 15), text_color=TEXT_SEC).place(
                             relx=0.5, rely=0.5, anchor="center")
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_remove()
            self._modules[mod_id] = frame

    # ── Module switching ──────────────────────────────────────────────────────

    def switch_module(self, module_id: str):
        if module_id not in self._modules:
            return
        if self._active_id:
            self._modules[self._active_id].grid_remove()
            b = self._sidebar_btns.get(self._active_id)
            if b:
                b.configure(fg_color="transparent", text_color=TEXT_SEC)

        self._modules[module_id].grid()
        self._active_id = module_id
        self._active_module = module_id
        b = self._sidebar_btns.get(module_id)
        if b:
            b.configure(fg_color=BG_ITEM, text_color=TEXT_PRI)
        self.title(f"Prism — {MODULE_NAMES.get(module_id, module_id)}")

    # ── Global drag & drop ────────────────────────────────────────────────────

    def _setup_global_drop(self):
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_global_drop)
        self.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        
    def _on_drag_enter(self, event):
        # Iluminar el borde principal fuertemente
        self._main.configure(border_width=4)
        
    def _on_drag_leave(self, event):
        self._main.configure(border_width=0)

    def _on_global_drop(self, event):
        self._on_drag_leave(event)
        import re, os
        paths = []
        for m in re.finditer(r'\{([^}]+)\}|(\S+)', event.data):
            p = m.group(1) or m.group(2)
            if p: paths.append(p)
        
        if not paths: return

        # --- Lógica de permanencia ---
        ext = os.path.splitext(paths[0])[1].lower()
        v_exts = [".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm"]
        
        # Si ya estamos en audio y soltamos un vídeo, nos quedamos en audio
        if self._active_module == "audio" and ext in v_exts:
            if hasattr(self._modules["audio"], "receive_files"):
                self._modules["audio"].receive_files(paths)
            return

        # Si no, procedemos con la detección automática normal
        mod_id = detect_module(paths[0])
        if mod_id and mod_id in self._modules:
            self.switch_module(mod_id)
            mod = self._modules[mod_id]
            if hasattr(mod, "receive_files"):
                mod.receive_files(paths)
        else:
            self.set_status("Tipo de archivo no soportado", error=True)

    # ── Backend check ─────────────────────────────────────────────────────────

    def _check_backends(self):
        from core.backend import check_backends
        self.backend = check_backends()
        self.after(0, self._update_backend_ui)

    def _update_backend_ui(self):
        if not self.backend:
            return
        lines = self.backend.summary_lines()
        self._backend_lbl.configure(text="\n".join(lines))

    # ── Job queue updates ─────────────────────────────────────────────────────

    def _on_queue_update(self):
        try:
            self.after(0, self._refresh_job_status)
            if self._job_panel_visible:
                self.after(0, self._job_panel.refresh)
        except Exception:
            pass

    def _refresh_job_status(self):
        jobs = self.job_queue.get_jobs()
        running = [j for j in jobs if j.status == JobStatus.RUNNING]
        pending = [j for j in jobs if j.status == JobStatus.PENDING]
        errors  = [j for j in jobs if j.status == JobStatus.ERROR]
        done    = [j for j in jobs if j.status == JobStatus.DONE]

        # Notificaciones nativas
        if cfg.get("notifications"):
            for j in done:
                if j.id not in self._notified_jobs:
                    self._notified_jobs.add(j.id)
                    try:
                        plyer.notification.notify(
                            title="Prism - Trabajo completado",
                            message=f"Se ha terminado de procesar: {j.name}",
                            app_name="Prism",
                            timeout=5
                        )
                    except Exception:
                        pass
        else:
            # Simplemente los marcamos como notificados para que no se acumulen
            for j in done:
                self._notified_jobs.add(j.id)

        if running:
            self._jobs_status.configure(
                text=f"⚙ {len(running)} en progreso · {len(pending)} en cola",
                text_color=ACCENT)
        elif errors:
            self._jobs_status.configure(
                text=f"⚠ {len(errors)} error(es)", text_color=DANGER)
        elif done:
            self._jobs_status.configure(
                text=f"✓ {len(done)} completado(s)", text_color=SUCCESS)
        else:
            self._jobs_status.configure(text="")

    def open_job_panel(self):
        """Fuerza la apertura gráfica del panel lateral si está cerrado."""
        if not self._job_panel_visible:
            self._toggle_job_panel()

    def _toggle_job_panel(self):
        self._job_panel_visible = not self._job_panel_visible
        if self._job_panel_visible:
            self._job_panel.grid()
            self._job_panel.refresh()
        else:
            self._job_panel.grid_remove()

    # ── Public helpers ────────────────────────────────────────────────────────

    def set_status(self, msg: str, error=False, success=False):
        color = DANGER if error else (SUCCESS if success else TEXT_SEC)
        self._status_lbl.configure(text=msg, text_color=color)
        if not error:
            self.after(5000, lambda: self._status_lbl.configure(
                text="Listo", text_color=TEXT_SEC))

    def submit_job(self, name: str, fn, *args, on_done=None, **kwargs):
        return self.job_queue.submit(name, fn, *args, on_done=on_done, **kwargs)


    # ── System Tray & Settings ────────────────────────────────────────────────

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Ajustes de Prism")
        win.geometry("400x320")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg=BG_DARK)
        
        ctk.CTkLabel(win, text="Preferencias", font=("Segoe UI", 18, "bold"), text_color=TEXT_PRI).pack(pady=(20, 20))
        
        tray_var = ctk.BooleanVar(value=cfg.get("close_to_tray", False))
        notif_var = ctk.BooleanVar(value=cfg.get("notifications", True))
        
        # Minimizar
        ctk.CTkSwitch(
            win, text="Minimizar a la bandeja del sistema (Reloj) al cerrar", 
            variable=tray_var, font=("Segoe UI", 12), text_color=TEXT_PRI
        ).pack(fill="x", padx=30, pady=15)
        
        # Notificaciones
        ctk.CTkSwitch(
            win, text="Notificaciones flotantes de Windows", 
            variable=notif_var, font=("Segoe UI", 12), text_color=TEXT_PRI
        ).pack(fill="x", padx=30, pady=15)

        # Apply
        def apply_changes():
            cfg.set("close_to_tray", tray_var.get())
            cfg.set("notifications", notif_var.get())
            win.destroy()
            self.set_status("Ajustes aplicados correctamente", success=True)
            
        ctk.CTkButton(
            win, text="Aplicar y Cerrar", font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT, text_color="white",
            height=36, corner_radius=8, command=apply_changes
        ).pack(pady=30)

    def _hide_window(self):
        """Oculta la ventana y activa el icóno en el área de notificación si está configurado."""
        if not cfg.get("close_to_tray"):
            self.destroy()
            os._exit(0)  # Mata todos los hilos de IA en segundo plano
            return
            
        self.withdraw()

        try:
            image = Image.open("icon.png")
        except Exception:
            image = Image.new('RGB', (64, 64), color='white')

        menu = pystray.Menu(
            pystray.MenuItem('Abrir Prism', self._show_window, default=True),
            pystray.MenuItem('Salir', self._quit_app)
        )
        self.tray_icon = pystray.Icon("Prism", image, "Prism", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self, icon, item):
        """Restaura la ventana principal."""
        self.tray_icon.stop()
        self.after(0, self.deiconify)

    def _quit_app(self, icon, item):
        """Cierra la aplicación por completo y mata los procesos en segundo plano."""
        self.tray_icon.stop()
        self.destroy()
        os._exit(0)  # Mata todos los hilos de IA/workers en segundo plano
