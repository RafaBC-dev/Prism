# =============================================================================
# build.ps1 - Prism Distributable Builder
# Genera una carpeta dist\Prism\ completamente autocontenida con Python embebido.
# El resultado es una instalación portátil: no requiere que el usuario tenga
# Python ni ninguna dependencia instalada en su PC.
# =============================================================================

# Si cualquier comando falla, el script se detiene inmediatamente en lugar de
# continuar silenciosamente con un estado roto.
$ErrorActionPreference = "Stop"

# --- CONFIGURACION ---
# Versión de Python embebido que se descargará. Cambiar aquí para actualizar.
$PY_VERSION = "3.11.9"
# URL del zip oficial de Python embebido para Windows 64-bit.
$PY_ZIP_URL  = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"
# Ruta temporal donde se guarda el zip descargado (se reutiliza si ya existe).
$PY_ZIP      = "$env:TEMP\python-embed.zip"
# URL del instalador oficial de pip (el gestor de paquetes de Python).
$GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
# Ruta temporal donde se guarda get-pip.py.
$GET_PIP     = "$env:TEMP\get-pip.py"
# Ruta de Python 3.11.9 instalado en el sistema, necesario para copiar tkinter.
# Debe coincidir EXACTAMENTE con $PY_VERSION para que _tkinter.pyd sea compatible.
$SYS_PY      = "C:\Python311"

# $PSScriptRoot es la carpeta donde está este propio script (raíz del proyecto).
$ROOT   = $PSScriptRoot
# Carpeta de salida final: aquí quedará todo el build listo para empaquetar.
$DIST   = Join-Path $ROOT "dist\Prism"
# Subcarpeta donde vivirá el intérprete Python embebido.
$PY_DIR = Join-Path $DIST "python"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  PRISM BUILD SCRIPT" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# --- PASO 1: Limpiar build anterior ---
# Borramos la carpeta dist\Prism\ completa para evitar que archivos obsoletos
# de builds anteriores contaminen el nuevo build.
Write-Host "[1/8] Limpiando build anterior..." -ForegroundColor Yellow
if (Test-Path $DIST) { Remove-Item $DIST -Recurse -Force }
New-Item -ItemType Directory -Path $DIST -Force | Out-Null
New-Item -ItemType Directory -Path $PY_DIR -Force | Out-Null
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 2: Descargar Python embebido ---
# Python embebido es un zip oficial de python.org que contiene el intérprete
# completo sin instalador. Es lo que hace que la app funcione en cualquier PC
# sin que el usuario tenga que instalar Python manualmente.
# El zip se cachea en $env:TEMP para no descargarlo en cada build.
Write-Host "[2/8] Descargando Python $PY_VERSION embebido..." -ForegroundColor Yellow
if (-not (Test-Path $PY_ZIP)) {
    Invoke-WebRequest -Uri $PY_ZIP_URL -OutFile $PY_ZIP -UseBasicParsing
}
Write-Host "      Extrayendo..." -ForegroundColor Gray
Expand-Archive -Path $PY_ZIP -DestinationPath $PY_DIR -Force
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 3: Activar site-packages en Python embebido ---
# El Python embebido viene con las importaciones de librerías externas DESACTIVADAS
# por defecto (para ser lo más minimalista posible). Hay un archivo ._pth que
# controla los paths de importación. Necesitamos:
#   1. Descomentar "import site" para activar site-packages.
#   2. Añadir "Lib" y "Lib\site-packages" explícitamente, porque el embebido no
#      los incluye por defecto y sin ellos no encuentra módulos copiados manualmente
#      como tkinter.
Write-Host "[3/8] Activando importaciones en Python embebido..." -ForegroundColor Yellow
$pthFile = Get-ChildItem -Path $PY_DIR -Filter "python*._pth" | Select-Object -First 1
if (-not $pthFile) { throw "No se encontro el archivo ._pth en $PY_DIR" }
$pthContent = Get-Content $pthFile.FullName
$pthContent = $pthContent -replace "#import site", "import site"
if ($pthContent -notcontains "import site") {
    $pthContent = $pthContent + "import site"
}
if ($pthContent -notcontains "Lib") {
    $pthContent = $pthContent + "Lib"
}
if ($pthContent -notcontains "Lib\site-packages") {
    $pthContent = $pthContent + "Lib\site-packages"
}
Set-Content -Path $pthFile.FullName -Value $pthContent
Write-Host "      Parcheado: $($pthFile.Name)" -ForegroundColor Gray

