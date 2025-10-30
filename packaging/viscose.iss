; Inno Setup script to install Viscose CLI
; Build with: iscc packaging/viscose.iss

#define AppName "Viscose Benchmarks"
#define AppVersion "0.1.0"
#define Publisher "Viscose"

[Setup]
AppId={{5E3D7B5E-84C2-45E8-9B30-2E5C64A0F7C2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={pf}\Viscose
DefaultGroupName={#AppName}
OutputDir=dist
OutputBaseFilename=viscose-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64
ChangesEnvironment=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; NOTE: Adjust the source path to your built executable if needed
Source: "..\dist\viscose.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Viscose"; Filename: "{app}\viscose.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Viscose"; Filename: "{app}\viscose.exe"; Tasks: desktopicon

[Registry]
; Append install folder to the system PATH
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Flags: preservestringtype

[Run]
; Launch a new console session to refresh PATH (optional)
Filename: "{app}\viscose.exe"; Description: "Run Viscose"; Flags: nowait postinstall skipifsilent
