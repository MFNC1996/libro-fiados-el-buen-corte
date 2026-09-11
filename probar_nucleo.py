# -*- coding: utf-8 -*-
"""Pruebas del nucleo. Ejecutar:  python probar_nucleo.py"""
import os, sys, tempfile
from datetime import date
# La consola de Windows usa cp1252 y no sabe escribir algunos simbolos;
# asi las pruebas no se caen por algo que no tiene que ver con la app.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nucleo as N

fallas = []

def check(nombre, obtenido, esperado):
    ok = obtenido == esperado
    print(("  ok   " if ok else "FALLA ") + nombre + "  ->  " + repr(obtenido) +
          ("" if ok else "   (esperado " + repr(esperado) + ")"))
    if not ok:
        fallas.append(nombre)

def falla_con(nombre, funcion, *args, **kw):
    try:
        funcion(*args, **kw)
    except ValueError as e:
        check(nombre + " (se niega)", True, True)
        return str(e)
    check(nombre + " (se niega)", False, True)
    return ""

print("--- pesos ---")
check("miles", N.pesos(12500), "$12.500")
check("millones", N.pesos(1234567), "$1.234.567")
check("cero", N.pesos(0), "$0")
check("negativo", N.pesos(-500), "-$500")

print("\n--- montos escritos como venga ---")
for texto, esperado in [("12500", 12500), ("12.500", 12500), ("$12.500", 12500),
                        ("12 500", 12500), ("12 mil", 12000), ("12,5 mil", 12500),
                        ("12k", 12000), ("3 lucas", 3000), ("8.990,50", 8991),
                        ("", None), ("abc", None), ("0", None), ("-5", None),
                        ("1,2,3", None)]:
    check("'%s'" % texto, N.leer_monto(texto), esperado)

print("\n--- fechas escritas como venga ---")
hoy = date(2026, 9, 10)
for texto, esperado in [("", "2026-09-10"), ("hoy", "2026-09-10"),
                        ("ayer", "2026-09-09"), ("7", "2026-09-07"),
                        ("28", "2026-08-28"),              # el 28 aun no llega: agosto
                        ("7/9", "2026-09-07"), ("7-9", "2026-09-07"),
                        ("28/12", "2025-12-28"),           # diciembre aun no llega
                        ("7/9/26", "2026-09-07"), ("07/09/2026", "2026-09-07"),
                        ("2026-09-07", "2026-09-07"), ("31/2", None),
                        ("hola", None), ("1/2/3/4", None)]:
    check("'%s'" % texto, N.leer_fecha(texto, hoy), esperado)
print("\n--- fechas con dia de la semana y mes en palabras ---")
martes20 = date(2026, 10, 20)                     # un martes; el 13 tambien fue martes
for texto, esperado in [("martes", "2026-10-20"),          # hoy mismo es martes
                        ("el lunes", "2026-10-19"), ("miércoles", "2026-10-14"),
                        ("Martes 13", "2026-10-13"), ("el martes, 13", "2026-10-13"),
                        ("13 de octubre", "2026-10-13"), ("martes 13 de octubre", "2026-10-13"),
                        ("2 de enero", "2026-01-02"), ("25 de diciembre", "2025-12-25"),
                        ("marte", None)]:
    check("'%s'" % texto, N.leer_fecha(texto, martes20), esperado)
check("'martes 13' busca el ultimo 13 que cayo martes", N.leer_fecha("martes 13", hoy),
      "2026-01-13")
check("fecha corta este anio", N.fecha_corta("2026-09-07", hoy), "07/09")
check("fecha corta otro anio", N.fecha_corta("2025-12-28", hoy), "28/12/25")
check("fecha corta", N.fecha_txt("2026-09-07"), "07/09/2026")
check("fecha larga", N.fecha_larga("2026-09-07"), "lunes 7 de septiembre de 2026")

print("\n--- telefono para WhatsApp ---")
check("9 1234 5678", N.telefono_whatsapp("9 1234 5678"), "56912345678")
check("+56 9 1234 5678", N.telefono_whatsapp("+56 9 1234 5678"), "56912345678")
check("8 digitos", N.telefono_whatsapp("12345678"), "56912345678")
check("fijo raro", N.telefono_whatsapp("452"), None)