# --- PASO 4: Instalar pip ---
# El Python embebido tampoco incluye pip. Lo instalamos descargando get-pip.py
# y ejecutándolo con el propio Python embebido. A partir de aquí ya podemos
# usar pip para instalar cualquier librería dentro de este Python aislado.
Write-Host "[4/8] Instalando pip en Python embebido..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $GET_PIP_URL -OutFile $GET_PIP -UseBasicParsing
$pyExe = Join-Path $PY_DIR "python.exe"
& $pyExe $GET_PIP --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "Error instalando pip" }
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 5: Instalar dependencias ---
# Instalamos todas las librerías del proyecto (customtkinter, rembg, whisper, etc.)
# usando el pip que acabamos de instalar. Todo queda dentro de dist\Prism\python\
# completamente aislado del Python del sistema. Por eso tarda tanto: descarga e
# instala PyTorch, CUDA, Whisper y todo lo demás desde cero.
Write-Host "[5/8] Instalando dependencias (puede tardar 10-20 min)..." -ForegroundColor Yellow
Write-Host "      PyTorch con CUDA y Whisper son pesados - ten paciencia." -ForegroundColor Gray
$pipExe = Join-Path $PY_DIR "Scripts\pip.exe"
$reqFile = Join-Path $ROOT "requirements.txt"
& $pipExe install -r $reqFile --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "Error instalando dependencias" }
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 6: Copiar archivos de la app ---
# Copiamos el código fuente de Prism a dist\Prism\. Solo los archivos necesarios
# para ejecutar la app, no los de desarrollo (tests, scripts, etc.).
Write-Host "[6/8] Copiando archivos de la aplicacion..." -ForegroundColor Yellow
$appItems = @("core", "modules", "ui", "main.py", "config.json", "icon.ico", "icon.png")
foreach ($item in $appItems) {
    $src = Join-Path $ROOT $item
    $dst = Join-Path $DIST $item
    if (Test-Path $src) {
        if (Test-Path $src -PathType Container) {
            Copy-Item $src $dst -Recurse -Force
        }
        else {
            Copy-Item $src $dst -Force
        }
        Write-Host "      Copiado: $item" -ForegroundColor Gray
    }
    else {
        Write-Host "      AVISO: No encontrado: $item" -ForegroundColor Magenta
    }
}

# --- PASO 7: Copiar herramientas externas y modelos de IA ---
# Copiamos las herramientas binarias y modelos que la app necesita en tiempo
# de ejecucion y que no se pueden instalar via pip:
#   - ffmpeg:        conversion de audio y video
#   - poppler:       renderizado de PDFs (usado por pdf2image)
#   - Tesseract-OCR: motor de reconocimiento optico de caracteres
#   - small.pt:      modelo de Whisper para transcripcion de audio
#   - .u2net:        modelo u2net de rembg para eliminar fondos con IA
# Si Tesseract no esta en la raiz del proyecto, hace fallback a la instalacion
# global de Program Files.
Write-Host "[7/8] Copiando FFmpeg, Poppler, Tesseract, modelo Whisper y U2NET..." -ForegroundColor Yellow
$extItems = @("ffmpeg", "poppler", "Tesseract-OCR", "small.pt", ".u2net")
foreach ($item in $extItems) {
    $src = Join-Path $ROOT $item
    if ($item -eq "Tesseract-OCR" -and -not (Test-Path $src)) {
        $src = "C:\Program Files\Tesseract-OCR"
    }

    $dst = Join-Path $DIST $item
    if (Test-Path $src) {
        if (Test-Path $src -PathType Container) {
            Copy-Item $src $dst -Recurse -Force
        }
        else {
            Copy-Item $src $dst -Force
        }
        Write-Host "      Copiado: $item" -ForegroundColor Gray
    }
    else {
        Write-Host "      AVISO: No encontrado: $item" -ForegroundColor Magenta
    }
}

