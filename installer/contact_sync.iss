; Inno Setup 6.3 or newer. Build with:  python build_exe.py   (it runs PyInstaller, then this script)
; Do not change AppId: Windows uses it to recognize the same program when a new version is installed.

#define AppName "Contact Sync"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppExe "ContactSync.exe"
#define AppPublisher "ArabianDeveloper"
#define AppURL "https://github.com/ArabianDeveloper/contact_sync"

[Setup]
AppId={{AD98CD95-D778-48F0-94AB-94BDDCA83D45}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=ContactSync-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\ContactSync\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

; The data of the user (settings, saved mappings, Google sign-in, logs) is in %APPDATA%\ContactSync
; and is NOT deleted when the program is uninstalled.