print("\n--- clientes ---")
d = N.Datos(os.path.join(tempfile.mkdtemp(), "prueba.sqlite3"))
juan = d.agregar_cliente("  Juan   Pérez ", "9 1234 5678", "vecino del frente")
check("nombre ordenado", d.cliente(juan)["nombre"], "Juan Pérez")
check("parte sin deuda", d.deuda(juan), 0)
falla_con("nombre repetido (sin importar tildes ni mayusculas)",
          d.agregar_cliente, "juan perez")
falla_con("nombre vacio", d.agregar_cliente, "   ")
ana = d.agregar_cliente("Ana Soto")
check("dos clientes", len(d.clientes()), 2)
check("buscar sin tilde encuentra con tilde", [c["nombre"] for c in d.clientes(buscar="perez")],
      ["Juan Pérez"])
check("buscar por telefono", len(d.clientes(buscar="5678")), 1)

print("\n--- anotar compras ---")
c1 = d.anotar(juan, "Molida 1 kg", "8.990", "2026-09-01")
c2 = d.anotar(juan, "Costillar 2 kg", 15000, "2026-09-03")
c3 = d.anotar(juan, "Pollo entero", "6.500", "2026-09-05")
check("debe la suma", d.deuda(juan), 8990 + 15000 + 6500)
check("tres pendientes", d.cliente(juan)["pendientes"], 3)
check("la mas antigua", d.cliente(juan)["mas_antigua"], "2026-09-01")
check("orden: mas nueva primero", [c["id"] for c in d.compras_de(juan)], [c3, c2, c1])
falla_con("monto cero", d.anotar, juan, "nada", 0)
falla_con("monto con letras", d.anotar, juan, "nada", "abc")

print("\n--- marcar una compra pagada ---")
check("cobra lo que faltaba", d.marcar_pagada(c2, "2026-09-06"), 15000)
check("queda pagada", d._compra(c2)["estado"], N.PAGADA)
check("con fecha de pago", [c["pagada_el"] for c in d.compras_de(juan, "pagadas")],
      ["2026-09-06"])
check("baja la deuda", d.deuda(juan), 8990 + 6500)
check("pendientes: 2", len(d.compras_de(juan, "pendientes")), 2)
check("pagarla otra vez no hace nada", d.marcar_pagada(c2), 0)
check("un solo pago registrado", len(d.pagos_de(juan)), 1)
falla_con("no se borra una compra pagada", d.borrar_compra, c2)
falla_con("no puede valer menos que lo abonado", d.editar_compra, c2,
          "2026-09-03", "Costillar", 1000)

print("\n--- volver a dejarla pendiente ---")
check("devuelve lo abonado", d.marcar_pendiente(c2), 15000)
check("vuelve la deuda", d.deuda(juan), 8990 + 15000 + 6500)
check("el pago se borro por quedar en cero", len(d.pagos_de(juan)), 0)

print("\n--- recibir un pago: desde la compra mas antigua ---")
r = d.recibir_pago(juan, "20.000", "2026-09-08", "efectivo")
check("salda la del 1 y abona la del 3", r["saldadas"], 1)
check("la que quedo a medias es el costillar", r["abonada"]["id"], c2)
check("molida pagada", d._compra(c1)["estado"], N.PAGADA)
check("costillar a medias", d._compra(c2)["estado"], N.PARCIAL)
check("costillar abonado", d._compra(c2)["abonado"], 20000 - 8990)
check("costillar falta", d._compra(c2)["falta"], 15000 - (20000 - 8990))
check("pollo intacto", d._compra(c3)["estado"], N.PENDIENTE)
check("deuda", d.deuda(juan), 8990 + 15000 + 6500 - 20000)
p = d.pagos_de(juan)[0]
check("el pago dice a que fue", [a["detalle"] for a in p["aplicaciones"]],
      ["Molida 1 kg", "Costillar 2 kg"])
msg = falla_con("pagar mas de lo que debe", d.recibir_pago, juan, 999999)
check("el aviso dice cuanto debe", N.pesos(d.deuda(juan)) in msg, True)

print("\n--- marcar pendiente una compra pagada con un pago repartido ---")
check("quita lo de la molida", d.marcar_pendiente(c1), 8990)
check("el pago se achica", d.pagos_de(juan)[0]["monto"], 20000 - 8990)
check("deuda sube", d.deuda(juan), 8990 + 15000 + 6500 - (20000 - 8990))

