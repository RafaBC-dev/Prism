import os
import sys
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class BackendStatus:
    ffmpeg: bool = False
    ffmpeg_version: str = ""
    gpu_codec: str = "libx264"
    libreoffice: bool = False
    libreoffice_cmd: str = ""
    pandoc: bool = False
    pandoc_version: str = ""

    def summary_lines(self) -> list[str]:
        lines = []
        if self.ffmpeg:
            v = f" {self.ffmpeg_version}" if self.ffmpeg_version else ""
            lines.append(f"FFmpeg{v} ✓")
        if self.libreoffice:
            lines.append("LibreOffice ✓")
        if self.pandoc:
            v = f" {self.pandoc_version}" if self.pandoc_version else ""
            lines.append(f"Pandoc{v} ✓")
        if not lines:
            lines.append("Solo Python (sin herr. ext.)")
        return lines


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def _inject_local_binaries():
    """Inyecta las carpetas bin/ locales en el PATH del sistema para esta ejecución."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # Sube un nivel desde 'core' a la raíz del proyecto
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Rutas a inyectar
    local_paths = [
        os.path.join(base_path, "ffmpeg", "bin"),
        os.path.join(base_path, "poppler", "bin")  # Ya que estamos, cubrimos Poppler también
    ]

    current_path = os.environ.get("PATH", "")
    for p in local_paths:
        if os.path.exists(p) and p not in current_path:
            os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]


def check_backends() -> BackendStatus:
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
        # Detección de GPU
        encoders = _run(["ffmpeg", "-encoders"])
        if "h264_nvenc" in encoders:
            s.gpu_codec = "h264_nvenc" # NVIDIA
        elif "h264_amf" in encoders:
            s.gpu_codec = "h264_amf"   # AMD
        elif "h264_qsv" in encoders:
            s.gpu_codec = "h264_qsv"   # Intel

    for cmd in ("libreoffice", "soffice", "libreoffice7.6", "libreoffice7.5"):
        if shutil.which(cmd):
            s.libreoffice = True
            s.libreoffice_cmd = cmd
            break

    if shutil.which("pandoc"):
        s.pandoc = True
        out = _run(["pandoc", "--version"])
        if out:
            s.pandoc_version = out.splitlines()[0].split()[-1]

    return s