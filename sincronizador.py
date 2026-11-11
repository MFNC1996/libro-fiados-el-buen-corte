# -*- coding: utf-8 -*-
"""
Mantiene el libro igual en el computador del local y en el celular.

Como funciona, en simple:

    1. Sube lo que se anoto aqui y todavia no esta en internet.
    2. Baja lo que cambio alla desde la ultima vez.
    3. Espera unos segundos y vuelve a empezar.

Todo esto corre en segundo plano, aparte de la ventana: si no hay internet,
el programa sigue funcionando igual y lo pendiente se sube cuando vuelva.

No usa librerias de fuera: solo lo que trae Python, para que el .exe siga
siendo un archivo chico y la compilacion no dependa de nadie.
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import nucleo as N

# ---------------------------------------------------------------------------
#  El servidor del local. Estos tres datos son publicos a proposito: la llave
#  "anon" no abre nada por si sola. La base de datos solo entrega los datos del
#  local al que pertenece el usuario que inicio sesion, y para eso hay que
#  entrar con correo y clave. La llave secreta (service_role) no esta aqui ni
#  en ninguna otra parte del programa.
# ---------------------------------------------------------------------------
URL = "https://zczlopvgnfwghlaykmph.supabase.co"
ANON = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpj"
        "emxvcHZnbmZ3Z2hsYXlrbXBoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk1MjM4NzUsImV4"
        "cCI6MjEwNTA5OTg3NX0.Nf4ZEI1bOM8Mhfxz6xI0bqM2SeH3ZI_vCWxknCuC_Ek")
LOCAL_ID = "ce58ba0c-aedd-47ad-8ea1-b42138b05389"

SEGUNDOS_ENTRE_VUELTAS = 10
# Al bajar se pide "lo que cambio desde hace un ratito antes" del ultimo
# cambio conocido: dos filas guardadas en el mismo instante podrian perderse
# si se pidiera exactamente desde ahi. Guardar dos veces la misma fila no
# hace dano, perderla si.
SEGUNDOS_DE_SOLAPE = 2


class ErrorDeNube(Exception):
    """Algo respondio mal el servidor (o no hay internet)."""


def configurar(datos):
    """
    Deja en la base local los datos del servidor, si todavia no estaban.

    Asi el programa recien instalado ya sabe a donde conectarse: en el local
    solo hay que entrar con el correo y la clave del dueno.
    """
    for clave, valor in (("url", URL), ("anon", ANON), ("local_id", LOCAL_ID)):
        if not datos.config(clave):
            datos.guardar_config(clave, valor)


def hay_sesion(datos):
    return bool(datos.config("refresco"))


def entrar(datos, correo, clave):
    """Inicia sesion y deja la sesion guardada para las proximas veces."""
    configurar(datos)
    nube = Nube(datos.config("url"), datos.config("anon"))
    refresco = nube.entrar(correo.strip(), clave)
    datos.guardar_config("refresco", refresco)
    datos.guardar_config("correo", correo.strip())
    return True


def salir(datos):
    datos.guardar_config("refresco", "")


# ------------------------------------------------------------------- usuarios
def _nube_lista(datos):
    """Una conexion con la sesion al dia, para las cosas que se piden al momento."""
    if not hay_sesion(datos):
        raise ErrorDeNube("Primero hay que entrar con la cuenta del local.")
    nube = Nube(datos.config("url") or URL, datos.config("anon") or ANON)
    nuevo = nube.renovar(datos.config("refresco"))
    if nuevo != datos.config("refresco"):
        datos.guardar_config("refresco", nuevo)
    return nube


def usuarios(datos):
    """Quienes pueden entrar al libro de este local."""
    return _nube_lista(datos).rpc("usuarios_del_local") or []


def crear_usuario(datos, correo, clave, rol="ayudante"):
    """
    Crea la cuenta de otra persona y le da acceso al local.

    Lo hace en dos pasos, como corresponde: primero la cuenta (eso lo permite
    cualquiera) y despues el acceso al local, que la base de datos solo deja
    hacer si quien lo pide es el dueno.
    """
    correo = (correo or "").strip()
    if "@" not in correo or "." not in correo.split("@")[-1]:
        raise ErrorDeNube("Ese correo no parece estar bien escrito.")
    if len((clave or "").strip()) < 6:
        raise ErrorDeNube("La clave tiene que tener al menos 6 letras o números.")
    nube = _nube_lista(datos)
    try:
        nube.crear_cuenta(correo, clave)
    except ErrorDeNube as e:
        # Si la cuenta ya existia, seguimos: lo que falta es darle el acceso.
        if "already" not in str(e).lower() and "registered" not in str(e).lower():
            raise
    nube.rpc("agregar_al_local", {"p_correo": correo, "p_rol": rol})
    return True


def dar_acceso(datos, correo, rol="ayudante"):
    """Le da acceso a alguien que ya tiene cuenta."""
    _nube_lista(datos).rpc("agregar_al_local",
                           {"p_correo": (correo or "").strip(), "p_rol": rol})
    return True


def quitar_acceso(datos, correo):
    """Le quita el acceso al local (la cuenta sigue existiendo)."""
    _nube_lista(datos).rpc("quitar_del_local", {"p_correo": (correo or "").strip()})
    return True


# ------------------------------------------------------------------- servidor
class Nube(object):
    """Las llamadas al servidor. No sabe nada de la ventana ni de la base."""

    def __init__(self, url, anon, tiempo=20):
        self.url = (url or "").rstrip("/")
        self.anon = anon or ""
        self.tiempo = tiempo
        self.token = ""          # dura una hora; se renueva solo
        self.refresco = ""

    def _llamar(self, metodo, camino, cuerpo=None, cabeceras=None, con_token=True):
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        pedido = urllib.request.Request(self.url + camino, data=datos, method=metodo)
        pedido.add_header("apikey", self.anon)
        pedido.add_header("Content-Type", "application/json")
        if con_token and self.token:
            pedido.add_header("Authorization", "Bearer " + self.token)
        for k, v in (cabeceras or {}).items():
            pedido.add_header(k, v)
        try:
            with urllib.request.urlopen(pedido, timeout=self.tiempo) as r:
                texto = r.read().decode("utf-8")
            return json.loads(texto) if texto else None
        except urllib.error.HTTPError as e:
            detalle = ""
            try:
                detalle = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise ErrorDeNube("El servidor respondio %s. %s" % (e.code, detalle))
        except urllib.error.URLError as e:
            raise ErrorDeNube("Sin conexion a internet (%s)" % e.reason)
        except (TimeoutError, OSError) as e:
            raise ErrorDeNube("No se pudo hablar con el servidor (%s)" % e)

    # -- entrar ----------------------------------------------------------
    def entrar(self, correo, clave):
        """Inicia sesion con correo y clave. Devuelve el refresco, para guardarlo."""
        r = self._llamar("POST", "/auth/v1/token?grant_type=password",
                         {"email": correo, "password": clave}, con_token=False)
        self.token = (r or {}).get("access_token", "")
        self.refresco = (r or {}).get("refresh_token", "")
        if not self.token:
            raise ErrorDeNube("El correo o la clave no son correctos.")
        return self.refresco

    def renovar(self, refresco=None):
        """Renueva la sesion sin volver a pedir la clave."""
        refresco = refresco or self.refresco
        if not refresco:
            raise ErrorDeNube("No hay sesion guardada: hay que entrar de nuevo.")
        r = self._llamar("POST", "/auth/v1/token?grant_type=refresh_token",
                         {"refresh_token": refresco}, con_token=False)
        self.token = (r or {}).get("access_token", "")
        self.refresco = (r or {}).get("refresh_token", "") or refresco
        if not self.token:
            raise ErrorDeNube("La sesion vencio: hay que entrar de nuevo.")
        return self.refresco

    # -- datos -----------------------------------------------------------
    def bajar(self, tabla, local_id, desde, tope=500):
        """Lo que cambio en el servidor despues de 'desde'."""
        filtros = [("local_id", "eq." + local_id), ("order", "actualizado.asc"),
                   ("limit", str(tope))]
        if desde:
            filtros.append(("actualizado", "gt." + desde))
        camino = "/rest/v1/%s?%s" % (tabla, urllib.parse.urlencode(filtros))
        return self._llamar("GET", camino) or []

    def rpc(self, funcion, argumentos=None):
        """Llama a una funcion de la base de datos (las de usuarios)."""
        return self._llamar("POST", "/rest/v1/rpc/" + funcion, argumentos or {})

    def crear_cuenta(self, correo, clave):
        """Crea una cuenta nueva. No cambia la sesion de quien esta usando el programa."""
        r = self._llamar("POST", "/auth/v1/signup",
                         {"email": correo, "password": clave}, con_token=False)
        return r or {}

    def datos_del_local(self, local_id):
        """La fila del local: de ahi sale la clave de administrador."""
        filas = self._llamar("GET", "/rest/v1/locales?id=eq.%s&select=*" % local_id) or []
        return filas[0] if filas else {}

    def subir(self, tabla, filas):
        """
        Sube filas (las crea o las reemplaza) y devuelve como quedaron, con la
        hora que les puso el servidor.
        """
        if not filas:
            return []
        return self._llamar(
            "POST", "/rest/v1/" + tabla, filas,
            {"Prefer": "resolution=merge-duplicates,return=representation"}) or []


# -------------------------------------------------------------- sincronizador
class Sincronizador(threading.Thread):
    """
    Da vueltas en segundo plano subiendo y bajando cambios.

    Trabaja con su propia conexion a la base (no la de la ventana), asi no se
    pisan. La ventana solo mira 'estado' y 'version' para saber si tiene que
    refrescar lo que muestra.
    """

    def __init__(self, ruta_base, cada=SEGUNDOS_ENTRE_VUELTAS):
        threading.Thread.__init__(self, daemon=True)
        self.ruta_base = ruta_base
        self.cada = cada
        self.version = 0             # sube cada vez que llegan cambios de afuera
        self.estado = {"conectado": False, "ultima": None, "pendientes": 0,
                       "aviso": "Sin configurar"}
        self._parar = threading.Event()
        self._ahora = threading.Event()

    def detener(self):
        self._parar.set()
        self._ahora.set()

    def apurar(self):
        """Se llama despues de anotar algo, para no esperar la vuelta completa."""
        self._ahora.set()

    def run(self):
        datos = N.Datos(self.ruta_base)
        nube = None
        while not self._parar.is_set():
            try:
                nube = self._una_vuelta(datos, nube)
            except ErrorDeNube as e:
                self.estado.update(conectado=False, aviso=str(e))
                nube = None if "sesion" in str(e).lower() else nube
            except Exception as e:                      # nunca se cae la vuelta
                self.estado.update(conectado=False, aviso="Error inesperado: %s" % e)
            self._ahora.wait(self.cada)
            self._ahora.clear()
        datos.cerrar()

    def _una_vuelta(self, datos, nube):
        url = datos.config("url")
        anon = datos.config("anon")
        local_id = datos.config("local_id")
        refresco = datos.config("refresco")
        if not (url and anon and local_id):
            self.estado.update(conectado=False, aviso="Sin configurar")
            return nube
        if nube is None:
            nube = Nube(url, anon)
            nube.refresco = refresco
            nuevo = nube.renovar()
            if nuevo != refresco:
                datos.guardar_config("refresco", nuevo)

        subidas = self._subir(datos, nube, local_id)
        bajadas = self._bajar(datos, nube, local_id)
        self._bajar_la_clave(datos, nube, local_id)
        if bajadas:
            self.version += 1
        self.estado.update(conectado=True, ultima=time.time(),
                           pendientes=datos.hay_pendientes(),
                           aviso="", subidas=subidas, bajadas=bajadas)
        return nube

    def _subir(self, datos, nube, local_id):
        total = 0
        for tabla in N.Datos.TABLAS:
            filas = datos.filas_pendientes(tabla)
            if not filas:
                continue
            for f in filas:
                f["local_id"] = local_id
                f["borrado"] = bool(f["borrado"])
                if "activo" in f:
                    f["activo"] = bool(f["activo"])
            devueltas = nube.subir(tabla, filas)
            datos.olvidar_pendientes(tabla, [f["id"] for f in filas])
            # El servidor devuelve la hora oficial de cada fila: se guarda.
            datos.guardar_de_la_nube(tabla, devueltas)
            total += len(filas)
        return total

    def _bajar_la_clave(self, datos, nube, local_id):
        """Trae la clave de administrador que puso el dueno (su huella)."""
        try:
            local = nube.datos_del_local(local_id)
        except ErrorDeNube:
            return
        if not local:
            return
        huella = local.get("clave_huella", "")
        if huella != datos.config("clave_huella"):
            datos.guardar_huella(huella, local.get("clave_sal", ""),
                                 local.get("clave_vueltas", 0))

    def _bajar(self, datos, nube, local_id):
        total = 0
        for tabla in N.Datos.TABLAS:
            # Se pide por tandas: la primera vez, o despues de estar mucho rato
            # sin internet, puede haber mas filas que las que entran en una.
            for _ in range(50):
                desde = datos.config("desde_" + tabla)
                filas = nube.bajar(tabla, local_id, _con_solape(desde))
                if not filas:
                    break
                total += datos.guardar_de_la_nube(tabla, filas)
                ultima = max(f.get("actualizado", "") for f in filas)
                if ultima and ultima != desde:
                    datos.guardar_config("desde_" + tabla, ultima)
                else:
                    break
                if len(filas) < 500:
                    break
        return total


def poner_clave_admin(datos, clave):
    """
    Pone (o saca, con clave vacia) la clave de administrador del local.

    Solo el dueno puede: lo comprueba la base de datos, no el programa. La
    clave no viaja: viaja su huella.
    """
    clave = (clave or "").strip()
    if clave and len(clave) < 4:
        raise ErrorDeNube("La clave tiene que tener al menos 4 números o letras.")
    nube = _nube_lista(datos)
    if clave:
        huella, sal, vueltas = N.huella_clave(clave)
    else:
        huella, sal, vueltas = "", "", 0
    nube.rpc("poner_clave_admin", {"p_huella": huella, "p_sal": sal, "p_vueltas": vueltas})
    datos.guardar_huella(huella, sal, vueltas)
    return True


def _con_solape(desde):
    """Pide desde un poquito antes, para no saltarse filas del mismo instante."""
    if not desde:
        return ""
    try:
        from datetime import datetime, timedelta, timezone
        t = datetime.strptime(desde[:23], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
        t -= timedelta(seconds=SEGUNDOS_DE_SOLAPE)
        return t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except ValueError:
        return desde