print("\n--- deshacer un pago ---")
d.borrar_pago(p["id"])
check("sin pagos", len(d.pagos_de(juan)), 0)
check("todo pendiente otra vez", d.deuda(juan), 8990 + 15000 + 6500)
check("sin abonos colgando", d.cx.execute("SELECT COUNT(*) FROM aplicaciones").fetchone()[0], 0)

print("\n--- pagar solo unas compras elegidas ---")
r = d.recibir_pago(juan, 6500, compras=[c3])
check("pago justo el pollo", d._compra(c3)["estado"], N.PAGADA)
check("la molida sigue", d._compra(c1)["estado"], N.PENDIENTE)
d.borrar_pago(r["pago_id"])

print("\n--- pagar todo ---")
d.recibir_pago(juan, d.deuda(juan))
check("queda al dia", d.deuda(juan), 0)
check("todas pagadas", len(d.compras_de(juan, "pagadas")), 3)
falla_con("pagar sin deuda", d.recibir_pago, juan, 100)

print("\n--- el ejemplo: debe $45.000 y el martes 13 abona $30.000 ---")
rosa = d.agregar_cliente("Rosa")
a1 = d.anotar(rosa, "Asado", 20000, "2026-10-01")
a2 = d.anotar(rosa, "Costillar", 25000, "2026-10-05")
check("debe 45 mil", d.deuda(rosa), 45000)
r = d.recibir_pago(rosa, "30 mil", N.leer_fecha("martes 13", martes20), "efectivo")
check("queda debiendo 15 mil", d.deuda(rosa), 15000)
check("el asado queda pagado", d._compra(a1)["estado"], N.PAGADA)
check("al costillar se le abonan 10 mil", d._compra(a2)["abonado"], 10000)
check("el costillar queda a medias", d._compra(a2)["estado"], N.PARCIAL)
check("el abono queda con su fecha", d.pagos_de(rosa)[0]["fecha"], "2026-10-13")
d.borrar_pago(r["pago_id"])
d.borrar_compra(a1); d.borrar_compra(a2); d.quitar_cliente(rosa)

print("\n--- estado de cuenta ---")
mov = d.movimientos(juan)
check("3 compras y 1 pago", [m["tipo"] for m in mov].count("compra"), 3)
check("saldo final cero", mov[-1]["saldo"], 0)

print("\n--- quitar clientes ---")
d.anotar(ana, "Chuleta", 4000)
falla_con("no se quita con deuda", d.quitar_cliente, ana)
check("con historia se archiva", d.quitar_cliente(juan), "archivado")
check("ya no sale en la lista", [c["id"] for c in d.clientes()], [ana])
check("sale con archivados", len(d.clientes(archivados=True)), 2)
d.reactivar_cliente(juan)
check("reactivado", len(d.clientes()), 2)
nuevo = d.agregar_cliente("Pedro")
check("sin historia se borra", d.quitar_cliente(nuevo), "borrado")

print("\n--- resumen ---")
res = d.resumen()
check("por cobrar", res["por_cobrar"], 4000)
check("clientes que deben", res["deben"], 1)
check("mayor deudora", res["mayores"][0]["nombre"], "Ana Soto")

print("\n--- mensaje de WhatsApp ---")
txt = N.texto_whatsapp(d.cliente(ana), d.compras_de(ana))
check("saluda por el primer nombre", txt.startswith("Hola Ana,"), True)
check("dice el total", "Total pendiente: $4.000" in txt, True)
txt = N.texto_whatsapp(d.cliente(juan), d.compras_de(juan))
check("al dia", "al día" in txt, True)

print("\n--- respaldo y restaurar ---")
copia = os.path.join(tempfile.mkdtemp(), "copia.sqlite3")
d.respaldar(copia)
check("la copia se lee", N.Datos.revisar_copia(copia)["clientes"], 2)
check("respaldo del dia", d.respaldar() is not None, True)
check("no repite el del dia", d.respaldar(), None)
check("cuenta la copia", d.ultimo_respaldo()[1], 1)
d.anotar(ana, "Algo que despues se deshace", 1000)
antes = d.restaurar(copia)
check("vuelve a lo de la copia", d.deuda(ana), 4000)
check("guardo lo de antes", os.path.exists(antes), True)
basura = os.path.join(tempfile.mkdtemp(), "no-es.sqlite3")
open(basura, "w").write("hola")
falla_con("un archivo cualquiera no se restaura", d.restaurar, basura)
falla_con("un archivo que no existe", N.Datos.revisar_copia, basura + "x")
check("la base sigue sana", d.deuda(ana), 4000)

