# Prism: Professional File Processing & Format Management

**Repository:** [https://github.com/RafaBC-dev/Prism.git](https://github.com/RafaBC-dev/Prism.git)

## 1. Descripción General
Prism es una estación de trabajo modular desarrollada en Python y orientada al procesamiento masivo de activos digitales en entorno local. La aplicación centraliza herramientas avanzadas de manipulación de datos, edición multimedia y procesamiento de documentos mediante una arquitectura desacoplada que garantiza la privacidad del usuario al ejecutar toda la lógica *on-premise*.

## 2. Arquitectura del Sistema
El proyecto sigue una estructura modular para facilitar la escalabilidad y el mantenimiento:

* **`main.py`**: Punto de entrada de la aplicación.
* **`core/`**: Motor interno que gestiona la configuración (`config.py`), la detección de hardware (`backend.py`), la validación de archivos (`detector.py`) y la gestión de tareas asíncronas (`job_queue.py`).
* **`modules/`**: Segmentación de lógica de negocio por dominios (PDF, Documentos, Hojas de cálculo, Imágenes, Audio y Vídeo).
* **`ui/`**: Interfaz gráfica implementada con CustomTkinter, dividida en el marco principal (`shell.py`) y componentes reutilizables (`widgets.py`).

## 3. Capacidades Técnicas por Módulo

### 📊 Hojas de Cálculo (Pandas Engine)
* **Procesamiento Vectorizado**: Filtrado, limpieza y normalización de datasets masivos en formatos CSV, XLSX y ODS.
* **Operaciones de Datos**: Fusión de múltiples fuentes de datos y exportación optimizada a formatos industriales como JSON o Excel.

### 🔊 Audio & Inteligencia Artificial
* **Neural Transcription**: Integración del modelo **OpenAI Whisper** para la conversión de voz a texto con procesamiento local.
* **Procesamiento de Señal**: Extracción de audio desde contenedores de vídeo, conversión de formatos, recorte temporal y ajuste de ganancia mediante FFmpeg.

### 🎬 Vídeo & Multimedia
* **FFmpeg Wrapper**: Reescalado de resolución (4K, 1080p, 720p), normalización de audio bajo estándar EBU R128 e incrustación de subtítulos hardcoded.
* **Optimización**: Generación de GIFs de alta fidelidad con gestión optimizada de paleta de colores.

### 📄 Documentos & PDF
* **Manipulación Estructural**: Unión, división y conversión universal entre formatos PDF, DOCX, MD y TXT.

### 🖼️ Procesamiento de Imagen
* **Background Removal**: Eliminación de fondos mediante modelos preentrenados (Rembg) sin latencia de red ni dependencia de APIs externas.

## 4. Requisitos del Sistema
El funcionamiento óptimo de Prism requiere las siguientes dependencias externas:

* **Python 3.10+**
* **FFmpeg**: Binarios necesarios para la codificación y manipulación multimedia.
* **Poppler**: Requerido para la gestión y renderización de archivos PDF.
* **Hardware**: Se recomienda el uso de una GPU compatible con CUDA para acelerar la ejecución de modelos de IA (Whisper).

## 5. Instalación y Despliegue (Modo Desarrollo)

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/RafaBC-dev/Prism.git
   ```

2. Instalar las dependencias de Python en un entorno virtual:
   ```bash
   pip install -r requirements.txt
   ```

3. Ejecutar la aplicación:
   ```bash
   python main.py
   ```

## 6. Generación del Instalador (.exe)

Prism ha abandonado la compilación nativa (Nuitka) en favor de una **distribución embebida de Python 3.11** mucho más robusta y rápida. Para empaquetarlo:

1. **Recolección:** Ejecuta el script `build.ps1` en PowerShell. Este descargará automáticamente Python embebido, las herramientas precompiladas FFmpeg y Poppler, resolverá `tkinter`, y clonará todas las librerías necesarias dentro de la carpeta aislada `dist\Prism`.
2. **Setup:** Abre `setup_prism.iss` usando **Inno Setup 6**.
3. **Compilar:** Presiona **F9** en Inno Setup. El instalador profesional listo para distribuir se generará en la carpeta `installer_output/`.

---
*Desarrollado por RafaBC-dev*