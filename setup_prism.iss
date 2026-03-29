; =============================================================================
; setup_prism.iss — Prism Installer Script (Inno Setup)
; Empaqueta la carpeta dist\Prism\ generada por build.ps1
; =============================================================================

[Setup]
AppName=Prism
AppVersion=1.0
AppPublisher=RafaBC-dev
AppPublisherURL=https://github.com/RafaBC-dev/Prism
DefaultDirName={autopf}\Prism
DefaultGroupName=Prism
UninstallDisplayIcon={app}\icon.ico
Compression=lzma2/fast
SolidCompression=no
OutputDir=C:\Users\rafae\Desktop\Prism\installer_output
OutputBaseFilename=Prism_v1.0_Setup
SetupIconFile=C:\Users\rafae\Desktop\Prism\icon.ico
; Requiere Windows 10 o superior (necesario para Python 3.11)
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; Toda la carpeta distribuible (Python embebido + app + herramientas)
Source: "C:\Users\rafae\Desktop\Prism\dist\Prism\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Instalar el modelo Whisper en la cache del usuario
Source: "C:\Users\rafae\Desktop\Prism\dist\Prism\small.pt"; DestDir: "{%USERPROFILE}\.cache\whisper"; Flags: ignoreversion

[Icons]
; Acceso directo en el menú inicio
Name: "{group}\Prism"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"

; Acceso directo en el escritorio
Name: "{commondesktop}\Prism"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"

[Run]
; Ofrecer lanzar la app al terminar de instalar
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; Description: "Lanzar Prism ahora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpiar archivos generados durante el uso de la app
Type: filesandordirs; Name: "{app}\__pycache__"