"""
Widgets reutilizables compartidos entre módulos.
"""

import os
import re
import customtkinter as ctk
from tkinterdnd2 import DND_FILES
from modules.base_module import (
    BG_CARD, BG_ITEM, BG_DARK, ACCENT, ACCENT_H,
    TEXT_PRI, TEXT_SEC, SUCCESS, DANGER, WARNING, BORDER
)
from core.job_queue import JobStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_drop(data: str) -> list[str]:
    paths = []
    for m in re.finditer(r'\{([^}]+)\}|(\S+)', data):
        p = m.group(1) or m.group(2)
        if p:
            paths.append(p)
    return paths


# ── DropZone ─────────────────────────────────────────────────────────────────

class DropZone(ctk.CTkFrame):
    """
    Zona de arrastrar y soltar. on_files(paths) se llama con la lista de rutas.
    También soporta clic para abrir explorador.
    """

    def __init__(self, master, on_files, extensions: list[str] | None = None,
                 height: int = 110, label: str = "Arrastra archivos aquí", **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10,
                         border_width=2, border_color=BORDER,
                         height=height, **kwargs)
        self.on_files = on_files
        self.extensions = [e.lower() for e in (extensions or [])]
        self.grid_propagate(False)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="📂", font=("Segoe UI", 32)).pack()
        ctk.CTkLabel(inner, text=label,
                     font=("Segoe UI", 13, "bold"), text_color=TEXT_PRI).pack(pady=(2, 0))
        hint = f"o haz clic para buscar"
        if extensions:
            hint = f"Formatos: {', '.join(extensions)}  ·  " + hint
        ctk.CTkLabel(inner, text=hint,
                     font=("Segoe UI", 10), text_color=TEXT_SEC).pack()

        for w in [self, inner] + inner.winfo_children():
            w.bind("<Button-1>", self._browse)

        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._drop)
        self.dnd_bind("<<DragEnter>>", lambda _: self._highlight(True))
        self.dnd_bind("<<DragLeave>>", lambda _: self._highlight(False))

    def _highlight(self, on: bool):
        self.configure(
            border_color=ACCENT if on else BORDER,
            fg_color="#172040" if on else BG_CARD
        )

    def _browse(self, _=None):
        from tkinter import filedialog
        ftypes = [("Archivos", " ".join(f"*{e}" for e in self.extensions))] if self.extensions else [("Todos", "*.*")]
        ftypes.append(("Todos", "*.*"))
        paths = filedialog.askopenfilenames(filetypes=ftypes)
        if paths:
            self.on_files(list(paths))

    def _drop(self, event):
        self._highlight(False)
        paths = parse_drop(event.data)
        if self.extensions:
            paths = [p for p in paths if os.path.splitext(p)[1].lower() in self.extensions]
        if paths:
            self.on_files(paths)


# ── FileListWidget ────────────────────────────────────────────────────────────

