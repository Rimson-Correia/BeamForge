; Inno Setup script for the BeamForge installer. Run through build_exe.ps1 -Installer,
; which passes AppVersion, AppDir (the built application folder), IconFile and Root.

[Setup]
; AppId identifies the application to Windows for upgrades and uninstall. Never change it.
AppId={{F0F6994E-1C1A-4C50-B15C-70F4D121EE19}
AppName=BeamForge
AppVersion={#AppVersion}
AppPublisher=Rimson Correia
AppPublisherURL=https://github.com/Rimson-Correia/BeamForge
AppSupportURL=https://github.com/Rimson-Correia/BeamForge
DefaultDirName={autopf}\BeamForge
DefaultGroupName=BeamForge
DisableProgramGroupPage=yes
LicenseFile={#Root}\LICENSE
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\BeamForge.exe
OutputDir={#Root}\dist
OutputBaseFilename=BeamForge-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Installs for the current user without administrator rights by default;
; the first page offers "for all users" instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\examples\reference_setup.toml"; DestDir: "{app}\examples"; Flags: ignoreversion
Source: "{#Root}\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\BeamForge"; Filename: "{app}\BeamForge.exe"
Name: "{group}\Uninstall BeamForge"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BeamForge"; Filename: "{app}\BeamForge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BeamForge.exe"; Description: "{cm:LaunchProgram,BeamForge}"; Flags: nowait postinstall skipifsilent
