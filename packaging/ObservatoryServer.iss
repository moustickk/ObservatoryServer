; Installateur d'ObservatoryServer.
;
; Compilation :
;   packaging\build_installer.cmd
; ou
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\ObservatoryServer.iss
;
; Produit dist\ObservatoryServer-Setup-<version>.exe
;
; Principe : le programme va dans Program Files, les donnees dans
; %ProgramData%\ObservatoryServer (cree ici avec des droits d'ecriture pour
; les utilisateurs, sinon l'application non elevatee ne pourrait pas y
; ecrire). Le demarrage automatique est un raccourci dans le dossier
; Demarrage de l'utilisateur, pas une tache planifiee ni un service : l'acces
; COM/ASCOM exige la session interactive.

#define MyAppName "ObservatoryServer"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Observatoire"
#define MyAppExeName "ObservatoryServer.exe"
#define MyAppId "{{6E2A7C41-9B3D-4F18-8E52-7D4A1C0B5F93}"

#ifndef Priv
  #define Priv "admin"
#endif

#ifndef OutSuffix
  #define OutSuffix ""
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} alpha
AppPublisher={#MyAppPublisher}
VersionInfoVersion=3.0.0.0
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired={#Priv}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=ObservatoryServer-Setup-{#MyAppVersion}{#OutSuffix}
SetupIconFile=..\assets\observatory.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes

; Le raccourci de demarrage va dans le profil de l'utilisateur qui installe.
; En installation « pour tous les utilisateurs », c'est le profil elevé —
; donc le meme compte dans le cas normal (un seul operateur). L'avertissement
; d'Inno vise le cas d'un administrateur qui installerait pour un autre
; utilisateur ; ce n'est pas la situation visée ici.
UsedUserAreasWarning=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"
Name: "autostart"; Description: "Demarrer a l'ouverture de session"; GroupDescription: "Demarrage :"; Flags: checkedonce
Name: "firewall"; Description: "Ouvrir le port 11111 dans le pare-feu (Alpaca)"; GroupDescription: "Reseau :"; Flags: checkedonce

[Dirs]
; Le programme tourne sans droits administrateur : il doit pouvoir ecrire
; dans son dossier de donnees. En installation par utilisateur (test, ou
; poste sans admin), on laisse l'application creer ses dossiers elle-meme.
Name: "{commonappdata}\{#MyAppName}"; Permissions: users-modify; Check: IsAdminInstallMode
Name: "{commonappdata}\{#MyAppName}\config"; Permissions: users-modify; Check: IsAdminInstallMode
Name: "{commonappdata}\{#MyAppName}\logs"; Permissions: users-modify; Check: IsAdminInstallMode
Name: "{commonappdata}\{#MyAppName}\state"; Permissions: users-modify; Check: IsAdminInstallMode

[Files]
Source: "..\dist\ObservatoryServer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Interface web"; Filename: "http://localhost:11111/ui/"
Name: "{group}\Desinstaller {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""ObservatoryServer (Alpaca)"" dir=in action=allow protocol=TCP localport=11111 profile=private,domain"; Flags: runhidden; Tasks: firewall; Check: IsAdminInstallMode

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""ObservatoryServer (Alpaca)"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"

[UninstallDelete]
; Les donnees (%ProgramData%) sont conservees : configuration, journaux et
; etat du toit survivent a une desinstallation. A supprimer a la main.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