class FileListWidget(ctk.CTkFrame):
    """
    Lista reordenable de archivos con botones ▲▼ y ✕.
    on_change() se llama cuando cambia la lista.
    """

    def __init__(self, master, on_change=None, show_pages=False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columnconfigure(0, weight=1)
        self.on_change = on_change
        self.show_pages = show_pages
        self._paths: list[str] = []
        self._build_header()
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                              scrollbar_button_color=BORDER)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._empty_lbl = ctk.CTkLabel(self._scroll, text="Sin archivos",
                                       font=("Segoe UI", 12), text_color=TEXT_SEC)
        self._empty_lbl.grid(row=0, column=0, pady=20)

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        hdr.columnconfigure(0, weight=1)
        self._count_lbl = ctk.CTkLabel(hdr, text="Archivos", font=("Segoe UI", 12, "bold"),
                                       text_color=TEXT_PRI)
        self._count_lbl.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="Limpiar", width=70, height=24,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      text_color=TEXT_SEC, hover_color=BG_ITEM, corner_radius=6,
                      font=("Segoe UI", 11), command=self.clear).grid(row=0, column=1)

    # ── Public ────────────────────────────────────────────────────────────────

    @property
    def paths(self) -> list[str]:
        return list(self._paths)

    def add_files(self, paths: list[str]):
        for p in paths:
            if p not in self._paths:
                self._paths.append(p)
        self._refresh()

    def clear(self):
        self._paths.clear()
        self._refresh()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not self._paths:
            self._empty_lbl = ctk.CTkLabel(self._scroll, text="Sin archivos",
                                           font=("Segoe UI", 12), text_color=TEXT_SEC)
            self._empty_lbl.grid(row=0, column=0, pady=20)
            self._count_lbl.configure(text="Archivos")
        else:
            n = len(self._paths)
            self._count_lbl.configure(text=f"{n} archivo{'s' if n != 1 else ''}")
            for i, path in enumerate(self._paths):
                self._make_item(i, path)

        if self.on_change:
            self.on_change()

    def _make_item(self, idx: int, path: str):
        row = ctk.CTkFrame(self._scroll, fg_color=BG_ITEM, corner_radius=8)
        row.grid(row=idx, column=0, sticky="ew", pady=2, padx=1)
        row.columnconfigure(1, weight=1)

        ctk.CTkLabel(row, text="📄", font=("Segoe UI", 18), width=32,
                     text_color=ACCENT).grid(row=0, column=0, padx=(8, 4), pady=6)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", pady=4)
        info.columnconfigure(0, weight=1)

        name = os.path.basename(path)
        size_kb = os.path.getsize(path) // 1024 if os.path.exists(path) else 0
        extra = f"{size_kb} KB"

        if self.show_pages:
            try:
                from pypdf import PdfReader
                pages = len(PdfReader(path).pages)
                extra = f"{pages} págs  ·  {size_kb} KB"
            except Exception:
                pass

        ctk.CTkLabel(info, text=name, font=("Segoe UI", 12, "bold"),
                     text_color=TEXT_PRI, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(info, text=extra, font=("Segoe UI", 10),
                     text_color=TEXT_SEC, anchor="w").grid(row=1, column=0, sticky="w")

        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.grid(row=0, column=2, padx=(4, 8), pady=6)

        s = dict(width=26, height=26, corner_radius=5, font=("Segoe UI", 11))
        ctk.CTkButton(btns, text="▲", fg_color=BG_CARD, hover_color=BORDER,
                      command=lambda i=idx: self._move(i, -1), **s).pack(side="left", padx=1)
        ctk.CTkButton(btns, text="▼", fg_color=BG_CARD, hover_color=BORDER,
                      command=lambda i=idx: self._move(i, 1), **s).pack(side="left", padx=1)
        ctk.CTkButton(btns, text="✕", fg_color="#4B1C1C", hover_color=DANGER,
                      text_color=DANGER, command=lambda i=idx: self._remove(i), **s).pack(side="left", padx=1)

    def _remove(self, idx: int):
        self._paths.pop(idx)
        self._refresh()

    def _move(self, idx: int, direction: int):
        new = idx + direction
        if 0 <= new < len(self._paths):
            self._paths[idx], self._paths[new] = self._paths[new], self._paths[idx]
            self._refresh()


# ── JobPanel ──────────────────────────────────────────────────────────────────

STATUS_COLOR = {
    JobStatus.PENDING:   TEXT_SEC,
    JobStatus.RUNNING:   ACCENT,
    JobStatus.DONE:      SUCCESS,
    JobStatus.ERROR:     DANGER,
    JobStatus.CANCELLED: WARNING,
}

STATUS_LABEL = {
    JobStatus.PENDING:   "En cola",
    JobStatus.RUNNING:   "Procesando",
    JobStatus.DONE:      "Completado",
    JobStatus.ERROR:     "Error",
    JobStatus.CANCELLED: "Cancelado",
}


class JobPanel(ctk.CTkFrame):
    """Panel lateral/flotante que muestra la cola de trabajos."""

    def __init__(self, master, job_queue, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)
        self.jq = job_queue
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Cola de trabajos", font=("Segoe UI", 13, "bold"),
                     text_color=TEXT_PRI).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="Limpiar", width=60, height=22,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      text_color=TEXT_SEC, hover_color=BG_ITEM, corner_radius=6,
                      font=("Segoe UI", 10),
                      command=lambda: (job_queue.clear_finished(), self.refresh())).grid(row=0, column=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._scroll.columnconfigure(0, weight=1)

        job_queue.on_update(self._schedule_refresh)

    def _schedule_refresh(self):
        try:
            self.after(0, self.refresh)
        except Exception:
            pass

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        jobs = self.jq.get_jobs()
        if not jobs:
            ctk.CTkLabel(self._scroll, text="Sin trabajos",
                         font=("Segoe UI", 11), text_color=TEXT_SEC).grid(row=0, column=0, pady=16)
            return

        for i, job in enumerate(reversed(jobs)):
            card = ctk.CTkFrame(self._scroll, fg_color=BG_ITEM, corner_radius=8)
            card.grid(row=i, column=0, sticky="ew", pady=3)
            card.columnconfigure(0, weight=1)

            color = STATUS_COLOR.get(job.status, TEXT_SEC)
            label = STATUS_LABEL.get(job.status, "")

            ctk.CTkLabel(card, text=job.name, font=("Segoe UI", 11, "bold"),
                         text_color=TEXT_PRI, anchor="w").grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=1, column=0, padx=10, sticky="ew")
            
            ctk.CTkLabel(info_frame, text=label, font=("Segoe UI", 10),
                         text_color=color, anchor="w").pack(side="left")

            if job.status == JobStatus.DONE and isinstance(job.result, str) and os.path.exists(job.result):
                import subprocess
                def open_folder(path=job.result):
                    subprocess.run(['explorer', '/select,', os.path.normpath(path)])
                ctk.CTkButton(info_frame, text="📂 Abrir", width=50, height=20, font=("Segoe UI", 10),
                              fg_color="transparent", hover_color=BORDER, text_color=TEXT_PRI,
                              command=open_folder).pack(side="right", padx=5)

            if job.status == JobStatus.RUNNING:
                bar = ctk.CTkProgressBar(card, height=4, corner_radius=2,
                                         progress_color=ACCENT, fg_color=BORDER)
                bar.grid(row=2, column=0, padx=10, pady=(4, 8), sticky="ew")
                bar.set(job.progress)
            elif job.status == JobStatus.ERROR:
                ctk.CTkLabel(card, text=job.error[:60], font=("Segoe UI", 9),
                             text_color=DANGER, anchor="w", wraplength=200).grid(
                             row=2, column=0, padx=10, pady=(2, 8), sticky="w")
            else:
                ctk.CTkFrame(card, height=8, fg_color="transparent").grid(row=2, column=0)
