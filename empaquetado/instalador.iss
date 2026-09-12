; Inno Setup: genera LibroDeFiados-Setup.exe
; Instala la aplicacion, crea accesos directos y deja un desinstalador.

#define Nombre    "Libro de Fiados"
#define Version   "1.2.1"
#define Empresa   "Macoem"
#define Ejecutable "LibroDeFiados.exe"

[Setup]
AppId={{4F2C9A71-8D3E-4B6A-A1C5-6E9B3D7F2A48}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher={#Empresa}
DefaultDirName={autopf}\LibroDeFiados
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
DisableDirPage=no
OutputDir=..\salida
OutputBaseFilename=LibroDeFiados-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Sin exigir administrador: instala para el usuario actual si no hay permisos.
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
UninstallDisplayName={#Nombre}
UninstallDisplayIcon={app}\{#Ejecutable}
SetupIconFile=icono.ico
; Si el programa esta abierto al actualizar, se le pide cerrarlo.
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el Escritorio"; \
  GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\{#Ejecutable}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LEEME.txt";          DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#Nombre}";              Filename: "{app}\{#Ejecutable}"
Name: "{group}\Desinstalar {#Nombre}";  Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nombre}";        Filename: "{app}\{#Ejecutable}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Ejecutable}"; Description: "Abrir {#Nombre} ahora"; \
  Flags: nowait postinstall skipifsilent

[Messages]
es.WelcomeLabel2=Esto instalara [name/ver] en tu computador.%n%nLos datos (clientes, compras y pagos) se guardan aparte, en tu carpeta de usuario, asi que puedes actualizar la aplicacion sin perder nada de lo anotado.
