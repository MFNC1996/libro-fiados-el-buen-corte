# Abre la aplicacion en Windows y fotografia sus pantallas principales.
# Se usa en la compilacion, para poder revisar la interfaz sin tener un
# Windows a mano. No forma parte del programa que se instala.
param([string]$Exe = "dist\LibroDeFiados.exe",
      [string]$Destino = "capturas")

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$codigo = @'
using System;
using System.Runtime.InteropServices;
public class Raton {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(
    uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
  public static void Clic(int x, int y) {
    SetCursorPos(x, y);
    mouse_event(0x0002, 0, 0, 0, 0);   // boton izquierdo abajo
    mouse_event(0x0004, 0, 0, 0, 0);   // boton izquierdo arriba
  }
}
'@
Add-Type -TypeDefinition $codigo

New-Item -ItemType Directory -Force -Path $Destino | Out-Null

function Fotografiar($nombre) {
    $a = [System.Windows.Forms.SystemInformation]::VirtualScreen.Width
    $h = [System.Windows.Forms.SystemInformation]::VirtualScreen.Height
    $bmp = New-Object System.Drawing.Bitmap $a, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
    $bmp.Save("$PWD\$Destino\$nombre.png",
              [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Host "  capturada: $nombre"
}

function Teclas($texto, $espera = 2) {
    [System.Windows.Forms.SendKeys]::SendWait($texto)
    Start-Sleep -Seconds $espera
}

# La pantalla de carga dura unos 3 segundos; para fotografiarla sin apuro se
# alarga solo en esta prueba.
$env:LIBRO_PRESENTACION_SEGUNDOS = "14"
$p = Start-Process -FilePath $Exe -PassThru
Start-Sleep -Seconds 7
Fotografiar "0-cargando"
Start-Sleep -Seconds 12
if ($p.HasExited) {
    Write-Error "La aplicacion se cerro sola (codigo $($p.ExitCode))."
    exit 1
}
Write-Host "La app siguio abierta: arranca bien."
$env:LIBRO_PRESENTACION_SEGUNDOS = $null

# La ventana se centra sola; un clic en la cabecera la trae al frente sin
# tocar ningun boton. Despues todo se hace con el teclado, que no depende de
# donde quede cada cosa.
$ancho = [System.Windows.Forms.SystemInformation]::PrimaryMonitorSize.Width
[Raton]::Clic([int]($ancho / 2), 75)
Start-Sleep -Seconds 1
Fotografiar "1-resumen"

Teclas "^b" 1
Teclas "Juan{ENTER}"             # un solo resultado: Enter abre su hoja
Fotografiar "2-hoja-del-cliente"

Teclas "Chuleta vetada 1 kg{ENTER}" 1
Teclas "12990" 1
Fotografiar "3-anotando"
Teclas "{ENTER}"
Fotografiar "4-anotado"

Teclas "^r"
Teclas "30000" 1                 # abona 30 mil
Fotografiar "5-abonar"
Teclas "{ESC}" 1

Teclas "^n"
Fotografiar "6-nuevo-cliente"
Teclas "{ESC}" 1

Teclas "^b" 1
Teclas "Carlos{ENTER}"
Fotografiar "7-deuda-antigua"

Teclas "{ESC}"
Fotografiar "8-resumen-actualizado"

# Una sola ventana: abrirlo otra vez no debe abrir un segundo programa.
$antes = @(Get-Process -Name LibroDeFiados -ErrorAction SilentlyContinue).Count
$otra = Start-Process -FilePath $Exe -PassThru
Start-Sleep -Seconds 12
$despues = @(Get-Process -Name LibroDeFiados -ErrorAction SilentlyContinue).Count
if (-not $otra.HasExited) {
    Write-Error "Se abrio una segunda ventana del programa."
    exit 1
}
if ($despues -ne $antes) {
    Write-Error "Habia $antes procesos y quedaron $despues."
    exit 1
}
Write-Host "Una sola ventana: la segunda vez no abrio otra ($antes procesos antes y despues)."
Fotografiar "10-sigue-una-sola"

Get-Process -Name LibroDeFiados -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
