"""
Punto de Entrada Principal (Bootstrap)
Prepara el entorno de ejecución aislando DLLs y variables de entorno antes de 
que Python intente invocar librerías problemáticas. Inicia la interfaz gráfica
CustomTkinter y blinda la app para evitar instancias duplicadas.
"""

import sys
import os
import ctypes

# Evitar múltiples instancias de Prism simultáneas
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Prism_Unique_App_Mutex")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)

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

# --- 2b. INYECCIÓN DE MODELOS DE IA ---
# Hace que remove_bg nunca intente descargar el modelo, usando el nuestro empaquetado.
os.environ["U2NET_HOME"] = os.path.join(_base, ".u2net")

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
    """
    Función de inicialización de la interfaz. Configura la cascada de eventos
    de apagado seguro para matar forzosamente todos los hilos rebeldes 
    (ej. modelos de IA en procesamiento) cuando el usuario cierra la app.
    """
    from ui.shell import PrismShell
    app = PrismShell()
    app.mainloop()

if __name__ == "__main__":
    main()