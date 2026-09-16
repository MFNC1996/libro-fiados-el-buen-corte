# -*- coding: utf-8 -*-
"""
Prueba de la sincronizacion, sin internet y sin cuenta de nadie.

Levanta un servidor de mentira que responde igual que Supabase y hace pasar
por ahi dos "dispositivos": el computador del local y el celular. Sirve para
comprobar lo unico que de verdad importa: que lo que se anota en uno aparezca
en el otro, y que nada se pierda ni se duplique.

    python probar_nube.py
"""
import json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nucleo as N
import sincronizador as S

fallas = []
def check(nombre, cond):
    print(("  ok   " if cond else "FALLA ") + nombre)
    if not cond:
        fallas.append(nombre)


# --------------------------------------------------- el servidor de mentira
class ServidorFalso(object):
    """Guarda las filas en memoria y responde como el de verdad."""

    def __init__(self):
        self.tablas = {t: {} for t in N.Datos.TABLAS}
        self.reloj = 0
        self.caidas = 0            # cuantas llamadas seguidas fallar a proposito
        self.cuentas = ["dueno@local.cl"]
        self.miembros = [{"correo": "dueno@local.cl", "rol": "dueno",
                          "desde": "2026-09-01T10:00:00Z"}]

    def ahora(self):
        self.reloj += 1
        return "2026-09-16T10:%02d:%02d.000Z" % (self.reloj // 60, self.reloj % 60)

    def upsert(self, tabla, filas):
        devueltas = []
        for f in filas:
            fila = dict(self.tablas[tabla].get(f["id"], {}))
            fila.update(f)
            fila["actualizado"] = self.ahora()      # la hora la pone el servidor
            self.tablas[tabla][f["id"]] = fila
            devueltas.append(fila)
        return devueltas

    def listar(self, tabla, local_id, desde, tope=500):
        filas = [f for f in self.tablas[tabla].values()
                 if f.get("local_id") == local_id and (not desde or f["actualizado"] > desde)]
        return sorted(filas, key=lambda f: f["actualizado"])[:tope]


ESTADO = ServidorFalso()


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _responder(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null")

    def do_POST(self):
        if ESTADO.caidas > 0:
            ESTADO.caidas -= 1
            return self._responder(500, {"message": "se cayo el servidor"})
        ruta = urlparse(self.path)
        if ruta.path == "/auth/v1/signup":
            cuerpo = self._cuerpo() or {}
            if cuerpo.get("email") in ESTADO.cuentas:
                return self._responder(422, {"message": "User already registered"})
            ESTADO.cuentas.append(cuerpo.get("email"))
            return self._responder(200, {"id": "usuario-nuevo"})
        if ruta.path.startswith("/rest/v1/rpc/"):
            if self.headers.get("Authorization") != "Bearer token-de-prueba":
                return self._responder(401, {"message": "sin permiso"})
            funcion = ruta.path[len("/rest/v1/rpc/"):]
            cuerpo = self._cuerpo() or {}
            if funcion == "usuarios_del_local":
                return self._responder(200, ESTADO.miembros)
            if funcion == "agregar_al_local":
                correo = cuerpo.get("p_correo")
                if correo not in ESTADO.cuentas:
                    return self._responder(
                        400, {"message": "Todavía no hay una cuenta con ese correo"})
                ESTADO.miembros = [m for m in ESTADO.miembros if m["correo"] != correo]
                ESTADO.miembros.append({"correo": correo, "rol": cuerpo.get("p_rol"),
                                        "desde": "2026-09-16T10:00:00Z"})
                return self._responder(200, "listo")
            if funcion == "quitar_del_local":
                ESTADO.miembros = [m for m in ESTADO.miembros
                                   if m["correo"] != cuerpo.get("p_correo")]
                return self._responder(200, "listo")
            return self._responder(404, {})
        if ruta.path == "/auth/v1/token":
            cuerpo = self._cuerpo() or {}
            if "password" in cuerpo and cuerpo.get("password") != "la-clave":
                return self._responder(400, {"error": "credenciales malas"})
            return self._responder(200, {"access_token": "token-de-prueba",
                                         "refresh_token": "refresco-de-prueba"})
        if ruta.path.startswith("/rest/v1/"):
            if self.headers.get("Authorization") != "Bearer token-de-prueba":
                return self._responder(401, {"message": "sin permiso"})
            tabla = ruta.path[len("/rest/v1/"):]
            return self._responder(201, ESTADO.upsert(tabla, self._cuerpo() or []))
        self._responder(404, {})

    def do_GET(self):
        if ESTADO.caidas > 0:
            ESTADO.caidas -= 1
            return self._responder(500, {"message": "se cayo el servidor"})
        ruta = urlparse(self.path)
        if not ruta.path.startswith("/rest/v1/"):
            return self._responder(404, {})
        if self.headers.get("Authorization") != "Bearer token-de-prueba":
            return self._responder(401, {"message": "sin permiso"})
        q = parse_qs(ruta.query)
        tabla = ruta.path[len("/rest/v1/"):]
        local = (q.get("local_id", ["eq."])[0])[3:]
        desde = (q.get("actualizado", [""])[0])[3:]
        tope = int(q.get("limit", ["500"])[0])
        self._responder(200, ESTADO.listar(tabla, local, desde, tope))


servidor = HTTPServer(("127.0.0.1", 0), Manejador)
threading.Thread(target=servidor.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d" % servidor.server_port
LOCAL = "local-de-prueba"


def dispositivo(nombre, local=LOCAL):
    """Un libro nuevo, ya configurado para hablar con el servidor de mentira."""
    d = N.Datos(os.path.join(tempfile.mkdtemp(), nombre + ".sqlite3"))
    for clave, valor in (("url", URL), ("anon", "anon-de-prueba"),
                         ("local_id", local), ("refresco", "refresco-de-prueba")):
        d.guardar_config(clave, valor)
    return d


def sincronizar(d, local=None):
    """Una vuelta completa de subir y bajar, como la que hace el programa."""
    local = local or d.config("local_id")
    s = S.Sincronizador(d.ruta)
    nube = S.Nube(URL, "anon-de-prueba")
    nube.renovar("refresco-de-prueba")
    s._subir(d, nube, local)
    s._bajar(d, nube, local)
    return s


print("--- entrar al servidor ---")
nube = S.Nube(URL, "anon-de-prueba")
check("entra con la clave correcta", nube.entrar("dueno@local.cl", "la-clave"))
try:
    S.Nube(URL, "anon-de-prueba").entrar("dueno@local.cl", "mala")
    check("rechaza la clave mala", False)
except S.ErrorDeNube:
    check("rechaza la clave mala", True)
try:
    S.Nube("http://127.0.0.1:1", "x").entrar("a@b.cl", "c")
    check("avisa cuando no hay internet", False)
except S.ErrorDeNube as e:
    check("avisa cuando no hay internet", "conexion" in str(e).lower() or
          "servidor" in str(e).lower())

print("\n--- el computador anota y sube ---")
pc = dispositivo("computador")
juan = pc.agregar_cliente("Juan Pérez", "9 8765 4321")
compra = pc.anotar(juan, "Costillar 2 kg", 15000, "2026-09-14")
pc.anotar(juan, "Molida 1 kg", 8990, "2026-09-15")
check("antes de subir hay 3 cosas pendientes", pc.hay_pendientes() == 3)
sincronizar(pc)
check("despues de subir no queda nada pendiente", pc.hay_pendientes() == 0)
check("el servidor tiene el cliente", len(ESTADO.tablas["clientes"]) == 1)
check("y las dos compras", len(ESTADO.tablas["compras"]) == 2)

print("\n--- el celular baja lo mismo ---")
cel = dispositivo("celular")
sincronizar(cel)
check("ve al cliente", cel.cliente(juan)["nombre"] == "Juan Pérez")
check("ve las dos compras", len(cel.compras_de(juan)) == 2)
check("y la misma deuda que el computador", cel.deuda(juan) == pc.deuda(juan) == 23990)

print("\n--- el celular abona y el computador se entera ---")
cel.recibir_pago(juan, 10000, "2026-09-16")
sincronizar(cel)
sincronizar(pc)
check("el computador ve el abono", pc.deuda(juan) == 13990)
check("con el detalle de a que compra fue",
      pc.pagos_de(juan)[0]["aplicaciones"][0]["detalle"] == "Costillar 2 kg")
check("los dos muestran lo mismo", pc.deuda(juan) == cel.deuda(juan))

print("\n--- el computador borra y el celular deja de verlo ---")
otra = pc.anotar(juan, "Pollo que se anoto mal", 6500)
sincronizar(pc); sincronizar(cel)
check("primero el celular la ve", any(c["id"] == otra for c in cel.compras_de(juan)))
pc.borrar_compra(otra)
sincronizar(pc); sincronizar(cel)
check("despues de borrarla, ya no", not any(c["id"] == otra for c in cel.compras_de(juan)))
check("y la deuda vuelve a cuadrar", cel.deuda(juan) == pc.deuda(juan) == 13990)

print("\n--- sin internet se sigue anotando ---")
ESTADO.caidas = 99                      # el servidor deja de responder
pendiente = pc.anotar(juan, "Longaniza sin señal", 3500)
try:
    sincronizar(pc)
except S.ErrorDeNube:
    pass
check("la compra quedo anotada igual", any(c["id"] == pendiente
                                           for c in pc.compras_de(juan)))
check("y esperando para subir", pc.hay_pendientes() >= 1)
ESTADO.caidas = 0                       # vuelve internet
sincronizar(pc); sincronizar(cel)
check("cuando vuelve la señal, sube sola", pc.hay_pendientes() == 0)
check("y aparece en el celular", any(c["id"] == pendiente for c in cel.compras_de(juan)))
check("con la deuda al dia en los dos", cel.deuda(juan) == pc.deuda(juan) == 13990 + 3500)

print("\n--- los dos anotan a la vez, sin pisarse ---")
a = pc.anotar(juan, "Lo que anoto el local", 1000)
b = cel.anotar(juan, "Lo que anoto el celular", 2000)
sincronizar(pc); sincronizar(cel); sincronizar(pc)
detalles = [c["detalle"] for c in pc.compras_de(juan)]
check("el computador tiene las dos", "Lo que anoto el local" in detalles and
      "Lo que anoto el celular" in detalles)
check("el celular tambien", len(cel.compras_de(juan)) == len(pc.compras_de(juan)))
check("y las cuentas coinciden", cel.deuda(juan) == pc.deuda(juan))
check("sin duplicados", len(set(c["id"] for c in pc.compras_de(juan))) ==
      len(pc.compras_de(juan)))

print("\n--- sincronizar de nuevo no repite nada ---")
antes = len(pc.compras_de(juan)), pc.deuda(juan)
sincronizar(pc); sincronizar(pc)
check("todo queda igual", (len(pc.compras_de(juan)), pc.deuda(juan)) == antes)

print("\n--- el caso de verdad: el libro que YA tiene el local pasa solo a internet ---")
# Se arma una base como la que hoy tiene el computador de la carniceria
# (version 1, con numeros corridos) y se abre con la version nueva.
import sqlite3
ruta_local = os.path.join(tempfile.mkdtemp(), "fiados.sqlite3")
vieja = sqlite3.connect(ruta_local)
vieja.executescript("""
    CREATE TABLE clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
        telefono TEXT NOT NULL DEFAULT '', nota TEXT NOT NULL DEFAULT '',
        activo INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL DEFAULT '');
    CREATE TABLE compras (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
        fecha TEXT NOT NULL, detalle TEXT NOT NULL DEFAULT '', monto INTEGER NOT NULL,
        creado TEXT NOT NULL DEFAULT '');
    CREATE TABLE pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER NOT NULL,
        fecha TEXT NOT NULL, monto INTEGER NOT NULL, nota TEXT NOT NULL DEFAULT '',
        creado TEXT NOT NULL DEFAULT '');
    CREATE TABLE aplicaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, pago_id INTEGER NOT NULL,
        compra_id INTEGER NOT NULL, monto INTEGER NOT NULL);
    INSERT INTO clientes (nombre, telefono, creado) VALUES
        ('Rosa Huenchul', '95551212', '2026-09-01 09:00:00'),
        ('Carlos Mena', '', '2026-09-01 09:05:00'),
        ('Marta Riquelme', '944443333', '2026-09-02 11:00:00');
    INSERT INTO compras (cliente_id, fecha, detalle, monto, creado) VALUES
        (1, '2026-09-03', 'Pollo entero', 6500, '2026-09-03 10:00:00'),
        (1, '2026-09-07', 'Molida 1 kg', 8990, '2026-09-07 10:00:00'),
        (2, '2026-08-02', 'Carne para cazuela', 5600, '2026-08-02 10:00:00'),
        (2, '2026-09-09', 'Pulpa de cerdo 2 kg', 11800, '2026-09-09 10:00:00'),
        (3, '2026-09-10', 'Asado de tira', 14900, '2026-09-10 10:00:00');
    INSERT INTO pagos (cliente_id, fecha, monto, nota, creado) VALUES
        (1, '2026-09-08', 6500, 'efectivo', '2026-09-08 10:00:00'),
        (3, '2026-09-12', 5000, 'abono', '2026-09-12 10:00:00');
    INSERT INTO aplicaciones (pago_id, compra_id, monto) VALUES (1, 1, 6500), (2, 5, 5000);
""")
vieja.commit(); vieja.close()

# Lo que el dueno ve hoy en su computador, para comparar despues.
antes = {"Rosa Huenchul": 8990, "Carlos Mena": 5600 + 11800, "Marta Riquelme": 14900 - 5000}

CARNICERIA = "local-de-la-carniceria"             # el local de verdad, aparte
local = N.Datos(ruta_local)                       # <- aqui migra sola
for clave, valor in (("url", URL), ("anon", "anon-de-prueba"),
                     ("local_id", CARNICERIA), ("refresco", "refresco-de-prueba")):
    local.guardar_config(clave, valor)
deudas = {c["nombre"]: c["deuda"] for c in local.clientes()}
check("los 3 clientes siguen ahi", len(deudas) == 3)
check("y cada uno debe exactamente lo mismo que antes", deudas == antes)
check("el total por cobrar no cambio",
      local.resumen()["por_cobrar"] == sum(antes.values()))
check("quedo todo listo para subir (5 compras + 3 clientes + 2 pagos + 2 abonos)",
      local.hay_pendientes() == 12)

sincronizar(local)
check("despues de conectarse, no queda nada sin subir", local.hay_pendientes() == 0)

nuevo_celular = dispositivo("celular-del-dueno", CARNICERIA)
sincronizar(nuevo_celular)
deudas_cel = {c["nombre"]: c["deuda"] for c in nuevo_celular.clientes()}
check("el celular ve los mismos 3 clientes", len(deudas_cel) == 3)
check("con las mismas deudas, sin escribir nada a mano", deudas_cel == antes)
rosa = [c for c in nuevo_celular.clientes() if c["nombre"] == "Rosa Huenchul"][0]
check("con el telefono que ya estaba anotado", rosa["telefono"] == "95551212")
check("y con el historial completo (compras pagadas incluidas)",
      len(nuevo_celular.compras_de(rosa["id"])) == 2)
check("el pollo figura pagado", [c["estado"] for c in
      nuevo_celular.compras_de(rosa["id"]) if c["detalle"] == "Pollo entero"] == [N.PAGADA])
marta = [c for c in nuevo_celular.clientes() if c["nombre"] == "Marta Riquelme"][0]
check("y el abono de Marta quedo pegado a su compra",
      nuevo_celular.compras_de(marta["id"])[0]["abonado"] == 5000)

# Y desde el celular se sigue trabajando sobre esos mismos datos.
nuevo_celular.recibir_pago(marta["id"], 9900)
sincronizar(nuevo_celular); sincronizar(local)
check("lo que cobra el dueno desde el celular llega al computador",
      local.deuda(marta["id"]) == 0)

print("\n--- un libro grande se sincroniza entero, por tandas ---")
grande = dispositivo("local-con-historia", "local-grande")
cliente_grande = grande.agregar_cliente("Cliente de muchos años")
for i in range(600):                      # mas de lo que cabe en una sola tanda
    grande.anotar(cliente_grande, "Compra %d" % i, 1000, "2026-01-01")
check("hay 601 cosas por subir", grande.hay_pendientes() == 601)
sincronizar(grande)
check("se subio todo", grande.hay_pendientes() == 0)
check("el servidor tiene las 600 compras", len(
    [c for c in ESTADO.tablas["compras"].values() if c["local_id"] == "local-grande"]) == 600)
otro = dispositivo("otro-dispositivo", "local-grande")
sincronizar(otro)
check("el otro dispositivo las baja todas (no solo la primera tanda)",
      len(otro.compras_de(cliente_grande)) == 600)
check("con la deuda completa", otro.deuda(cliente_grande) == 600 * 1000)

print("\n--- el dueno crea mas usuarios desde el programa ---")
check("al principio solo esta el dueno", len(S.usuarios(pc)) == 1)
S.crear_usuario(pc, "mostrador@elbuencorte.cl", "clave-larga", "ayudante")
gente = S.usuarios(pc)
check("queda agregado el del mostrador", len(gente) == 2)
check("con el rol de ayudante", [g["rol"] for g in gente
                                 if g["correo"] == "mostrador@elbuencorte.cl"] == ["ayudante"])
S.crear_usuario(pc, "mostrador@elbuencorte.cl", "otra-clave")
check("volver a agregarlo no lo duplica", len(S.usuarios(pc)) == 2)
for correo, clave, porque in [("sin-arroba", "clave-larga", "correo mal escrito"),
                              ("otro@local.cl", "123", "clave muy corta")]:
    try:
        S.crear_usuario(pc, correo, clave)
        check("rechaza: " + porque, False)
    except S.ErrorDeNube:
        check("rechaza: " + porque, True)
S.quitar_acceso(pc, "mostrador@elbuencorte.cl")
check("y se le puede quitar el acceso", len(S.usuarios(pc)) == 1)
try:
    S.dar_acceso(pc, "desconocido@nadie.cl")
    check("no da acceso a un correo sin cuenta", False)
except S.ErrorDeNube:
    check("no da acceso a un correo sin cuenta", True)

print()
servidor.shutdown()
if fallas:
    print("FALLARON %d PRUEBAS:" % len(fallas))
    for f in fallas:
        print("  - " + f)
    sys.exit(1)
print("Todo bien.")