print("\n--- 3000 operaciones al azar: las cuentas siempre cuadran ---")
import random
azar = random.Random(1996)            # siempre las mismas, para poder repetir una falla
d = N.Datos(os.path.join(tempfile.mkdtemp(), "azar.sqlite3"))
clientes = [d.agregar_cliente("Cliente %d" % i) for i in range(6)]
hechas = {"anotar": 0, "pagada": 0, "pendiente": 0, "abono": 0, "deshacer": 0,
          "borrar": 0, "corregir": 0, "rechazada": 0}

def revisar_todo():
    """Lo que tiene que cumplirse siempre, pase lo que pase."""
    malos = []
    for cl in clientes:
        compras = d.compras_de(cl)
        pagos = d.pagos_de(cl)
        fiado = sum(c["monto"] for c in compras)
        pagado = sum(p["monto"] for p in pagos)
        if d.deuda(cl) != fiado - pagado:
            malos.append("deuda != fiado - pagado (cliente %d)" % cl)
        if d.deuda(cl) != sum(c["falta"] for c in compras):
            malos.append("deuda != suma de lo que falta (cliente %d)" % cl)
        for c in compras:
            if not (0 <= c["abonado"] <= c["monto"]):
                malos.append("compra %d con abonado fuera de rango" % c["id"])
            estado = (N.PAGADA if c["falta"] == 0 else
                      N.PARCIAL if c["abonado"] else N.PENDIENTE)
            if c["estado"] != estado:
                malos.append("compra %d con estado equivocado" % c["id"])
        for p in pagos:
            if p["monto"] <= 0 or p["monto"] != sum(a["monto"] for a in p["aplicaciones"]):
                malos.append("pago %d no cuadra con lo que cubre" % p["id"])
        if d.deuda(cl) < 0:
            malos.append("deuda negativa (cliente %d)" % cl)
    huerfanas = d.cx.execute("""SELECT COUNT(*) FROM aplicaciones a
                                 LEFT JOIN compras c ON c.id = a.compra_id
                                 LEFT JOIN pagos p ON p.id = a.pago_id
                                WHERE c.id IS NULL OR p.id IS NULL""").fetchone()[0]
    if huerfanas:
        malos.append("%d abonos colgando de algo que ya no existe" % huerfanas)
    return malos

primer_error = None
for paso in range(3000):
    cl = azar.choice(clientes)
    compras = d.compras_de(cl)
    op = azar.choice(["anotar"] * 4 + ["pagada", "pendiente", "abono", "abono",
                                       "deshacer", "borrar", "corregir"])
    try:
        if op == "anotar" or not compras:
            op = "anotar"
            d.anotar(cl, "cosa %d" % paso, azar.randint(1, 60) * 500,
                     "2026-%02d-%02d" % (azar.randint(1, 9), azar.randint(1, 28)))
        elif op == "pagada":
            d.marcar_pagada(azar.choice(compras)["id"])
        elif op == "pendiente":
            d.marcar_pendiente(azar.choice(compras)["id"])
        elif op == "abono":
            deuda = d.deuda(cl)
            d.recibir_pago(cl, azar.randint(1, max(1, deuda + 5000)))   # a veces de mas
        elif op == "deshacer":
            pagos = d.pagos_de(cl)
            if pagos:
                d.borrar_pago(azar.choice(pagos)["id"])
        elif op == "borrar":
            d.borrar_compra(azar.choice(compras)["id"])
        elif op == "corregir":
            c = azar.choice(compras)
            d.editar_compra(c["id"], c["fecha"], c["detalle"], azar.randint(1, 60) * 500)
        hechas[op] += 1
    except ValueError:
        hechas["rechazada"] += 1        # lo que no se puede hacer se rechaza, sin romper nada
    malos = revisar_todo()
    if malos and primer_error is None:
        primer_error = "paso %d (%s): %s" % (paso, op, malos[0])
        break
check("ninguna operacion descuadra las cuentas", primer_error, None)
print("       " + ", ".join("%s %d" % (k, n) for k, n in hechas.items()))
check("hubo de todo", all(n > 20 for n in hechas.values()), True)

print()
if fallas:
    print("FALLARON %d PRUEBAS:" % len(fallas))
    for f in fallas:
        print("  - " + f)
    sys.exit(1)
print("Todo bien.")
