import sys
import os

# --- 1. PARCHE DE SEGURIDAD PARA DLLs ---
if hasattr(os, 'add_dll_directory'):
    is_frozen = getattr(sys, 'frozen', False)
    base_dir = os.path.dirname(sys.executable) if is_frozen else os.path.dirname(os.path.abspath(__file__))
    os.add_dll_directory(base_dir)
    for sub in ['onnxruntime', 'onnxruntime/capi', 'torch/lib']:
        path = os.path.join(base_dir, sub.replace('/', os.sep))
        if os.path.isdir(path):
            os.add_dll_directory(path)

# --- 2. INYECCIÓN NATIVA DE HERRAMIENTAS (FFmpeg y Poppler) ---
# Esto hace que pdf2image encuentren las herramientas sin VBS ni variables de entorno
_base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = os.path.join(_base, "ffmpeg", "bin") + os.pathsep + os.environ["PATH"]
os.environ["PATH"] = os.path.join(_base, "poppler", "Library", "bin") + os.pathsep + os.environ["PATH"]

# --- FIX: Evitar crash "NoneType object has no attribute 'write'" en pythonw.exe (ia, print) ---
class DummyWriter:
    def write(self, x): pass
    def flush(self): pass
if sys.stdout is None: sys.stdout = DummyWriter()
if sys.stderr is None: sys.stderr = DummyWriter()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def main():
    from ui.shell import PrismShell
    app = PrismShell()

    # --- 3. KILL SWITCH (Cierre perfecto) ---
    def on_closing():
        app.destroy()
        os._exit(0) # Aniquila la RAM y los hilos de la IA al instante
        
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()

if __name__ == "__main__":
    main()