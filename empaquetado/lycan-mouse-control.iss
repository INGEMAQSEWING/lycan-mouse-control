; Instalador de Lycan Mouse Control (modelo: installer\edwin-cnc-3d.iss de EDWIN CNC 3D).
;
; En la nube: .github\workflows\windows.yml
; A mano:     iscc /DMyAppVersion=1.0.0 empaquetado\lycan-mouse-control.iss
;             (sin /DMyAppVersion compila igual como version 0.0.0)
;
; El AppId es FIJO: no cambiarlo nunca, o Windows toma cada version como otro programa.

#define MyAppName "Lycan Mouse Control"
#define MyAppPublisher "Lycan Developments"
#define MyAppExeName "LycanMouseControl.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
; VersionInfoVersion solo acepta numeros (a.b.c.d). El workflow pasa /DMyAppVersionNum con la
; parte numerica cuando la version trae algo como "1.1.0-beta".
#ifndef MyAppVersionNum
  #define MyAppVersionNum MyAppVersion
#endif

[Setup]
AppId={{05FDCE37-EFA7-4182-B127-C765607E7C41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersionNum}
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
; LZMA2 solido: la carpeta de ~211 MB queda en un instalador de ~56-60 MB.
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
spanish.BorrarConfig=¿Desea borrar también su configuración (calibración, sensibilidad y atajos) y los registros de errores?%n%nSi va a volver a instalar Lycan Mouse Control, elija No para conservarlos.

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

; La configuracion y los registros viven en %APPDATA%\Lycan Mouse Control ({userappdata}).
; NO se borran sin preguntar: ver [Code] (por defecto se conservan).

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent

[Code]
// Al desinstalar: borrar SIEMPRE el arranque con Windows (tambien si lo activo el programa
// desde Opciones, que Inno no conoce) y preguntar si se borra la configuracion
// (por defecto se conserva).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Carpeta: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    if RegValueExists(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'LycanMouseControl') then
      RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'LycanMouseControl');
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    Carpeta := ExpandConstant('{userappdata}\Lycan Mouse Control');
    if DirExists(Carpeta) and (not UninstallSilent) then
    begin
      if MsgBox(CustomMessage('BorrarConfig'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Carpeta, True, True, True);
    end;
  end;
end;
