# =============================================================================
# build.ps1 - Prism Distributable Builder
# Genera una carpeta dist\Prism\ completamente autocontenida con Python embebido
# =============================================================================

$ErrorActionPreference = "Stop"

# --- CONFIGURACION ---
$PY_VERSION  = "3.11.9"
$PY_ZIP_URL  = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-embed-amd64.zip"
$PY_ZIP      = "$env:TEMP\python-embed.zip"
$GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
$GET_PIP     = "$env:TEMP\get-pip.py"

$ROOT   = $PSScriptRoot
$DIST   = Join-Path $ROOT "dist\Prism"
$PY_DIR = Join-Path $DIST "python"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  PRISM BUILD SCRIPT" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# --- PASO 1: Limpiar build anterior ---
Write-Host "[1/8] Limpiando build anterior..." -ForegroundColor Yellow
if (Test-Path $DIST) { Remove-Item $DIST -Recurse -Force }
New-Item -ItemType Directory -Path $DIST -Force | Out-Null
New-Item -ItemType Directory -Path $PY_DIR -Force | Out-Null
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 2: Descargar Python embebido ---
Write-Host "[2/8] Descargando Python $PY_VERSION embebido..." -ForegroundColor Yellow
if (-not (Test-Path $PY_ZIP)) {
    Invoke-WebRequest -Uri $PY_ZIP_URL -OutFile $PY_ZIP -UseBasicParsing
}
Write-Host "      Extrayendo..." -ForegroundColor Gray
Expand-Archive -Path $PY_ZIP -DestinationPath $PY_DIR -Force
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 3: Activar site-packages en Python embebido ---
Write-Host "[3/8] Activando importaciones en Python embebido..." -ForegroundColor Yellow
$pthFile = Get-ChildItem -Path $PY_DIR -Filter "python*._pth" | Select-Object -First 1
if (-not $pthFile) { throw "No se encontro el archivo ._pth en $PY_DIR" }
$pthContent = Get-Content $pthFile.FullName
$pthContent = $pthContent -replace "#import site", "import site"
if ($pthContent -notcontains "import site") {
    $pthContent = $pthContent + "import site"
}
if ($pthContent -notcontains "Lib") {
    $pthContent = @("python311.zip", ".", "Lib", "Lib\site-packages", "import site")
}
Set-Content -Path $pthFile.FullName -Value $pthContent
Write-Host "      Parcheado: $($pthFile.Name)" -ForegroundColor Gray

# --- PASO 4: Instalar pip ---
Write-Host "[4/8] Instalando pip en Python embebido..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $GET_PIP_URL -OutFile $GET_PIP -UseBasicParsing
$pyExe = Join-Path $PY_DIR "python.exe"
& $pyExe $GET_PIP --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "Error instalando pip" }
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 5: Instalar dependencias ---
Write-Host "[5/8] Instalando dependencias (puede tardar 10-20 min)..." -ForegroundColor Yellow
Write-Host "      PyTorch con CUDA y Whisper son pesados - ten paciencia." -ForegroundColor Gray
$pipExe = Join-Path $PY_DIR "Scripts\pip.exe"
$reqFile = Join-Path $ROOT "requirements.txt"
& $pipExe install -r $reqFile --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "Error instalando dependencias" }
Write-Host "      OK" -ForegroundColor Gray

# --- PASO 6: Copiar archivos de la app ---
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

# --- PASO 7: Copiar herramientas externas y modelo AI ---
Write-Host "[7/8] Copiando FFmpeg, Poppler, Tesseract, modelo Whisper y U2NET..." -ForegroundColor Yellow
$extItems = @("ffmpeg", "poppler", "Tesseract-OCR", "small.pt", ".u2net")
foreach ($item in $extItems) {
    $src = Join-Path $ROOT $item
    # Fallback para Tesseract si no está en la raíz
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

# --- PASO 8: Crear lanzador VBScript (sin ventana negra) ---
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

$pythonw = Join-Path $PY_DIR "pythonw.exe"
if (Test-Path $pythonw) {
    Write-Host "  [OK] pythonw.exe encontrado - lanzador listo" -ForegroundColor Green
}
else {
    Write-Host "  [AVISO] pythonw.exe no encontrado en $PY_DIR" -ForegroundColor Red
}
Write-Host ""
