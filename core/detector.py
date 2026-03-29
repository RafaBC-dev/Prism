"""
Módulo Detector (Enrutador de Extensiones)
Identifica automáticamente el tipo de archivo y lo asocia con su módulo
de procesamiento gráfico (Ej: .pdf -> módulo PDF, .mp4 -> módulo Vídeo).
"""

from pathlib import Path

EXTENSION_MAP = {
    ".pdf": "pdf",
    ".docx": "docs", ".doc": "docs", ".odt": "docs",
    ".txt": "docs", ".md": "docs", ".rtf": "docs",
    ".xlsx": "sheets", ".xls": "sheets", ".csv": "sheets", ".ods": "sheets",
    ".png": "images", ".jpg": "images", ".jpeg": "images",
    ".webp": "images", ".gif": "images", ".bmp": "images",
    ".tiff": "images", ".tif": "images",
    ".mp3": "audio", ".wav": "audio", ".ogg": "audio",
    ".flac": "audio", ".aac": "audio", ".m4a": "audio",
    ".mp4": "video", ".mkv": "video", ".avi": "video",
    ".mov": "video", ".webm": "video", ".wmv": "video",
}

MODULE_ICONS = {
    "pdf":    "📄",
    "docs":   "📝",
    "sheets": "📊",
    "images": "🖼",
    "audio":  "🎵",
    "video":  "🎬",
}

MODULE_NAMES = {
    "pdf":    "PDF",
    "docs":   "Documentos",
    "sheets": "Hojas de cálculo",
    "images": "Imágenes",
    "audio":  "Audio",
    "video":  "Vídeo",
}

MODULE_ORDER = ["pdf", "docs", "sheets", "images", "audio", "video"]


def detect_module(filepath: str) -> str | None:
    """Extrae la extensión de un archivo y devuelve su ID de módulo asociado."""
    ext = Path(filepath).suffix.lower()
    return EXTENSION_MAP.get(ext)


def get_icon(module_id: str) -> str:
    """Obtiene el emoji descriptivo del módulo."""
    return MODULE_ICONS.get(module_id, "📁")


def get_name(module_id: str) -> str:
    """Obtiene el nombre en español del módulo."""
    return MODULE_NAMES.get(module_id, module_id)


def file_info(filepath: str) -> dict:
    """
    Agrupa los metadatos esenciales de un archivo en disco.
    
    Args:
        filepath (str): Ruta absoluta del archivo.
    Returns:
        dict: Objeto estandarizado con nombre, extensión, tamaño y módulo asignado.
    """
    p = Path(filepath)
    size = p.stat().st_size if p.exists() else 0
    return {
        "name": p.name,
        "stem": p.stem,
        "ext": p.suffix.lower(),
        "size_bytes": size,
        "size_str": _fmt_size(size),
        "module": detect_module(filepath),
    }


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"