# --- PASO 7b: Copiar tkinter y Tcl/Tk desde Python 3.11 del sistema ---
# El Python embebido no incluye tkinter ni las librerias Tcl/Tk que necesita.
# Los copiamos desde la instalacion 3.11.9 del sistema ($SYS_PY), que debe
# coincidir exactamente con la version embebida para que _tkinter.pyd sea compatible.
#
# IMPORTANTE - por que usamos \* en vez de copiar la carpeta directamente:
# Copy-Item con una carpeta como destino la anida dentro si el destino ya existe
# (tkinter -> tkinter\tkinter). Usando \* copiamos el CONTENIDO, no la carpeta.
# Por eso creamos el directorio destino antes con New-Item.
#
# Los archivos Tcl/Tk van en dist\Prism\lib\ (no en python\tcl\) porque es la
# ruta donde _tkinter.pyd los busca al inicializarse, segun el error que lanza
# si no los encuentra: "Can't find a usable init.tcl in ... dist\Prism\lib\tcl8.6"
Write-Host "      Copiando tkinter y Tcl/Tk desde Python 3.11..." -ForegroundColor Gray

# 1. Modulo Python de tkinter (el codigo .py)
New-Item -ItemType Directory -Path "$PY_DIR\Lib\tkinter" -Force | Out-Null
Copy-Item "$SYS_PY\Lib\tkinter\*" "$PY_DIR\Lib\tkinter\" -Recurse -Force

# 2. DLLs nativas: _tkinter.pyd va en la raiz de python\ (no en DLLs\)
#    porque el Python embebido busca los .pyd en el mismo directorio que python.exe
Copy-Item "$SYS_PY\DLLs\_tkinter.pyd" "$PY_DIR\" -Force
Copy-Item "$SYS_PY\DLLs\tcl86t.dll"   "$PY_DIR\" -Force
Copy-Item "$SYS_PY\DLLs\tk86t.dll"    "$PY_DIR\" -Force

# 3. Librerias de scripting de Tcl/Tk en dist\Prism\lib\ (ruta que busca _tkinter)
New-Item -ItemType Directory -Path "$DIST\lib\tcl8.6" -Force | Out-Null
New-Item -ItemType Directory -Path "$DIST\lib\tk8.6"  -Force | Out-Null
Copy-Item "$SYS_PY\tcl\tcl8.6\*" "$DIST\lib\tcl8.6\" -Recurse -Force
Copy-Item "$SYS_PY\tcl\tk8.6\*"  "$DIST\lib\tk8.6\"  -Recurse -Force

Write-Host "      tkinter y Tcl/Tk copiados OK" -ForegroundColor Gray

# --- PASO 8: Crear lanzador VBScript (sin ventana negra) ---
# Si lanzaramos main.py directamente con python.exe apareceria una ventana negra
# de consola detras de la app. Para evitarlo usamos pythonw.exe (la variante
# silenciosa de Python) y lo invocamos desde un VBScript con oShell.Run ... 0
# (el 0 significa "ventana oculta"). El script calcula su propia ruta en tiempo
# de ejecucion para que funcione independientemente de donde este instalada la app.
Write-Host "[8/8] Creando lanzador sin consola..." -ForegroundColor Yellow
$vbsLines = @(
    'Set oShell = CreateObject("WScript.Shell")',
    'strDir = Replace(WScript.ScriptFullName, WScript.ScriptName, "")',
    'strPy  = strDir & "python\pythonw.exe"',
    'strApp = strDir & "main.py"',
    'oShell.Run Chr(34) & strPy & Chr(34) & " " & Chr(34) & strApp & Chr(34), 0, False'
)
$vbsDest = Join-Path $DIST "Prism.vbs"
Set-Content -Path $vbsDest -Value $vbsLines -Encoding UTF8
Write-Host "      Creado: Prism.vbs" -ForegroundColor Gray

# =============================================================================
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETADO SIN ERRORES" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Carpeta distribuible: $DIST" -ForegroundColor White
Write-Host ""
Write-Host "  SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "  Abre Inno Setup y compila setup_prism.iss" -ForegroundColor White
Write-Host "  El instalador aparecera en: installer_output" -ForegroundColor White
Write-Host ""

# Verificacion final: comprobamos que pythonw.exe existe en el build.
# Si no esta, el lanzador .vbs y los accesos directos del instalador no funcionaran.
$pythonw = Join-Path $PY_DIR "pythonw.exe"
if (Test-Path $pythonw) {
    Write-Host "  [OK] pythonw.exe encontrado - lanzador listo" -ForegroundColor Green
}
else {
    Write-Host "  [AVISO] pythonw.exe no encontrado en $PY_DIR" -ForegroundColor Red
}
Write-Host ""
