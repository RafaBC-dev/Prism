"""
Módulo de Configuración Base
Gestiona las preferencias persistentes del usuario a través de un archivo JSON 
aislado en el directorio del sistema. Garantiza que los ajustes sobrevivan entre 
ejecuciones de Prism.
"""

import os
import json

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".prism")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Valores por defecto de la aplicación
DEFAULT_CONFIG = {
    "theme": "Dark",          # Dark, Light, System
    "close_to_tray": False,   # Minimizar en vez de cerrar
    "notifications": True     # Avisos Toast de Windows
}

_current_config = None

def _get_config_path() -> str:
    """Obtiene y garantiza la existencia estructural del directorio base."""
    # Usamos la carpeta del perfil de usuario (~/.prism/config.json)
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    return CONFIG_FILE

def load_config() -> dict:
    """
    Carga la configuración desde el disco o inicializa una nueva si no existe.
    Fusiona claves nuevas faltantes de DEFAULT_CONFIG automáticamente.
    
    Returns:
        dict: Diccionario en memoria con las configuraciones actuales.
    """
    global _current_config
    if _current_config is not None:
        return _current_config

    path = _get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Fusionamos con los defaults por si hay claves nuevas tras una actualización
                _current_config = {**DEFAULT_CONFIG, **data}
        except Exception:
            _current_config = DEFAULT_CONFIG.copy()
    else:
        _current_config = DEFAULT_CONFIG.copy()
        save_config(_current_config)  # Creamos el primer archivo

    return _current_config

def save_config(new_config: dict):
    """
    Sobrescribe el archivo config.json con las nuevas claves de diccionaro suministradas.
    
    Args:
        new_config (dict): Diccionario actualizado para volcar a disco.
    """
    global _current_config
    _current_config = new_config
    path = _get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_current_config, f, indent=4)
    except Exception:
        pass

def get(key: str, default=None):
    """
    Obtiene un valor específico del gestor de configuración en memoria.
    
    Args:
        key (str): Nombre de la propiedad a recuperar.
        default (Any): Valor devuelto si la clave no existe.
    """
    return load_config().get(key, default)

def set(key: str, value):
    """
    Inserta o actualiza un valor puntual en memoria y guarda forzosamente a disco.
    
    Args:
        key (str): Propiedad a sobreescribir.
        value (Any): Nuevo valor que persistir.
    """
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
