import customtkinter as ctk
from abc import abstractmethod

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