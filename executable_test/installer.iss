; Inno Setup 6 Script for CvSU Document Generator
; Packages PyInstaller onedir distribution into a modern per-user setup wizard.

#define MyAppName "CvSU Document Generator"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Cavite State University - CEIT"
#define MyAppURL "https://cvsu.edu.ph"
#define MyAppExeName "CvSU Gen.exe"
#define MyAppIcon "app_icon.ico"

[Setup]
; Unique AppId to manage upgrades/reinstalls cleanly
AppId={{C6285A7E-D24E-4B02-861E-7F899D412F5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\CvSU Gen
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=CvSU_Gen_Setup_v{#MyAppVersion}
SetupIconFile={#MyAppIcon}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Low privileges mode: enables non-admin faculty to install in user space without UAC escalation
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Visual presentation
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Distribute all files from PyInstaller onedir bundle
Source: "dist\CvSU Gen\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Icon resource for uninstaller and shell
Source: "{#MyAppIcon}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcon}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcon}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

