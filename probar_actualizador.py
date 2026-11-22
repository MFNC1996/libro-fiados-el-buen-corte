# -*- coding: utf-8 -*-
"""
Prueba del actualizador, contra un GitHub de mentira.

    python probar_actualizador.py

Comprueba lo que de verdad importa: que reconozca cuando hay una version
nueva, que no se confunda comparando numeros, que baje el archivo completo y
que avise con palabras entendibles cuando algo falla.
"""
import json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actualizador as A

fallas = []
def check(nombre, cond):
    print(("  ok   " if cond else "FALLA ") + nombre)
    if not cond:
        fallas.append(nombre)


ESTADO = {"version": "9.9.9", "con_instalador": True, "tope": False,
          "instalador": b"x" * (2 * 1024 * 1024)}


class GitHubFalso(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.endswith("/releases/latest"):
            if ESTADO["tope"]:
                self.send_response(403)
                self.send_header("x-ratelimit-remaining", "0")
                self.end_headers()
                return self.wfile.write(b'{"message":"rate limit"}')
            assets = []
            if ESTADO["con_instalador"]:
                assets = [{"name": A.ARCHIVO, "size": len(ESTADO["instalador"]),
                           "browser_download_url": URL + "/bajar"}]
            cuerpo = json.dumps({"tag_name": "v" + ESTADO["version"],
                                 "body": "Arregla lo del monto",
                                 "assets": assets}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            return self.wfile.write(cuerpo)
        if self.path == "/bajar":
            self.send_response(200)
            self.send_header("Content-Length", str(len(ESTADO["instalador"])))
            self.end_headers()
            return self.wfile.write(ESTADO["instalador"])
        self.send_response(404)
        self.end_headers()


servidor = HTTPServer(("127.0.0.1", 0), GitHubFalso)
threading.Thread(target=servidor.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d" % servidor.server_port
A.REPO = "local/prueba"
A._api_de_verdad = A._api
A._api = lambda url: A._api_de_verdad(URL + "/releases/latest")

print("--- comparar versiones ---")
check("1.10.0 es mas nueva que 1.9.0", A.comparar("1.10.0", "1.9.0") == 1)
check("2.0.0 es mas nueva que 1.99.99", A.comparar("2.0.0", "1.99.99") == 1)
check("la misma es la misma", A.comparar("2.1.0", "2.1.0") == 0)
check("no se confunde con la v adelante", A.comparar("v2.1.0", "2.1.0") == 0)
check("2.1 cuenta igual que 2.1.0", A.comparar("2.1", "2.1.0") == 0)
check("una vieja es vieja", A.comparar("2.0.0", "2.1.0") == -1)

print("\n--- buscar la ultima version ---")
info = A.ultima_version()
check("trae la version sin la v", info["version"] == "9.9.9")
check("trae las notas", "monto" in info["notas"])
check("trae el instalador", info["url"].endswith("/bajar"))
hay, info = A.hay_nueva("2.1.0")
check("avisa que hay una nueva", hay is True)
hay, info = A.hay_nueva("9.9.9")
check("si es la misma, no avisa", hay is False)
hay, info = A.hay_nueva("10.0.0")
check("si la de aqui es mas nueva, tampoco", hay is False)

print("\n--- una version sin instalador no se ofrece ---")
ESTADO["con_instalador"] = False
hay, info = A.hay_nueva("1.0.0")
check("no se ofrece actualizar a algo que no se puede instalar", hay is False)
ESTADO["con_instalador"] = True

print("\n--- bajar el instalador ---")
pasos = []
ruta = A.descargar(URL + "/bajar", avisar=lambda hecho, total: pasos.append((hecho, total)),
                   destino=os.path.join(tempfile.mkdtemp(), "setup.exe"))
check("quedo el archivo", os.path.exists(ruta))
check("completo", os.path.getsize(ruta) == len(ESTADO["instalador"]))
check("fue avisando como iba", len(pasos) > 1 and pasos[-1][0] == len(ESTADO["instalador"]))
check("y sabia cuanto pesaba", pasos[-1][1] == len(ESTADO["instalador"]))

print("\n--- un archivo a medias no se instala ---")
ESTADO["instalador"] = b"x" * 100
try:
    A.descargar(URL + "/bajar", destino=os.path.join(tempfile.mkdtemp(), "corto.exe"))
    check("avisa que llego incompleta", False)
except A.ErrorDeActualizacion as e:
    check("avisa que llego incompleta", "incompleta" in str(e))
ESTADO["instalador"] = b"x" * (2 * 1024 * 1024)

print("\n--- cuando GitHub dice que esperemos ---")
ESTADO["tope"] = True
try:
    A.ultima_version()
    check("lo explica en vez de mostrar un error feo", False)
except A.ErrorDeActualizacion as e:
    check("lo explica en vez de mostrar un error feo", "más tarde" in str(e))
    check("y aclara que el programa sigue andando", "sigue funcionando" in str(e))
ESTADO["tope"] = False

print("\n--- sin internet ---")
A._api = lambda url: A._api_de_verdad("http://127.0.0.1:1/releases/latest")
try:
    A.ultima_version()
    check("avisa que no hay conexion", False)
except A.ErrorDeActualizacion as e:
    check("avisa que no hay conexion", "conexión" in str(e) or "conexion" in str(e))

print("\n--- fuera de Windows no se instala sola ---")
try:
    A.instalar("/tmp/loquesea.exe")
    check("lo dice claramente", False)
except A.ErrorDeActualizacion as e:
    check("lo dice claramente", "Windows" in str(e))

print("\n--- el instalador se lanza como corresponde ---")
lanzados = []
A.se_puede_instalar = lambda: True
import subprocess
original = subprocess.Popen
subprocess.Popen = lambda cmd, **kw: lanzados.append(cmd)
A.instalar("C:\\\\temp\\\\setup.exe")
subprocess.Popen = original
check("en silencio", "/SILENT" in lanzados[0])
check("sin reiniciar el computador", "/NORESTART" in lanzados[0])
check("y pidiendole que vuelva a abrir el programa", "/ABRIR=1" in lanzados[0])

print()
servidor.shutdown()
if fallas:
    print("FALLARON %d PRUEBAS:" % len(fallas))
    for f in fallas:
        print("  - " + f)
    sys.exit(1)
print("Todo bien.")
