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

DIV_COLOR        = "#1A2744"   # color del divisor en reposo
DIV_COLOR_HOVER  = ACCENT      # color al pasar el ratón
DIV_WIDTH        = 5           # px de ancho del divisor
SIDEBAR_MIN      = 110         # ancho mínimo del sidebar
SIDEBAR_MAX      = 340         # ancho máximo del sidebar
SIDEBAR_DEFAULT  = 220         # ancho inicial


class BaseModule(ctk.CTkFrame):
    """
    Todos los módulos heredan de esta clase.
    Reciben `app` (la shell) para acceder a job_queue, backend, set_status, etc.

    Layout de columnas:
        col 0  → sidebar de herramientas  (ancho variable, arrastrable)
        col 1  → divisor de 5 px          (cursor doble flecha)
        col 2  → panel de contenido       (weight=1, se expande)

    Cada módulo debe:
      - Llamar _build_divider() en __init__ DESPUÉS de _build_sidebar()
      - Hacer grid de sus paneles en column=2
      - NO usar grid_propagate(False) en el sidebar frame
      - Implementar receive_files(paths)
    """

    module_id: str = ""

    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        # columnas: configuradas por _build_divider()

    # ── Divisor arrastrable ──────────────────────────────────────────────────

    def _build_divider(self, column: int = 1):
        """
        Inserta el divisor arrastrable.
        column=1 → divisor izquierdo del sidebar (sincronizado entre módulos)
        column=3 → divisor derecho del panel de preview
        """
        is_left = (column == 1)

        if is_left:
            # Leer ancho guardado o usar default
            from core.config import load_config
            if not hasattr(self.app, '_shared_sb_width'):
                self.app._shared_sb_width = load_config("sidebar_width", SIDEBAR_DEFAULT)
            self._sb_width = self.app._shared_sb_width
            self.grid_columnconfigure(0, minsize=self._sb_width, weight=0)
            self.grid_columnconfigure(1, minsize=DIV_WIDTH, weight=0)
            if not hasattr(self, '_right_panel_exists'):
                self.grid_columnconfigure(2, weight=1)
        else:
            # Divisor derecho — columna pasada como argumento
            if not hasattr(self.app, '_shared_preview_width'):
                from core.config import load_config
                self.app._shared_preview_width = load_config("preview_width", 280)
            self._preview_width = self.app._shared_preview_width
            self._right_panel_exists = True
            self.grid_columnconfigure(2, weight=1)          # centro se expande
            self.grid_columnconfigure(column, minsize=DIV_WIDTH, weight=0)
            self.grid_columnconfigure(column + 1, minsize=self._preview_width, weight=0)

        div = ctk.CTkFrame(
            self, fg_color=DIV_COLOR, width=DIV_WIDTH,
            corner_radius=0, cursor="sb_h_double_arrow",
        )
        div.grid(row=0, column=column, sticky="nsew")
        div.grid_propagate(False)
        div.bind("<Enter>", self._div_enter)
        div.bind("<Leave>", self._div_leave)
        div.bind("<Button-1>", self._div_start)
        div.bind("<B1-Motion>", self._div_drag)
        div.bind("<ButtonRelease-1>", self._div_release)
        self._div = div
        self._drag_x = 0

    # ── Métodos del divisor (unificados, soportan col 1 y col 3) ────────────────

    def _div_press(self, event, div, column):
        self._divs[column]["drag_x"] = event.x_root
        div.configure(fg_color=DIV_COLOR_HOVER)

    def _div_move(self, event, div, column):
        info   = self._divs[column]
        delta  = event.x_root - info["drag_x"]
        info["drag_x"] = event.x_root

        if column == 1:   # sidebar izquierdo
            new_w = max(SIDEBAR_MIN, min(SIDEBAR_MAX, self._sb_width + delta))
            if new_w != self._sb_width:
                self._sb_width = new_w
                self.grid_columnconfigure(0, minsize=new_w)
        else:             # panel preview derecho
            new_w = max(150, min(500, self._preview_width - delta))
            if new_w != self._preview_width:
                self._preview_width = new_w
                self.grid_columnconfigure(column + 1, minsize=new_w)

    def _div_up(self, event, div, column):
        div.configure(fg_color=DIV_COLOR)
        from core.config import save_config
        if column == 1:
            self.app._shared_sb_width = self._sb_width
            save_config("sidebar_width", self._sb_width)
            if hasattr(self.app, '_modules'):
                for mod in self.app._modules.values():
                    if mod is not self and hasattr(mod, '_sb_width'):
                        mod._sb_width = self._sb_width
                        mod.grid_columnconfigure(0, minsize=self._sb_width)
        else:
            self.app._shared_preview_width = self._preview_width
            save_config("preview_width", self._preview_width)

    # ── backwards compat stubs ────────────────────────────────────────────────
    def _div_enter(self, _=None):   self._div.configure(fg_color=DIV_COLOR_HOVER)
    def _div_leave(self, _=None):   self._div.configure(fg_color=DIV_COLOR)
    def _div_start(self, e):        self._drag_x = e.x_root
    def _div_drag(self, e):         self._div_move(e, self._div, 1)
    def _div_release(self, _=None): self._div_up(None, self._div, 1)

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
