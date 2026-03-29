"""
Módulo de Identificación de Backend (Núcleo)
Gestiona la detección y enlace dinámico de herramientas externas instaladas
en el sistema (como FFmpeg) y evalúa las capacidades de hardware de la máquina,
como la disponibilidad de códecs GPU para aceleración de video.
"""

import os
import sys
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class BackendStatus:
    """
    Estructura de datos inmutable que almacena el estado y las capacidades
    de los motores de procesamiento multimedia detectados.
    """
    ffmpeg: bool = False
    ffmpeg_version: str = ""
    gpu_codec: str = "libx264"

    def summary_lines(self) -> list[str]:
        """
        Genera un informe visual resumido de la salud del backend.
        
        Returns:
            list[str]: Lista de cadenas aptas para renderizarse en la Interfaz Gráfica.
        """
        lines = []
        if self.ffmpeg:
            v = f" {self.ffmpeg_version}" if self.ffmpeg_version else ""
            lines.append(f"FFmpeg{v} ✓")
        if not lines:
            lines.append("Solo Python (sin herr. ext.)")
        return lines


def _run(cmd: list[str]) -> str:
    """
    Ejecutor silencioso de subprocesos. Envuelve las llamadas al sistema operativo
    ocultando la persistente ventana de consola negra (cmd.exe) en sistemas Windows.
    
    Args:
        cmd (list[str]): Comando y argumentos a ejecutar.
        
    Returns:
        str: Salida combinada (STDOUT + STDERR) de la ejecución, o cadena vacía en error.
    """
    try:
        cf = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=cf)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def _inject_local_binaries():
    """
    Inyecta las carpetas binarias locales (FFmpeg y Poppler) en el PATH 
    del sistema temporal que consume la aplicación durante su ejecución,
    garantizando que las herramientas sean detectables sin configuración manual del usuario.
    """
    if getattr(sys, 'frozen', False):
        # Soporte nativo para Nuitka y entorno embebido compilado
        base_path = os.path.dirname(sys.executable)
    else:
        # Modo desarrollo (ej. VS Code)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Rutas absolutas a inyectar en memoria
    local_paths = [
        os.path.join(base_path, "ffmpeg", "bin"),
        os.path.join(base_path, "poppler", "bin")
    ]

    current_path = os.environ.get("PATH", "")
    for p in local_paths:
        if os.path.exists(p) and p not in current_path:
            os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]


def check_backends() -> BackendStatus:
    """
    Explora el entorno de ejecución, valida la integridad funcional de 
    FFmpeg e interroga los codificadores disponibles buscando soporte nativo 
    de hardware (NVIDIA, AMD, o Intel).
    
    Returns:
        BackendStatus: Semáforo estructural con las capacidades detectadas.
    """
    # 1. Aseguramos que los binarios locales están en el PATH
    _inject_local_binaries()

    s = BackendStatus()

    if shutil.which("ffmpeg"):
        s.ffmpeg = True
        out = _run(["ffmpeg", "-version"])
        for line in out.splitlines():
            if "version" in line:
                parts = line.split("version ")
                if len(parts) > 1:
                    s.ffmpeg_version = parts[1].split(" ")[0]
                break
        
        # Detección heurística de aceleración por hardware (GPU)
        encoders = _run(["ffmpeg", "-encoders"])
        if "h264_nvenc" in encoders:
            s.gpu_codec = "h264_nvenc" # Hardware NVIDIA detectado
        elif "h264_amf" in encoders:
            s.gpu_codec = "h264_amf"   # Hardware AMD detectado
        elif "h264_qsv" in encoders:
            s.gpu_codec = "h264_qsv"   # Aceleración iGPU Intel detectada

    return s