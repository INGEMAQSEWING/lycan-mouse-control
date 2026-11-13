; Instalador de Lycan Mouse Control (modelo: installer\edwin-cnc-3d.iss de EDWIN CNC 3D).
;
; En la nube: .github\workflows\lycan-mouse-windows.yml
; A mano:     iscc /DMyAppVersion=1.0.0 empaquetado\lycan-mouse-control.iss
;
; El AppId es FIJO: no cambiarlo nunca, o Windows toma cada version como otro programa.

#define MyAppName "Lycan Mouse Control"
#define MyAppPublisher "Lycan Developments"
#define MyAppExeName "LycanMouseControl.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{05FDCE37-EFA7-4182-B127-C765607E7C41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Lycan Mouse Control - maneje el raton con las manos
VersionInfoProductName={#MyAppName}

; Instalacion para el usuario actual, SIN pedir permiso de administrador
; (va a C:\Users\<usuario>\AppData\Local\Programs\Lycan Mouse Control).
; Si en el dialogo elige "para todos los usuarios", va a Program Files y pide administrador.
DefaultDirName={autopf}\Lycan Mouse Control
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes

OutputDir=..\dist
OutputBaseFilename=Lycan-Mouse-Control-{#MyAppVersion}-Windows-64-bits

WizardStyle=modern
ShowLanguageDialog=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; LZMA2 solido: la carpeta de ~199 MB queda en un instalador de ~56 MB.
Compression=lzma2/max
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; Cierra el programa si esta abierto al actualizar o desinstalar
; (si no, Windows no deja reemplazar los archivos en uso).
CloseApplications=force
RestartApplications=no
#if FileExists(AddBackslash(SourcePath) + "..\recursos\lycan-mouse.ico")
SetupIconFile=..\recursos\lycan-mouse.ico
#endif

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
spanish.Inicio=Abrir Lycan Mouse Control al encender el computador
spanish.Opciones=Opciones:

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "inicio"; Description: "{cm:Inicio}"; GroupDescription: "{cm:Opciones}"; Flags: unchecked

[InstallDelete]
; Al actualizar, borrar la carpeta interna anterior para no mezclar DLL viejas.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\LycanMouseControl\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Arranque con Windows (solo si marca la casilla). El programa siempre arranca en PAUSA.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "LycanMouseControl"; \
    ValueData: """{app}\{#MyAppExeName}"" --minimizado"; \
    Tasks: inicio; Flags: uninsdeletevalue

[UninstallDelete]
; Ajustes y registro del usuario (calibracion, sensibilidad, log).
Type: filesandordirs; Name: "{localappdata}\Lycan Mouse Control"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent
