# -*- coding: utf-8 -*-
"""
Nucleo del libro de fiados: datos y calculos.

No depende de la interfaz, asi que se puede probar solo. La ventana
(app.py) solo llama a estas funciones.

Como se lleva la cuenta
-----------------------
Cada cliente tiene COMPRAS (lo que se anoto: que llevo y cuanto vale) y
PAGOS (la plata que entrego). Cada pago queda repartido entre compras
concretas, en la tabla "aplicaciones". Asi cada compra sabe cuanto le han
abonado y si esta pendiente, pagada a medias o pagada entera, y el total que
debe el cliente es la suma de lo que le falta a cada compra.

    - "Marcar pagada" una compra crea un pago justo por lo que le faltaba.
    - "Recibir pago" por un monto lo reparte desde la compra mas antigua.
    - "Marcar pendiente" le quita a la compra lo abonado (y achica o borra
      el pago de donde salio). "Deshacer pago" borra el pago entero.
"""

import os
import pathlib
import re
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

NOMBRE_APP = "Libro de Fiados"
NEGOCIO = "Carnicería El Buen Corte"
CIUDAD = "Loncoche"

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

PENDIENTE, PARCIAL, PAGADA = "pendiente", "parcial", "pagada"


# ----------------------------------------------------------------- ubicacion
def carpeta_datos():
    """Los datos viven fuera del .exe, para que actualizarlo no los borre."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.environ.get("XDG_DATA_HOME") or \
            os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    ruta = os.path.join(base, "LibroDeFiados")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# ------------------------------------------------------------------- formatos
def pesos(monto):
    """1234567 -> '$1.234.567'"""
    monto = int(round(monto or 0))
    signo = "-" if monto < 0 else ""
    return signo + "$" + "{:,}".format(abs(monto)).replace(",", ".")


def leer_monto(texto):
    """
    Entiende el monto escrito como venga. Devuelve pesos enteros, o None.

        12500  12.500  $12.500  12 500  -> 12500
        12,5 mil   12 mil   12k        -> 12500 / 12000 / 12000
        8.990,50                        -> 8991  (los centavos se redondean)
    """
    t = str(texto or "").strip().lower().replace("$", "").replace(" ", "")
    if not t:
        return None
    mil = 1
    for sufijo in ("mil", "lucas", "luca", "k"):
        if t.endswith(sufijo):
            t, mil = t[:-len(sufijo)], 1000
            break
    t = t.replace(".", "")
    if t.count(",") > 1:
        return None
    t = t.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d*)?", t or "x"):
        return None
    valor = int(float(t) * mil + 0.5)          # medio peso para arriba, como en caja
    return valor if valor > 0 else None


def leer_fecha(texto, hoy=None):
    """
    Entiende la fecha escrita como venga y la deja en ISO (aaaa-mm-dd).

        (vacio) / hoy   -> hoy            ayer        -> ayer
        7               -> dia 7 de este mes (o del anterior, si aun no llega)
        7/9  7-9  7.9   -> 7 de septiembre (del anio pasado si aun no llega)
        7/9/26  7/9/2026  2026-09-07
        7 de septiembre -> igual que 7/9
        martes          -> el ultimo martes (hoy, si hoy es martes)
        martes 13       -> el ultimo martes 13 que ya paso

    Devuelve None si de verdad no se entiende.
    """
    hoy = hoy or date.today()
    t = _sin_tildes(texto).strip().replace(",", " ")
    if t in ("", "hoy"):
        return hoy.isoformat()
    if t == "ayer":
        return (hoy - timedelta(days=1)).isoformat()
    if t in ("anteayer", "antes de ayer", "antier"):
        return (hoy - timedelta(days=2)).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        a, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _fecha_o_none(a, mes, d)

    # Palabras: el dia de la semana se aparta, y el mes pasa a numero.
    dia_semana = None
    palabras = []
    for p in t.split():
        if p in _DIAS_SIN_TILDE:
            dia_semana = _DIAS_SIN_TILDE.index(p)
        elif p in MESES:
            palabras += ["/", str(MESES.index(p) + 1)]
        elif p not in ("el", "de", "del", "dia", "pasado"):
            palabras.append(p)
    t = " ".join(palabras)

    if not t.strip():
        if dia_semana is None:
            return None
        atras = (hoy.weekday() - dia_semana) % 7          # hoy mismo cuenta
        return (hoy - timedelta(days=atras)).isoformat()

    partes = [p for p in re.split(r"[/\-. ]+", t) if p]
    if not partes or len(partes) > 3 or not all(p.isdigit() for p in partes):
        return None
    nums = [int(p) for p in partes]
    if len(nums) == 1:
        if dia_semana is not None:
            # "martes 13": el ultimo mes en que el 13 cayo martes.
            a, mes = hoy.year, hoy.month
            for _ in range(15):
                f = _fecha_o_none(a, mes, nums[0])
                if f and f <= hoy.isoformat() and \
                        date(a, mes, nums[0]).weekday() == dia_semana:
                    return f
                a, mes = (a, mes - 1) if mes > 1 else (a - 1, 12)
        f = _fecha_o_none(hoy.year, hoy.month, nums[0])
        if f and f > hoy.isoformat():            # el 28 escrito un dia 3: mes pasado
            ant = hoy.replace(day=1) - timedelta(days=1)
            f = _fecha_o_none(ant.year, ant.month, nums[0])
        return f
    if len(nums) == 2:
        f = _fecha_o_none(hoy.year, nums[1], nums[0])
        if f and f > hoy.isoformat():            # el 28/12 escrito en enero
            f = _fecha_o_none(hoy.year - 1, nums[1], nums[0])
        return f
    a = nums[2] + 2000 if nums[2] < 100 else nums[2]
    return _fecha_o_none(a, nums[1], nums[0])


def _fecha_o_none(a, m, d):
    try:
        return date(a, m, d).isoformat()
    except ValueError:
        return None


def fecha_txt(iso):
    """'2026-09-07' -> '07/09/2026'"""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or ""


def fecha_corta(iso, hoy=None):
    """'2026-09-07' -> '07/09' si es de este anio; si no, '07/09/25'."""
    hoy = hoy or date.today()
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
    except (TypeError, ValueError):
        return iso or ""
    return d.strftime("%d/%m" if d.year == hoy.year else "%d/%m/%y")


def fecha_larga(iso):
    """'2026-09-07' -> 'lunes 7 de septiembre de 2026'"""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return iso or ""
    return "%s %d de %s de %d" % (DIAS[d.weekday()], d.day, MESES[d.month - 1], d.year)


def hace_cuanto(iso, hoy=None):
    """Cuantos dias pasaron desde esa fecha, dicho en palabras."""
    hoy = hoy or date.today()
    try:
        d = (hoy - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        return ""
    if d <= 0:
        return "hoy"
    if d == 1:
        return "ayer"
    if d < 60:
        return "hace %d días" % d
    return "hace %d meses" % (d // 30)


def dias_desde(iso, hoy=None):
    hoy = hoy or date.today()
    try:
        return (hoy - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        return 0


def ahora_txt():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ahora_utc():
    """
    La hora en formato universal, que es como la guarda el servidor.

    Se usa para saber que cambio primero cuando el computador y el celular
    anotan casi al mismo tiempo; por eso no puede ser la hora del pais.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def telefono_whatsapp(telefono):
    """
    Numero para abrir WhatsApp, o None. Pensado para Chile:

        9 1234 5678  /  +56 9 1234 5678  /  56912345678  -> 56912345678
    """
    d = "".join(c for c in str(telefono or "") if c.isdigit())
    if len(d) == 8:
        d = "569" + d
    elif len(d) == 9 and d.startswith("9"):
        d = "56" + d
    elif len(d) == 11 and d.startswith("56"):
        pass
    else:
        return None
    return d


# --------------------------------------------------------------------- datos
class Datos(object):
    """
    El libro, guardado en el computador.

    Desde la version 2 cada fila lleva tres cosas mas, para poder compartir el
    libro entre el computador del local y el celular:

        id           un codigo unico (uuid), no un numero corrido. Asi dos
                     dispositivos pueden anotar a la vez sin pisarse.
        actualizado  cuando cambio por ultima vez. Sincronizar es preguntar
                     "dame lo que cambio despues de tal hora".
        borrado      nada se borra de verdad: se marca. Si no, un dispositivo
                     que estuvo sin internet reviviria lo que el otro borro.

    Ademas se anota en "pendientes" cada fila que cambio aqui y todavia no se
    ha subido. El computador sigue funcionando sin internet: anota igual, y
    cuando vuelve la conexion sube lo pendiente.
    """

    TABLAS = ("clientes", "compras", "pagos", "aplicaciones")
    # Lo minimo que tiene que traer una fila nueva que llega del servidor.
    OBLIGATORIAS = {"clientes": ("nombre",),
                    "compras": ("cliente_id", "fecha", "monto"),
                    "pagos": ("cliente_id", "fecha", "monto"),
                    "aplicaciones": ("pago_id", "compra_id", "monto")}

    def __init__(self, ruta=None):
        self.ruta = ruta or os.path.join(carpeta_datos(), "fiados.sqlite3")
        self.cx = sqlite3.connect(self.ruta)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.execute("PRAGMA foreign_keys=ON")
        self.local_id = ""
        self._preparar()
        self.local_id = self.config("local_id", "")

    # -- armado y migracion ----------------------------------------------
    def _preparar(self):
        c = self.cx
        if self._hay_base_vieja():
            self._apartar_base_vieja()
        c.execute("""CREATE TABLE IF NOT EXISTS clientes (
                       id          TEXT    PRIMARY KEY,
                       local_id    TEXT    NOT NULL DEFAULT '',
                       nombre      TEXT    NOT NULL,
                       telefono    TEXT    NOT NULL DEFAULT '',
                       nota        TEXT    NOT NULL DEFAULT '',
                       activo      INTEGER NOT NULL DEFAULT 1,
                       borrado     INTEGER NOT NULL DEFAULT 0,
                       creado      TEXT    NOT NULL DEFAULT '',
                       actualizado TEXT    NOT NULL DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS compras (
                       id          TEXT    PRIMARY KEY,
                       local_id    TEXT    NOT NULL DEFAULT '',
                       cliente_id  TEXT    NOT NULL REFERENCES clientes(id),
                       fecha       TEXT    NOT NULL,
                       detalle     TEXT    NOT NULL DEFAULT '',
                       monto       INTEGER NOT NULL,
                       borrado     INTEGER NOT NULL DEFAULT 0,
                       creado      TEXT    NOT NULL DEFAULT '',
                       actualizado TEXT    NOT NULL DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS pagos (
                       id          TEXT    PRIMARY KEY,
                       local_id    TEXT    NOT NULL DEFAULT '',
                       cliente_id  TEXT    NOT NULL REFERENCES clientes(id),
                       fecha       TEXT    NOT NULL,
                       monto       INTEGER NOT NULL,
                       nota        TEXT    NOT NULL DEFAULT '',
                       borrado     INTEGER NOT NULL DEFAULT 0,
                       creado      TEXT    NOT NULL DEFAULT '',
                       actualizado TEXT    NOT NULL DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS aplicaciones (
                       id          TEXT    PRIMARY KEY,
                       local_id    TEXT    NOT NULL DEFAULT '',
                       pago_id     TEXT    NOT NULL REFERENCES pagos(id),
                       compra_id   TEXT    NOT NULL REFERENCES compras(id),
                       monto       INTEGER NOT NULL,
                       borrado     INTEGER NOT NULL DEFAULT 0,
                       creado      TEXT    NOT NULL DEFAULT '',
                       actualizado TEXT    NOT NULL DEFAULT '')""")
        # Lo que cambio aqui y falta subir.
        c.execute("""CREATE TABLE IF NOT EXISTS pendientes (
                       tabla TEXT NOT NULL,
                       id    TEXT NOT NULL,
                       PRIMARY KEY (tabla, id))""")
        # Ajustes locales: a que local pertenece, hasta donde se sincronizo.
        c.execute("""CREATE TABLE IF NOT EXISTS ajustes (
                       clave TEXT PRIMARY KEY,
                       valor TEXT NOT NULL DEFAULT '')""")
        for t in ("compras", "pagos"):
            c.execute("CREATE INDEX IF NOT EXISTS ix_%s ON %s(cliente_id, fecha)" % (t, t))
        c.execute("CREATE INDEX IF NOT EXISTS ix_apl_compra ON aplicaciones(compra_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_apl_pago ON aplicaciones(pago_id)")
        c.commit()
        self._copiar_base_vieja()

    def _hay_base_vieja(self):
        """True si el archivo es de la version 1 (numeros corridos)."""
        cols = [f[1] for f in self.cx.execute("PRAGMA table_info(clientes)")]
        return bool(cols) and "borrado" not in cols

    def _apartar_base_vieja(self):
        """Las tablas viejas se guardan aparte, para copiarlas y no perderlas."""
        with self.cx:
            for t in self.TABLAS:
                self.cx.execute("ALTER TABLE %s RENAME TO %s_v1" % (t, t))

    def _copiar_base_vieja(self):
        """
        Pasa lo anotado en la version 1 a la forma nueva: a cada fila se le da
        su codigo unico, y queda marcada para subirse a internet la primera vez
        que haya conexion. No se pierde ni una compra.
        """
        if not self.cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='clientes_v1'").fetchone():
            return 0
        if self.config("copiada_la_version_1"):
            return 0
        ahora, copiadas = ahora_utc(), 0
        nuevos = {"clientes": {}, "compras": {}, "pagos": {}}
        with self.cx:
            for v in self.cx.execute("SELECT * FROM clientes_v1 ORDER BY id"):
                nid = self._id()
                nuevos["clientes"][v["id"]] = nid
                self.cx.execute(
                    "INSERT INTO clientes (id, local_id, nombre, telefono, nota, activo, "
                    "creado, actualizado) VALUES (?,?,?,?,?,?,?,?)",
                    (nid, self.local_id, v["nombre"], v["telefono"], v["nota"],
                     v["activo"], _creado_iso(v["creado"]), ahora))
                self._marcar("clientes", nid)
                copiadas += 1
            for v in self.cx.execute("SELECT * FROM compras_v1 ORDER BY id"):
                nid = self._id()
                nuevos["compras"][v["id"]] = nid
                self.cx.execute(
                    "INSERT INTO compras (id, local_id, cliente_id, fecha, detalle, monto, "
                    "creado, actualizado) VALUES (?,?,?,?,?,?,?,?)",
                    (nid, self.local_id, nuevos["clientes"][v["cliente_id"]], v["fecha"],
                     v["detalle"], v["monto"], _creado_iso(v["creado"]), ahora))
                self._marcar("compras", nid)
                copiadas += 1
            for v in self.cx.execute("SELECT * FROM pagos_v1 ORDER BY id"):
                nid = self._id()
                nuevos["pagos"][v["id"]] = nid
                self.cx.execute(
                    "INSERT INTO pagos (id, local_id, cliente_id, fecha, monto, nota, "
                    "creado, actualizado) VALUES (?,?,?,?,?,?,?,?)",
                    (nid, self.local_id, nuevos["clientes"][v["cliente_id"]], v["fecha"],
                     v["monto"], v["nota"], _creado_iso(v["creado"]), ahora))
                self._marcar("pagos", nid)
                copiadas += 1
            for v in self.cx.execute("SELECT * FROM aplicaciones_v1 ORDER BY id"):
                nid = self._id()
                self.cx.execute(
                    "INSERT INTO aplicaciones (id, local_id, pago_id, compra_id, monto, "
                    "creado, actualizado) VALUES (?,?,?,?,?,?,?)",
                    (nid, self.local_id, nuevos["pagos"][v["pago_id"]],
                     nuevos["compras"][v["compra_id"]], v["monto"], ahora, ahora))
                self._marcar("aplicaciones", nid)
                copiadas += 1
        self.guardar_config("copiada_la_version_1", ahora)
        return copiadas

    # -- ajustes y sincronizacion ----------------------------------------
    def config(self, clave, defecto=""):
        f = self.cx.execute("SELECT valor FROM ajustes WHERE clave=?", (clave,)).fetchone()
        return f["valor"] if f else defecto

    def guardar_config(self, clave, valor):
        with self.cx:
            self.cx.execute("INSERT INTO ajustes (clave, valor) VALUES (?,?) "
                            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                            (clave, str(valor)))
        if clave == "local_id":
            self.local_id = str(valor)

    def _id(self):
        return str(uuid.uuid4())

    def _marcar(self, tabla, *ids):
        """Deja anotado que estas filas hay que subirlas."""
        for i in ids:
            self.cx.execute("INSERT OR IGNORE INTO pendientes (tabla, id) VALUES (?,?)",
                            (tabla, i))

    def _tocar(self, tabla, *ids):
        """Pone la hora de cambio y marca para subir."""
        ahora = ahora_utc()
        for i in ids:
            self.cx.execute("UPDATE %s SET actualizado=? WHERE id=?" % tabla, (ahora, i))
        self._marcar(tabla, *ids)

    def hay_pendientes(self):
        return self.cx.execute("SELECT COUNT(*) FROM pendientes").fetchone()[0]

    def filas_pendientes(self, tabla):
        """Las filas completas que faltan por subir, listas para mandar."""
        return [dict(f) for f in self.cx.execute(
            "SELECT t.* FROM %s t JOIN pendientes p ON p.id = t.id AND p.tabla = ?"
            % tabla, (tabla,))]

    def olvidar_pendientes(self, tabla, ids):
        with self.cx:
            for i in ids:
                self.cx.execute("DELETE FROM pendientes WHERE tabla=? AND id=?", (tabla, i))

    def guardar_de_la_nube(self, tabla, filas):
        """
        Guarda lo que llego del servidor. Gana siempre lo del servidor, salvo
        en una fila que aqui este pendiente de subir: esa se respeta hasta que
        alcance a subirse.
        """
        if tabla not in self.TABLAS or not filas:
            return 0
        columnas = [f[1] for f in self.cx.execute("PRAGMA table_info(%s)" % tabla)]
        guardadas = 0
        with self.cx:
            for fila in filas:
                fid = fila.get("id")
                if not fid:
                    continue
                pendiente = self.cx.execute(
                    "SELECT 1 FROM pendientes WHERE tabla=? AND id=?", (tabla, fid)).fetchone()
                if pendiente:
                    continue
                datos = {}
                for k in columnas:
                    if k in fila:
                        v = fila[k]
                        if k in ("borrado", "activo"):
                            v = 1 if v in (True, 1, "true", "t") else 0
                        datos[k] = v
                existe = self.cx.execute(
                    "SELECT 1 FROM %s WHERE id=?" % tabla, (fid,)).fetchone()
                if existe:
                    campos = ", ".join("%s=?" % k for k in datos if k != "id")
                    if not campos:
                        continue
                    self.cx.execute("UPDATE %s SET %s WHERE id=?" % (tabla, campos),
                                    [v for k, v in datos.items() if k != "id"] + [fid])
                else:
                    faltan = [k for k in self.OBLIGATORIAS[tabla] if k not in datos]
                    if faltan:
                        continue        # fila incompleta: se ignora, no se inventa nada
                    campos = ", ".join(datos)
                    huecos = ", ".join("?" * len(datos))
                    self.cx.execute("INSERT INTO %s (%s) VALUES (%s)"
                                    % (tabla, campos, huecos), list(datos.values()))
                guardadas += 1
        return guardadas

    def cerrar(self):
        self.cx.close()

    # -- clientes --------------------------------------------------------
    _SQL_CLIENTES = """
        SELECT cl.*,
               COALESCE(SUM(c.monto - COALESCE(a.abonado, 0)), 0)      AS deuda,
               COALESCE(SUM(CASE WHEN c.monto > COALESCE(a.abonado, 0)
                                 THEN 1 ELSE 0 END), 0)                AS pendientes,
               MIN(CASE WHEN c.monto > COALESCE(a.abonado, 0)
                        THEN c.fecha END)                              AS mas_antigua,
               MAX(c.fecha)                                            AS ultima_compra,
               (SELECT MAX(p.fecha) FROM pagos p
                 WHERE p.cliente_id = cl.id AND p.borrado = 0)         AS ultimo_pago
          FROM clientes cl
          LEFT JOIN compras c ON c.cliente_id = cl.id AND c.borrado = 0
          LEFT JOIN (SELECT compra_id, SUM(monto) AS abonado
                       FROM aplicaciones WHERE borrado = 0 GROUP BY compra_id) a
                 ON a.compra_id = c.id
    """

    def clientes(self, archivados=False, buscar=""):
        """
        Lista de clientes con lo que deben. Por defecto solo los activos;
        con archivados=True, tambien los archivados.
        """
        filas = self.cx.execute(
            self._SQL_CLIENTES + " WHERE cl.borrado = 0" +
            ("" if archivados else " AND cl.activo = 1") +
            " GROUP BY cl.id ORDER BY cl.nombre COLLATE NOCASE").fetchall()
        lista = [dict(f) for f in filas]
        b = _sin_tildes(buscar).strip()
        if b:
            lista = [x for x in lista
                     if b in _sin_tildes(x["nombre"]) or
                     b in _sin_tildes(x["telefono"]) or b in _sin_tildes(x["nota"])]
        return lista

    def cliente(self, cid):
        f = self.cx.execute(
            self._SQL_CLIENTES + " WHERE cl.id = ? AND cl.borrado = 0 GROUP BY cl.id",
            (cid,)).fetchone()
        return dict(f) if f else None

    def _nombre_ocupado(self, nombre, salvo=None):
        for f in self.cx.execute(
                "SELECT id, nombre FROM clientes WHERE activo = 1 AND borrado = 0"):
            if f["id"] != salvo and _sin_tildes(f["nombre"]).strip() == \
                    _sin_tildes(nombre).strip():
                return True
        return False

    def agregar_cliente(self, nombre, telefono="", nota=""):
        nombre = " ".join(str(nombre or "").split())
        if not nombre:
            raise ValueError("Escribe el nombre del cliente.")
        if self._nombre_ocupado(nombre):
            raise ValueError("Ya hay un cliente que se llama \"%s\".\n\n"
                             "Agrégale algo para distinguirlos, por ejemplo el "
                             "apellido o de dónde es." % nombre)
        nuevo = self._id()
        with self.cx:
            self.cx.execute(
                "INSERT INTO clientes (id, local_id, nombre, telefono, nota, creado, "
                "actualizado) VALUES (?,?,?,?,?,?,?)",
                (nuevo, self.local_id, nombre, str(telefono or "").strip(),
                 str(nota or "").strip(), ahora_utc(), ahora_utc()))
            self._marcar("clientes", nuevo)
        return nuevo

    def editar_cliente(self, cid, nombre, telefono="", nota=""):
        nombre = " ".join(str(nombre or "").split())
        if not nombre:
            raise ValueError("El nombre no puede quedar vacío.")
        if self._nombre_ocupado(nombre, salvo=cid):
            raise ValueError("Ya hay otro cliente que se llama \"%s\"." % nombre)
        with self.cx:
            self.cx.execute("UPDATE clientes SET nombre=?, telefono=?, nota=? WHERE id=?",
                            (nombre, str(telefono or "").strip(),
                             str(nota or "").strip(), cid))
            self._tocar("clientes", cid)

    def quitar_cliente(self, cid):
        """
        Saca al cliente de la lista. Si nunca se le anoto nada se borra; si
        tiene historia se archiva, para no perderla. No se puede con deuda.

        Devuelve "borrado" o "archivado".
        """
        cl = self.cliente(cid)
        if not cl:
            raise ValueError("Ese cliente ya no existe.")
        if cl["deuda"] > 0:
            raise ValueError("%s todavía debe %s.\n\nNo se puede quitar a alguien "
                             "que tiene deuda." % (cl["nombre"], pesos(cl["deuda"])))
        tiene = self.cx.execute(
            "SELECT (SELECT COUNT(*) FROM compras WHERE cliente_id=? AND borrado=0) + "
            "(SELECT COUNT(*) FROM pagos WHERE cliente_id=? AND borrado=0)",
            (cid, cid)).fetchone()[0]
        with self.cx:
            if tiene:
                self.cx.execute("UPDATE clientes SET activo=0 WHERE id=?", (cid,))
                self._tocar("clientes", cid)
                return "archivado"
            self.cx.execute("UPDATE clientes SET borrado=1 WHERE id=?", (cid,))
            self._tocar("clientes", cid)
            return "borrado"

    def reactivar_cliente(self, cid):
        cl = self.cliente(cid)
        if cl and self._nombre_ocupado(cl["nombre"], salvo=cid):
            raise ValueError("Ya hay otro cliente activo que se llama \"%s\". "
                             "Cámbiale el nombre a uno de los dos primero." % cl["nombre"])
        with self.cx:
            self.cx.execute("UPDATE clientes SET activo=1 WHERE id=?", (cid,))
            self._tocar("clientes", cid)

    # -- compras ---------------------------------------------------------
    def _compra(self, compra_id):
        f = self.cx.execute(
            """SELECT c.*, COALESCE((SELECT SUM(monto) FROM aplicaciones
                                      WHERE compra_id = c.id AND borrado = 0), 0) AS abonado
                 FROM compras c WHERE c.id = ? AND c.borrado = 0""",
            (compra_id,)).fetchone()
        if not f:
            raise ValueError("Esa anotación ya no existe.")
        return _con_estado(dict(f))

    def compras_de(self, cid, filtro="todas"):
        """
        Lo anotado a un cliente, de la mas nueva a la mas vieja.
        filtro: "todas", "pendientes" (incluye las pagadas a medias) o "pagadas".
        """
        filas = self.cx.execute(
            """SELECT c.*,
                      COALESCE(SUM(a.monto), 0) AS abonado,
                      MAX(p.fecha)              AS pagada_el
                 FROM compras c
                 LEFT JOIN aplicaciones a ON a.compra_id = c.id AND a.borrado = 0
                 LEFT JOIN pagos p        ON p.id = a.pago_id AND p.borrado = 0
                WHERE c.cliente_id = ? AND c.borrado = 0
                GROUP BY c.id
                ORDER BY c.fecha DESC, c.creado DESC""", (cid,)).fetchall()
        lista = [_con_estado(dict(f)) for f in filas]
        if filtro == "pendientes":
            lista = [x for x in lista if x["estado"] != PAGADA]
        elif filtro == "pagadas":
            lista = [x for x in lista if x["estado"] == PAGADA]
        return lista

    def anotar(self, cid, detalle, monto, fecha=None):
        """Anota una compra fiada. Devuelve su id."""
        monto = _monto_valido(monto)
        fecha = fecha or date.today().isoformat()
        if not self.cliente(cid):
            raise ValueError("Ese cliente ya no existe.")
        nueva = self._id()
        with self.cx:
            self.cx.execute(
                "INSERT INTO compras (id, local_id, cliente_id, fecha, detalle, monto, "
                "creado, actualizado) VALUES (?,?,?,?,?,?,?,?)",
                (nueva, self.local_id, cid, fecha,
                 " ".join(str(detalle or "").split()), monto, ahora_utc(), ahora_utc()))
            self._marcar("compras", nueva)
        return nueva

    def editar_compra(self, compra_id, fecha, detalle, monto):
        monto = _monto_valido(monto)
        c = self._compra(compra_id)
        if monto < c["abonado"]:
            raise ValueError(
                "A esta compra ya le abonaron %s, así que no puede valer menos "
                "que eso.\n\nSi el pago estuvo mal, primero márcala como "
                "pendiente." % pesos(c["abonado"]))
        with self.cx:
            self.cx.execute("UPDATE compras SET fecha=?, detalle=?, monto=? WHERE id=?",
                            (fecha, " ".join(str(detalle or "").split()), monto,
                             compra_id))
            self._tocar("compras", compra_id)

    def borrar_compra(self, compra_id):
        c = self._compra(compra_id)
        if c["abonado"] > 0:
            raise ValueError(
                "Esta compra tiene %s abonados.\n\nPrimero márcala como pendiente "
                "(eso quita el abono) y despues la puedes borrar." % pesos(c["abonado"]))
        with self.cx:
            self.cx.execute("UPDATE compras SET borrado=1 WHERE id=?", (compra_id,))
            self._tocar("compras", compra_id)

    # -- pagos -----------------------------------------------------------
    def marcar_pagada(self, compra_id, fecha=None, nota=""):
        """
        La compra queda pagada entera: se registra un pago por lo que le
        faltaba. Devuelve cuanto se cobro (0 si ya estaba pagada).
        """
        c = self._compra(compra_id)
        if c["falta"] <= 0:
            return 0
        fecha = fecha or date.today().isoformat()
        pago, apl = self._id(), self._id()
        with self.cx:
            self.cx.execute(
                "INSERT INTO pagos (id, local_id, cliente_id, fecha, monto, nota, creado, "
                "actualizado) VALUES (?,?,?,?,?,?,?,?)",
                (pago, self.local_id, c["cliente_id"], fecha, c["falta"], nota or "",
                 ahora_utc(), ahora_utc()))
            self.cx.execute(
                "INSERT INTO aplicaciones (id, local_id, pago_id, compra_id, monto, "
                "creado, actualizado) VALUES (?,?,?,?,?,?,?)",
                (apl, self.local_id, pago, compra_id, c["falta"], ahora_utc(), ahora_utc()))
            self._marcar("pagos", pago)
            self._marcar("aplicaciones", apl)
        return c["falta"]

    def marcar_pendiente(self, compra_id):
        """
        La compra vuelve a quedar debiendose entera. Lo que se le habia
        abonado se descuenta de los pagos de donde salio; un pago que queda
        en cero se borra. Devuelve cuanto se quito.
        """
        c = self._compra(compra_id)
        if c["abonado"] <= 0:
            return 0
        with self.cx:
            apls = self.cx.execute(
                "SELECT id, pago_id, monto FROM aplicaciones "
                "WHERE compra_id=? AND borrado=0", (compra_id,)).fetchall()
            for a in apls:
                self.cx.execute("UPDATE aplicaciones SET borrado=1 WHERE id=?", (a["id"],))
                self._tocar("aplicaciones", a["id"])
                self.cx.execute("UPDATE pagos SET monto = monto - ? WHERE id=?",
                                (a["monto"], a["pago_id"]))
                self._tocar("pagos", a["pago_id"])
            vacios = [f["id"] for f in self.cx.execute(
                "SELECT id FROM pagos WHERE monto <= 0 AND borrado = 0")]
            for pid in vacios:
                self.cx.execute("UPDATE pagos SET borrado=1, monto=1 WHERE id=?", (pid,))
                self._tocar("pagos", pid)
        return c["abonado"]

    def recibir_pago(self, cid, monto, fecha=None, nota="", compras=None):
        """
        El cliente entrega plata. Se reparte entre sus compras pendientes,
        desde la mas antigua (o solo entre las compras indicadas, en ese orden).

        No se aceptan pagos mayores a la deuda: el libro no guarda saldo a favor.
        Devuelve {"pago_id", "monto", "saldadas", "abonada"} donde saldadas es
        cuantas compras quedaron pagadas enteras y abonada la que quedo a medias.
        """
        monto = _monto_valido(monto)
        fecha = fecha or date.today().isoformat()
        pendientes = sorted(self.compras_de(cid, "pendientes"),
                            key=lambda x: (x["fecha"], x["creado"]))
        if compras is not None:
            orden = {compra_id: i for i, compra_id in enumerate(compras)}
            pendientes = sorted([x for x in pendientes if x["id"] in orden],
                                key=lambda x: orden[x["id"]])
        deuda = sum(x["falta"] for x in pendientes)
        if deuda <= 0:
            raise ValueError("No hay nada pendiente que pagar.")
        if monto > deuda:
            raise ValueError("Está pagando %s, pero debe %s.\n\nEl libro no guarda "
                             "saldo a favor: recibe como máximo %s y entrega el "
                             "vuelto." % (pesos(monto), pesos(deuda), pesos(deuda)))
        resto, saldadas, abonada = monto, 0, None
        pid = self._id()
        with self.cx:
            self.cx.execute(
                "INSERT INTO pagos (id, local_id, cliente_id, fecha, monto, nota, creado, "
                "actualizado) VALUES (?,?,?,?,?,?,?,?)",
                (pid, self.local_id, cid, fecha, monto, nota or "", ahora_utc(),
                 ahora_utc()))
            self._marcar("pagos", pid)
            for x in pendientes:
                if resto <= 0:
                    break
                parte = min(resto, x["falta"])
                apl = self._id()
                self.cx.execute(
                    "INSERT INTO aplicaciones (id, local_id, pago_id, compra_id, monto, "
                    "creado, actualizado) VALUES (?,?,?,?,?,?,?)",
                    (apl, self.local_id, pid, x["id"], parte, ahora_utc(), ahora_utc()))
                self._marcar("aplicaciones", apl)
                resto -= parte
                if parte == x["falta"]:
                    saldadas += 1
                else:
                    abonada = x
        return {"pago_id": pid, "monto": monto, "saldadas": saldadas,
                "abonada": abonada}

    def pagos_de(self, cid):
        """Pagos recibidos de un cliente, del mas nuevo al mas viejo."""
        filas = self.cx.execute(
            "SELECT * FROM pagos WHERE cliente_id=? AND borrado=0 "
            "ORDER BY fecha DESC, creado DESC", (cid,)).fetchall()
        lista = []
        for f in filas:
            p = dict(f)
            apl = self.cx.execute(
                """SELECT c.detalle, c.fecha, a.monto, c.monto AS total
                     FROM aplicaciones a JOIN compras c ON c.id = a.compra_id
                    WHERE a.pago_id = ? AND a.borrado = 0 AND c.borrado = 0
                    ORDER BY c.fecha, c.creado""", (p["id"],)).fetchall()
            p["aplicaciones"] = [dict(a) for a in apl]
            lista.append(p)
        return lista

    def borrar_pago(self, pago_id):
        """Deshace un pago: las compras que cubria vuelven a quedar pendientes."""
        f = self.cx.execute("SELECT id FROM pagos WHERE id=? AND borrado=0",
                            (pago_id,)).fetchone()
        if not f:
            raise ValueError("Ese pago ya no existe.")
        with self.cx:
            apls = [a["id"] for a in self.cx.execute(
                "SELECT id FROM aplicaciones WHERE pago_id=? AND borrado=0", (pago_id,))]
            for a in apls:
                self.cx.execute("UPDATE aplicaciones SET borrado=1 WHERE id=?", (a,))
                self._tocar("aplicaciones", a)
            self.cx.execute("UPDATE pagos SET borrado=1 WHERE id=?", (pago_id,))
            self._tocar("pagos", pago_id)

    # -- totales ---------------------------------------------------------
    def deuda(self, cid):
        cl = self.cliente(cid)
        return cl["deuda"] if cl else 0

    def resumen(self, hoy=None):
        hoy = hoy or date.today()
        mes = hoy.strftime("%Y-%m")
        clientes = self.clientes()
        deben = [c for c in clientes if c["deuda"] > 0]
        fiado_mes = self.cx.execute(
            "SELECT COALESCE(SUM(monto),0) FROM compras "
            "WHERE substr(fecha,1,7)=? AND borrado=0", (mes,)).fetchone()[0]
        cobrado_mes = self.cx.execute(
            "SELECT COALESCE(SUM(monto),0) FROM pagos "
            "WHERE substr(fecha,1,7)=? AND borrado=0", (mes,)).fetchone()[0]
        return {
            "por_cobrar": sum(c["deuda"] for c in deben),
            "clientes": len(clientes),
            "deben": len(deben),
            "fiado_mes": fiado_mes,
            "cobrado_mes": cobrado_mes,
            "mes": MESES[hoy.month - 1],
            "mayores": sorted(deben, key=lambda c: -c["deuda"]),
        }

    def movimientos(self, cid):
        """
        Compras y pagos mezclados por fecha, del mas viejo al mas nuevo, con el
        saldo que iba quedando. Para el estado de cuenta impreso.
        """
        mov = []
        for c in self.cx.execute(
                "SELECT * FROM compras WHERE cliente_id=? AND borrado=0", (cid,)):
            mov.append({"fecha": c["fecha"], "orden": (c["creado"], 0, c["id"]),
                        "tipo": "compra", "detalle": c["detalle"], "cargo": c["monto"],
                        "abono": 0})
        for p in self.cx.execute(
                "SELECT * FROM pagos WHERE cliente_id=? AND borrado=0", (cid,)):
            mov.append({"fecha": p["fecha"], "orden": (p["creado"], 1, p["id"]),
                        "tipo": "pago", "detalle": p["nota"] or "Pago",
                        "cargo": 0, "abono": p["monto"]})
        mov.sort(key=lambda m: (m["fecha"], m["orden"]))
        saldo = 0
        for m in mov:
            saldo += m["cargo"] - m["abono"]
            m["saldo"] = saldo
            del m["orden"]
        return mov

    def total_clientes(self):
        return self.cx.execute(
            "SELECT COUNT(*) FROM clientes WHERE borrado=0").fetchone()[0]

    # -- respaldos -------------------------------------------------------
    def carpeta_respaldos(self):
        c = os.path.join(os.path.dirname(self.ruta), "respaldos")
        os.makedirs(c, exist_ok=True)
        return c

    def respaldar(self, destino=None, conservar=60, reemplazar=False):
        """
        Copia la base de datos. Sin destino hace la copia del dia dentro de
        respaldos/ y borra las mas viejas; con destino la guarda donde se le
        diga (un pendrive, por ejemplo). Con reemplazar=True renueva la copia
        del dia aunque ya exista (se usa al cerrar el programa).

        Usa la copia propia de SQLite y no copiar el archivo a mano, porque
        con WAL el archivo suelto puede quedar a medias.
        """
        automatico = destino is None
        if automatico:
            destino = os.path.join(self.carpeta_respaldos(),
                                   "fiados-%s.sqlite3" % date.today().isoformat())
            if os.path.exists(destino) and not reemplazar:
                return None                      # ya hay copia de hoy
        otro = sqlite3.connect(destino)
        try:
            with otro:
                self.cx.backup(otro)
        finally:
            otro.close()
        if automatico:
            self._podar_respaldos(conservar)
        return destino

    def _copias(self):
        try:
            return sorted(f for f in os.listdir(self.carpeta_respaldos())
                          if f.startswith("fiados-") and f.endswith(".sqlite3"))
        except OSError:
            return []

    def _podar_respaldos(self, conservar):
        for viejo in self._copias()[:-conservar] if conservar > 0 else []:
            try:
                os.remove(os.path.join(self.carpeta_respaldos(), viejo))
            except OSError:
                pass

    def ultimo_respaldo(self):
        """(fecha, cuantas copias hay). (None, 0) si todavia no hay ninguna."""
        copias = self._copias()
        if not copias:
            return None, 0
        return copias[-1][len("fiados-"):-len(".sqlite3")], len(copias)

    @staticmethod
    def revisar_copia(ruta):
        """Cuantos clientes, compras y pagos trae una copia. ValueError si no sirve."""
        try:
            otro = _abrir_solo_lectura(ruta)
            try:
                # Lo borrado sigue guardado, pero no se cuenta: al dueno hay
                # que decirle cuantos clientes de verdad trae la copia.
                n = [otro.execute("SELECT COUNT(*) FROM %s WHERE borrado=0" % t).fetchone()[0]
                     for t in ("clientes", "compras", "pagos", "aplicaciones")]
            finally:
                otro.close()
        except sqlite3.Error:
            raise ValueError("Ese archivo no es una copia del Libro de Fiados.")
        return {"clientes": n[0], "compras": n[1], "pagos": n[2]}

    def restaurar(self, ruta):
        """
        Reemplaza todos los datos por los de una copia. Antes guarda lo que
        habia en respaldos/, por si fue un error.
        """
        self.revisar_copia(ruta)
        antes = os.path.join(self.carpeta_respaldos(), "antes-de-restaurar-%s.sqlite3"
                             % datetime.now().strftime("%Y-%m-%d_%H%M%S"))
        self.respaldar(antes)
        otro = _abrir_solo_lectura(ruta)
        try:
            otro.backup(self.cx)
        finally:
            otro.close()
        self.cx.execute("PRAGMA foreign_keys=ON")
        self._preparar()
        return antes


# ---------------------------------------------------------------- auxiliares
def _abrir_solo_lectura(ruta):
    """Abre una copia sin poder modificarla (y sin crearla si no existe)."""
    if not os.path.isfile(ruta):
        raise sqlite3.OperationalError("no existe")
    uri = pathlib.Path(os.path.abspath(ruta)).as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _creado_iso(creado):
    """La fecha de creacion de la version 1 ('2026-09-10 12:00:00') en ISO."""
    return str(creado or "").replace(" ", "T") or ahora_utc()


def _con_estado(c):
    c["abonado"] = int(c.get("abonado") or 0)
    c["falta"] = c["monto"] - c["abonado"]
    if c["falta"] <= 0:
        c["estado"] = PAGADA
    elif c["abonado"] > 0:
        c["estado"] = PARCIAL
    else:
        c["estado"] = PENDIENTE
    if c["estado"] != PAGADA:
        c["pagada_el"] = None
    else:
        c.setdefault("pagada_el", None)
    return c


def _monto_valido(monto):
    if isinstance(monto, str):
        valor = leer_monto(monto)
    else:
        try:
            valor = int(round(float(monto)))
        except (TypeError, ValueError):
            valor = None
    if not valor or valor <= 0:
        raise ValueError("Escribe un monto mayor que cero.")
    if valor > 100000000:
        raise ValueError("Ese monto es demasiado grande. Revisa que esté bien escrito.")
    return valor


_TILDES = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunaeiouun")
_DIAS_SIN_TILDE = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _sin_tildes(texto):
    return str(texto or "").translate(_TILDES).lower()


def texto_whatsapp(cliente, compras, negocio=NEGOCIO):
    """El mensaje para mandarle al cliente lo que debe."""
    nombre = cliente["nombre"].split()[0] if cliente.get("nombre") else ""
    pend = sorted([c for c in compras if c["estado"] != PAGADA],
                  key=lambda c: (c["fecha"], c["id"]))
    total = sum(c["falta"] for c in pend)
    if not pend:
        return ("Hola %s, te saludamos de %s. Tu cuenta está al día, no tienes "
                "nada pendiente. ¡Gracias!" % (nombre, negocio))
    lineas = ["Hola %s, te saludamos de %s." % (nombre, negocio),
              "Te dejamos el detalle de tu cuenta pendiente:", ""]
    for c in pend:
        det = c["detalle"] or "Compra"
        extra = " (abonado %s)" % pesos(c["abonado"]) if c["abonado"] else ""
        lineas.append("- %s  %s  %s%s" % (fecha_txt(c["fecha"])[:5], det,
                                           pesos(c["falta"]), extra))
    lineas += ["", "Total pendiente: %s" % pesos(total), "", "¡Gracias!"]
    return "\n".join(lineas)
