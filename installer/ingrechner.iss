; Inno-Setup-Skript für den Ingenieurs-Rechner
;
; Bauen (nach "pyinstaller ingrechner.spec"):
;   iscc /DAppVersion=0.5.0 installer\ingrechner.iss
; Ergebnis: dist\installer\Ingenieurs-Rechner-Setup-<Version>.exe
;
; Stille Installation (z. B. Softwareverteilung):
;   Ingenieurs-Rechner-Setup-x.y.z.exe /VERYSILENT /SUPPRESSMSGBOXES /ALLUSERS
;   (/CURRENTUSER = nur für den angemeldeten Benutzer, ohne Administratorrechte)

#define AppName "Ingenieurs-Rechner"
#define AppExe "Ingenieurs-Rechner.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Die AppId darf sich nie ändern – sonst werden Updates als neues Programm installiert.
AppId={{CED6D8DE-0288-46B4-874B-8DE5693DA2F7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Installation ohne Administratorrechte möglich; im Dialog wählbar "für alle Benutzer"
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=Ingenieurs-Rechner-Setup-{#AppVersion}
SetupIconFile=..\ingrechner\resources\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc"; Description: "Projektdateien (.irp) und Protokolle (.irpk) mit dem {#AppName} öffnen"; GroupDescription: "Dateizuordnung:"

[InstallDelete]
; Reste einer älteren Version entfernen (Bibliotheken ändern sich zwischen Versionen)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Ingenieurs-Rechner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Projektdateien .irp
Root: HKA; Subkey: "Software\Classes\.irp"; ValueType: string; ValueName: ""; ValueData: "IngRechner.Projekt"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.irp\OpenWithProgids"; ValueType: string; ValueName: "IngRechner.Projekt"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\IngRechner.Projekt"; ValueType: string; ValueName: ""; ValueData: "Ingenieurs-Rechner Projekt"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\IngRechner.Projekt\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\IngRechner.Projekt\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc
; Besprechungsprotokolle .irpk
Root: HKA; Subkey: "Software\Classes\.irpk"; ValueType: string; ValueName: ""; ValueData: "IngRechner.Protokoll"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.irpk\OpenWithProgids"; ValueType: string; ValueName: "IngRechner.Protokoll"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\IngRechner.Protokoll"; ValueType: string; ValueName: ""; ValueData: "Ingenieurs-Rechner Besprechungsprotokoll"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\IngRechner.Protokoll\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\IngRechner.Protokoll\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
