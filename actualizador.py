# -*- coding: utf-8 -*-
"""
Busca e instala versiones nuevas, sin que nadie tenga que ir a buscarlas.

La idea es simple: cuando se arregla algo, se publica una version nueva en
GitHub y en el local basta con apretar "Actualizar". El programa:

    1. le pregunta a GitHub cual es la ultima version publicada,
    2. la compara con la que esta corriendo,
    3. descarga el instalador,
    4. lo lanza en silencio y se cierra, para dejarse reemplazar,
    5. el instalador lo vuelve a abrir solo, ya actualizado.

Los datos del local no se tocan nunca: viven aparte, en la carpeta del
usuario, y el instalador no los mira siquiera.

Sin librerias de fuera: solo lo que trae Python.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPO = "MFNC1996/libro-fiados-el-buen-corte"
ARCHIVO = "LibroDeFiados-Setup.exe"      # el instalador publicado en cada version
TIEMPO = 20


class ErrorDeActualizacion(Exception):
    """No se pudo averiguar o bajar la version nueva."""


def comparar(a, b):
    """
    Compara dos versiones por numero, no por letra.

    Asi "1.10.0" es mas nueva que "1.9.0", que alfabeticamente seria al reves.
    Devuelve 1 si a es mas nueva, -1 si es mas vieja, 0 si son la misma.
    """
    def partes(v):
        return [int(n) for n in re.findall(r"\d+", str(v or ""))] or [0]
    pa, pb = partes(a), partes(b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else 0
        y = pb[i] if i < len(pb) else 0
        if x != y:
            return 1 if x > y else -1
    return 0


def _api(url):
    pedido = urllib.request.Request(url)
    pedido.add_header("Accept", "application/vnd.github+json")
    pedido.add_header("User-Agent", "LibroDeFiados-Actualizador")
    try:
        with urllib.request.urlopen(pedido, timeout=TIEMPO) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # GitHub deja consultar sin cuenta, pero con un tope por hora. Si se
        # aprieta "Buscar actualizacion" muchas veces seguidas, responde 403 y
        # el error crudo parece una falla, cuando solo hay que esperar.
        if e.code == 403 and e.headers.get("x-ratelimit-remaining") == "0":
            raise ErrorDeActualizacion(
                "GitHub no deja seguir preguntando por ahora (hay un tope por hora). "
                "Se arregla solo: intenta de nuevo más tarde. El programa sigue "
                "funcionando igual.")
        raise ErrorDeActualizacion("GitHub respondió %s al buscar la última versión."
                                   % e.code)
    except urllib.error.URLError as e:
        raise ErrorDeActualizacion("Sin conexión a internet (%s)." % e.reason)
    except (TimeoutError, OSError, ValueError) as e:
        raise ErrorDeActualizacion("No se pudo preguntar por la última versión (%s)." % e)


def ultima_version():
    """
    La ultima version publicada: {version, notas, url, tamano}.

    url es la del instalador; si la version publicada no trae instalador,
    queda en None y no hay nada que actualizar.
    """
    datos = _api("https://api.github.com/repos/%s/releases/latest" % REPO)
    version = str(datos.get("tag_name") or "").lstrip("vV")
    archivo = next((a for a in datos.get("assets") or []
                    if a.get("name") == ARCHIVO), None)
    return {"version": version,
            "notas": (datos.get("body") or "").strip(),
            "url": (archivo or {}).get("browser_download_url"),
            "tamano": (archivo or {}).get("size") or 0}


def hay_nueva(version_actual):
    """(hay_una_nueva, info). No se cae nunca por falta de internet: avisa."""
    info = ultima_version()
    hay = bool(info["url"]) and comparar(info["version"], version_actual) > 0
    return hay, info


def se_puede_instalar():
    """
    Solo tiene sentido en el Windows del local, con el programa ya instalado.

    Mientras se desarrolla (en un Mac, o corriendo el codigo suelto) se puede
    buscar la version nueva, pero no instalarla.
    """
    return sys.platform.startswith("win") and getattr(sys, "frozen", False)


def descargar(url, avisar=None, destino=None):
    """
    Baja el instalador a una carpeta temporal. Va avisando como va, para poder
    mostrar una barra en vez de dejar la ventana congelada.
    """
    destino = destino or os.path.join(tempfile.gettempdir(), ARCHIVO)
    pedido = urllib.request.Request(url)
    pedido.add_header("User-Agent", "LibroDeFiados-Actualizador")
    try:
        with urllib.request.urlopen(pedido, timeout=TIEMPO) as r:
            total = int(r.headers.get("Content-Length") or 0)
            bajado = 0
            with open(destino, "wb") as f:
                while True:
                    trozo = r.read(64 * 1024)
                    if not trozo:
                        break
                    f.write(trozo)
                    bajado += len(trozo)
                    if avisar:
                        avisar(bajado, total)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorDeActualizacion("No se pudo bajar la actualización (%s)." % e)
    if os.path.getsize(destino) < 1024 * 1024:
        raise ErrorDeActualizacion("La actualización llegó incompleta. Intenta de nuevo.")
    return destino


def instalar(ruta):
    """
    Lanza el instalador y devuelve: el programa tiene que cerrarse enseguida
    para dejarse reemplazar. El instalador lo vuelve a abrir solo cuando
    termina (por eso el /ABRIR=1).
    """
    if not se_puede_instalar():
        raise ErrorDeActualizacion(
            "La actualización automática solo funciona en el programa instalado "
            "en Windows.")
    subprocess.Popen([ruta, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/ABRIR=1"],
                     close_fds=True)
    return True
