# -*- coding: utf-8 -*-
"""
Una sola ventana del programa a la vez.

Si ya esta abierto y alguien le vuelve a dar doble clic, no se abre otro: se
trae al frente el que ya estaba. Dos ventanas sobre la misma base podrian
pisarse los datos (una compra anotada dos veces, por ejemplo).

En Windows se usa un mutex con nombre. El sistema lo suelta solo cuando el
programa se cierra, aunque se cierre mal o se corte la luz, asi que nunca
queda "trabado" impidiendo abrirlo. En otros sistemas (solo para desarrollar)
se usa un candado sobre un archivo, que tambien se suelta solo.
"""
import os
import sys

NOMBRE = "LibroDeFiados_ElBuenCorte_Macoem"
_retenido = []          # mantiene vivo el mutex o el archivo mientras corre


def tomar(carpeta=None):
    """True si esta es la unica ventana abierta; False si ya habia otra."""
    if sys.platform.startswith("win"):
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        h = k32.CreateMutexW(None, False, "Local\\" + NOMBRE)
        ya_habia = ctypes.get_last_error() == 183          # ERROR_ALREADY_EXISTS
        if not h:
            return True        # si Windows no deja crearlo, no se bloquea el programa
        _retenido.append(h)
        return not ya_habia

    import fcntl
    import tempfile
    ruta = os.path.join(carpeta or tempfile.gettempdir(), NOMBRE + ".lock")
    f = open(ruta, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _retenido.append(f)
    return True


def traer_al_frente(titulo):
    """Busca la ventana que ya esta abierta y la pone adelante. True si pudo."""
    if not sys.platform.startswith("win"):
        return False
    import ctypes
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    u32.FindWindowW.restype = ctypes.c_void_p
    u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    hwnd = u32.FindWindowW(None, titulo)
    if not hwnd:
        return False
    u32.ShowWindow(ctypes.c_void_p(hwnd), 9)            # SW_RESTORE: si estaba minimizada
    u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    return True
