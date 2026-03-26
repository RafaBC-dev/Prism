[Setup]
AppName=Prism
AppVersion=1.0
DefaultDirName={autopf}\Prism
DefaultGroupName=Prism
UninstallDisplayIcon={app}\Prism.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.\installer_output
OutputBaseFilename=Prism_v1.0_Setup
SetupIconFile=C:\Users\rafae\Desktop\Prism\icon.ico

[Files]
; 1. El ejecutable y las librerías que generó PyInstaller
Source: "C:\Users\rafae\Desktop\Prism\dist\Prism\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

; 2. Los binarios externos que Prism necesita para funcionar
Source: "C:\Users\rafae\Desktop\Prism\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs
Source: "C:\Users\rafae\Desktop\Prism\poppler\*"; DestDir: "{app}\poppler"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Prism"; Filename: "{app}\Prism.exe"
Name: "{commondesktop}\Prism"; Filename: "{app}\Prism.exe"

[Run]
Filename: "{app}\Prism.exe"; Description: "Lanzar Prism ahora"; Flags: nowait postinstall skipifsilent