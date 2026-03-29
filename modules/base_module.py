"""
Módulo Base de Especialización
Clase abstracta de la que heredan todos los módulos de procesamiento (Audio, PDF, etc).
Proporciona acceso directo al bus central (App) y gestiona de forma transparente
la inserción de componentes visuales estándar (Divisores, Paneles).
"""

import customtkinter as ctk
from abc import abstractmethod
import os
import sys

def resolve_tool_path(subdir: str, exe: str) -> str:
    """
    Localiza un binario de herramienta externo de forma portable.
    Busca primero en la carpeta de la aplicación (distribución) y 
    luego cae al PATH global del sistema.
    """
    # Determinamos la raíz de la aplicación (donde está main.py o el .exe)
    if getattr(sys, 'frozen', False):
        # Ejecutando desde el empaquetado (dist/Prism/)
        base_dir = os.path.dirname(sys.executable)
    else:
        # Ejecutando desde código fuente (modules/ es hijo de la raíz)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Candidatos comunes de carpetas de herramientas
    candidates = [
        os.path.join(base_dir, subdir, exe),                 # Tesseract-OCR/tesseract.exe
        os.path.join(base_dir, subdir, "bin", exe),          # ffmpeg/bin/ffmpeg.exe
        os.path.join(base_dir, subdir, "Library", "bin", exe) # poppler/Library/bin/pdftocairo.exe
    ]

    for path in candidates:
        if os.path.exists(path):
            return path
            
    # Fallback: asumimos que está en el PATH global del sistema
    return exe

# ── Paleta compartida ────────────────────────────────────────────────────────
BG_DARK  = "#0F172A"
BG_CARD  = "#1E293B"
BG_ITEM  = "#334155"
ACCENT   = "#3B82F6"
ACCENT_H = "#2563EB"
TEXT_PRI = "#F1F5F9"
TEXT_SEC = "#94A3B8"
SUCCESS  = "#22C55E"
DANGER   = "#EF4444"
WARNING  = "#F59E0B"
BORDER   = "#334155"

DIV_COLOR        = "#1A2744"   # color del divisor estático
DIV_WIDTH        = 5           # px de ancho del divisor
SIDEBAR_DEFAULT  = 220         # ancho fijo inicial


class BaseModule(ctk.CTkFrame):
    """
    Todos los módulos heredan de esta clase.
    Reciben `app` (la shell) para acceder a job_queue, backend, set_status, etc.

    Layout de columnas:
        col 0  → sidebar de herramientas  (tamaño fijo)
        col 1  → divisor de 5 px          (estático)
        col 2  → panel de contenido       (weight=1, se expande)

    Cada módulo debe:
      - Llamar _build_divider() en __init__ DESPUÉS de _build_sidebar()
      - Hacer grid de sus paneles en column=2
      - Implementar receive_files(paths)
    """

    module_id: str = ""

    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)

    # ── Divisor Visual Fijo ──────────────────────────────────────────────────

    def _build_divider(self, column: int = 1):
        """
        Inserta un divisor visual sin lógica de redimensión.
        column=1 → divisor izquierdo del sidebar
        column=3 → divisor derecho del panel de preview
        """
        is_left = (column == 1)

        if is_left:
            # Tamaño fijo para el menú lateral
            self.grid_columnconfigure(0, minsize=SIDEBAR_DEFAULT, weight=0)
            self.grid_columnconfigure(1, minsize=DIV_WIDTH, weight=0)
            if not hasattr(self, '_right_panel_exists'):
                self.grid_columnconfigure(2, weight=1)
        else:
            # Tamaño fijo para el panel derecho de vista previa (280px)
            self._right_panel_exists = True
            self.grid_columnconfigure(2, weight=1)          
            self.grid_columnconfigure(column, minsize=DIV_WIDTH, weight=0)
            self.grid_columnconfigure(column + 1, minsize=280, weight=0)

        # Divisor puramente decorativo, sin eventos de ratón
        div = ctk.CTkFrame(
            self, fg_color=DIV_COLOR, width=DIV_WIDTH, corner_radius=0
        )
        div.grid(row=0, column=column, sticky="nsew")
        div.grid_propagate(False)

    # ── Helpers para subclases ───────────────────────────────────────────────

    def submit_job(self, name: str, fn, *args, on_done=None, **kwargs) -> str:
        # Abre el panel lateral automáticamente para que el usuario sepa que algo ocurre
        if hasattr(self.app, 'open_job_panel'):
            self.app.open_job_panel()
        return self.app.job_queue.submit(name, fn, *args, on_done=on_done, **kwargs)

    def set_status(self, msg: str, error=False, success=False):
        self.app.set_status(msg, error=error, success=success)

    @property
    def backend(self):
        return self.app.backend

    # ── Interface que cada módulo implementa ────────────────────────────────

    @abstractmethod
    def receive_files(self, paths: list[str]):
        """Called when files are dropped anywhere on the window."""
        ...


class BasePanel(ctk.CTkFrame):
    """
    Clase base para todos los paneles de herramientas (ConvertPanel, ResizePanel, etc).
    Proporciona métodos rápidos para interactuar con la JobQueue y el estado de la app
    a través del módulo padre (master).
    """
    def __init__(self, master, app=None, **kwargs):
        # Aseguramos un estilo base para todos los paneles si no se especifica otro.
        kwargs.setdefault("fg_color", BG_DARK)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)
        self._app_override = app

    def submit_job(self, name: str, fn, *args, **kwargs) -> str:
        """Proxy para enviar trabajos a través del módulo contenedor."""
        if hasattr(self.master, 'submit_job'):
            return self.master.submit_job(name, fn, *args, **kwargs)
        # Fallback de seguridad si el padre no es un BaseModule
        return self.app.job_queue.submit(name, fn, *args, **kwargs)

    def set_status(self, msg: str, error=False, success=False):
        """Proxy para actualizar el estado a través del módulo contenedor."""
        if hasattr(self.master, 'set_status'):
            self.master.set_status(msg, error=error, success=success)
        else:
            self.app.set_status(msg, error=error, success=success)

    @property
    def app(self):
        """Retorna el objeto app buscándolo recursivamente o via inyección."""
        if hasattr(self, '_app_override') and self._app_override:
            return self._app_override
        if hasattr(self.master, 'app'):
            return self.master.app
        # Si el master es la app (ej. tests)
        return self.master