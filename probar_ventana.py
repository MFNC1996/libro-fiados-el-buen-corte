# -*- coding: utf-8 -*-
"""
Arma la ventana entera sin mostrarla y prueba el uso de todos los dias:
agregar un cliente, anotarle, marcar pagado, recibir un pago, deshacer.

Sirve para que la compilacion falle en GitHub y no en el computador del local.
"""
import os, sys, tempfile, threading
# La consola de Windows usa cp1252 y no sabe escribir simbolos como el del
# check; asi las pruebas no se caen por algo que no tiene que ver con la app.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
os.environ["XDG_DATA_HOME"] = os.environ["LOCALAPPDATA"]

# Si algo queda dando vueltas sin fin (la ventana colgada), la prueba falla
# en vez de quedarse esperando para siempre.
def _vigilante():
    print("\nFALLA: la ventana se quedo colgada mas de 90 segundos")
    sys.stdout.flush()
    os._exit(1)
_reloj = threading.Timer(90, _vigilante)
_reloj.daemon = True
_reloj.start()

import nucleo as N

try:
    import app
except ImportError as e:
    print("FALLA: no se pudo importar la ventana: %s" % e)
    sys.exit(1)

# Las preguntas se contestan solas: si a todo.
preguntas = []
app.messagebox.askyesno = lambda *a, **k: (preguntas.append(a[0]), True)[1]
app.messagebox.showinfo = lambda *a, **k: preguntas.append(a[0])
app.messagebox.showwarning = lambda *a, **k: preguntas.append(a[0])
app.webbrowser.open = lambda *a, **k: preguntas.append("navegador")
app.App._abrir = staticmethod(lambda ruta: preguntas.append("abrir " + ruta))

fallas = []
def check(nombre, cond):
    print(("  ok   " if cond else "FALLA ") + nombre)
    if not cond:
        fallas.append(nombre)

def al_dia():
    for _ in range(5):
        v.update()

v = app.App()
v.withdraw()
al_dia()

print("--- la ventana ---")
check("'by Macoem' en la cabecera", v.lbl_autor.cget("text") == "by Macoem")
check("'by Macoem' en la barra de titulo", "by Macoem" in v.title())
check("parte en el resumen", v.sel is None)
check("sin clientes muestra la bienvenida", v.caja_bienvenida.winfo_manager() == "pack")
check("por cobrar parte en $0", v.lbl_por_cobrar.cget("text") == "$0")
for nombre in ("tv_cli", "tv_compras", "tv_pagos", "tv_mayores", "e_buscar", "e_fecha",
               "e_detalle", "e_monto", "btn_anotar", "btn_recibir", "btn_pagar_todo",
               "lbl_deuda", "lbl_aviso", "lbl_respaldo"):
    check("existe %s" % nombre, hasattr(v, nombre))

print("\n--- una sola ventana a la vez ---")
import instancia
candado = tempfile.mkdtemp()
check("la primera toma el candado", instancia.tomar(candado) is True)
check("una segunda ya no puede", instancia.tomar(candado) is False)

print("\n--- agregar un cliente con el dialogo ---")
dlg = app.DialogoCliente(v, v.datos)
dlg.e_nombre.poner("Juan Pérez")
dlg.e_tel.poner("9 1234 5678")
cid = dlg.aceptar()
dlg.destroy()
check("quedo creado", v.datos.cliente(cid)["nombre"] == "Juan Pérez")
dlg = app.DialogoCliente(v, v.datos)
dlg.e_tel.poner("hola")
check("en el telefono no entran letras", dlg.e_tel.valor() == "")
dlg.e_tel.poner("+56 9 1234-5678")
check("numeros, espacios, + y guion si", dlg.e_tel.valor() == "+56 9 1234-5678")
check("la pista del telefono se ve igual (no la bloquea el filtro)",
      app.Campo(dlg.cuerpo, pista="Ej: 9 1234 5678", tipo="telefono").get()
      == "Ej: 9 1234 5678")
dlg.e_nombre.poner("juan perez")
dlg._ok()
check("un nombre repetido muestra el aviso en el dialogo",
      "Ya hay un cliente" in dlg.lbl_error.cget("text"))
dlg.destroy()
v.datos.agregar_cliente("Ana Soto")
v.recargar_todo()
al_dia()
check("la lista muestra a los dos", len(v.tv_cli.get_children()) == 2)

print("\n--- buscar ---")
v.e_buscar.poner("perez")
v.recargar_clientes()
check("encuentra sin tilde", v.tv_cli.get_children() == (str(cid),))
v._buscar_enter()
al_dia()
check("Enter con uno solo lo abre", v.sel == cid)
v.e_buscar.limpiar()
v.recargar_clientes()

print("\n--- abrir su hoja no deja la ventana colgada ---")
v.mostrar_inicio()
v.tv_cli.selection_set(str(cid))
al_dia()
check("elegirlo en la lista abre su hoja", v.sel == cid)
check("muestra el nombre", v.lbl_nombre.cget("text") == "Juan Pérez")
check("al dia", v.lbl_deuda.cget("text") == "AL DÍA")
check("sin deuda no se puede recibir pago", not v.btn_recibir.activo)

print("\n--- anotar desde la fila de arriba ---")
v.e_detalle.poner("Molida 1 kg")
v.e_monto.poner("8.990")
v.anotar()
al_dia()
check("anotado", v.datos.deuda(cid) == 8990)
check("se limpio el detalle", v.e_detalle.valor() == "")
check("se limpio el monto", v.e_monto.valor() == "")
check("la deuda se ve arriba", v.lbl_deuda.cget("text") == "$8.990")
check("el total general se actualiza", v.lbl_por_cobrar.cget("text") == "$8.990")
check("aparece en la tabla", len(v.tv_compras.get_children()) == 1)
check("con el check para pagar", "Pagar" in v.tv_compras.item(
    v.tv_compras.get_children()[0], "values")[0])
check("avisa abajo", "Anotado" in v.lbl_aviso.cget("text"))
v.e_fecha.poner("ayer")
v.e_detalle.poner("Costillar 2 kg")
v.e_monto.poner("15000")
check("al salir de la casilla el monto se ordena con puntos", v.e_monto.valor() == "15.000")
v.anotar()
al_dia()
check("con fecha de ayer", v.datos.compras_de(cid)[-1]["fecha"] ==
      N.leer_fecha("ayer"))
check("15000 anotado", v.datos.deuda(cid) == 8990 + 15000)
v.e_monto.poner("abc")
check("en el monto no entran letras", v.e_monto.valor() == "")
v.e_monto.poner("12a5")
check("ni mezcladas con numeros", v.e_monto.valor() == "")
v.e_monto.poner("-500")
check("ni el signo menos", v.e_monto.valor() == "")
v.e_monto.limpiar(); v.e_monto._entrar()
v.e_monto.insert("insert", "123456789012")         # como si lo escribiera de golpe
check("ni un numero larguisimo", app.tk.Entry.get(v.e_monto) == "")
v.e_monto.poner("$12.500")
check("el signo $ y los puntos si", v.e_monto.valor() == "12.500")

# Escribir 10000 numero por numero: los puntos se van marcando solos.
v.e_monto.limpiar()
v.e_monto._entrar()          # como cuando se pincha la casilla: se va la pista gris
vistos = []
for tecla in "10000":
    v.e_monto.insert("insert", tecla)
    v.e_monto._marcar_miles()
    vistos.append(app.tk.Entry.get(v.e_monto))
check("escribiendo 10000 se marcan los puntos solos",
      vistos == ["1", "10", "100", "1.000", "10.000"])
v.e_monto.insert("insert", "0")
v.e_monto._marcar_miles()
check("y sigue al agregar otro cero", app.tk.Entry.get(v.e_monto) == "100.000")
v.e_monto.icursor(3)                       # el cursor se queda donde iba
v.e_monto.insert("insert", "5")
v.e_monto._marcar_miles()
check("corrigiendo al medio queda bien", app.tk.Entry.get(v.e_monto) == "1.005.000")
check("el cursor no se va al final", v.e_monto.index("insert") == 5)
v.e_monto.limpiar()
v.e_detalle.poner("algo")
v.anotar()
check("sin monto no se anota", v.datos.deuda(cid) == 8990 + 15000)
check("y lo dice", "monto" in v.lbl_aviso.cget("text"))
v.e_monto.poner("0")
v.anotar()
check("un monto cero no se anota", v.datos.deuda(cid) == 8990 + 15000)
v.e_detalle.limpiar(); v.e_detalle._entrar()
v.e_detalle.insert("insert", "x" * 200)
check("el detalle tiene largo maximo", app.tk.Entry.get(v.e_detalle) == "")
v.e_detalle.insert("insert", "x" * 80)
check("80 letras si caben", len(app.tk.Entry.get(v.e_detalle)) == 80)
v.e_detalle.limpiar()
v.e_monto.limpiar()
v.e_detalle.limpiar(); v.e_monto.limpiar()
v.e_fecha.poner("99/99")
check("una fecha mala se nota al tiro", v._revisar_fecha() is None)
v.e_fecha.limpiar()

print("\n--- el check de pagado ---")
molida = [c for c in v.datos.compras_de(cid) if c["detalle"] == "Molida 1 kg"][0]["id"]
v.cambiar_pagada(molida)
al_dia()
check("queda pagada", v.datos._compra(molida)["estado"] == N.PAGADA)
check("baja la deuda", v.lbl_deuda.cget("text") == "$15.000")
check("en 'Por pagar' ya no sale", str(molida) not in v.tv_compras.get_children())
v.cambiar_filtro("todas")
check("en 'Todas' sale con el check", "Pagada" in v.tv_compras.item(str(molida), "values")[0])
v.cambiar_pagada(molida)
al_dia()
check("otro clic la deja pendiente (preguntando)", v.datos._compra(molida)["estado"]
      == N.PENDIENTE and preguntas[-1] == "Volver a pendiente")

print("\n--- abonar ---")
check("el boton dice ABONAR", v.btn_recibir.cget("text") == "ABONAR")
dlg = app.DialogoPago(v, v._cl, v.datos)
check("parte sin monto", dlg.e_monto.valor() == "")
check("solo pregunta el monto", not hasattr(dlg, "e_fecha") and not hasattr(dlg, "e_nota"))
dlg.e_monto.poner("treinta")
check("en el abono no entran letras", dlg.e_monto.valor() == "")
dlg.e_monto.poner("10.000")
dlg._previa()
check("dice cuanto queda debiendo", dlg.lbl_prev.cget("text") == "Queda debiendo $13.990.")
r = dlg.aceptar()
check("el abono queda con la fecha de hoy", r["fecha"] == N.date.today().isoformat())
dlg.destroy()
v.recargar_todo()
al_dia()
check("abonado", v.datos.deuda(cid) == 8990 + 15000 - 10000)
check("sale en pagos recibidos", len(v.tv_pagos.get_children()) == 1)
dlg = app.DialogoPago(v, v._cl, v.datos)
dlg.e_monto.poner("999.999")
dlg._previa()
check("si paga de mas lo avisa con el vuelto", "vuelto" in dlg.lbl_prev.cget("text"))
dlg._ok()
check("y no lo acepta", "saldo a favor" in dlg.lbl_error.cget("text"))
dlg.destroy()

print("\n--- deshacer ese pago ---")
v.nb.select(v.tab_pagos)
v.tv_pagos.selection_set(v.tv_pagos.get_children()[0])
al_dia()
v.deshacer_pago()
al_dia()
check("vuelve la deuda", v.datos.deuda(cid) == 8990 + 15000)

print("\n--- pago todo ---")
v.pago_todo()
al_dia()
check("al dia", v.datos.deuda(cid) == 0 and v.lbl_deuda.cget("text") == "AL DÍA")

print("\n--- corregir y borrar ---")
v.e_detalle.poner("Pollo")
v.e_monto.poner("6500")
v.anotar()
al_dia()
pollo = [c for c in v.datos.compras_de(cid) if c["detalle"] == "Pollo"][0]
dlg = app.DialogoCompra(v, v.datos._compra(pollo["id"]))
check("el monto a corregir parte con puntos", dlg.e_monto.valor() == "6.500")
dlg.e_fecha.poner("31/12/2099")
dlg._ok()
check("no deja poner una fecha que no llega", "no llega" in dlg.lbl_error.cget("text"))
dlg.e_fecha.poner("hoy")
dlg.e_monto.poner("letras")
check("en corregir tampoco entran letras", dlg.e_monto.valor() == "")
dlg.e_monto.poner("6.990")
dlg.aceptar()
dlg.destroy()
check("corregido", v.datos._compra(pollo["id"])["monto"] == 6990)
v.recargar_todo()
v.tv_compras.selection_set(str(pollo["id"]))
v.borrar_compra()
al_dia()
check("borrado", v.datos.deuda(cid) == 0)

print("\n--- estado de cuenta y WhatsApp ---")
v.imprimir_estado()
ruta = [p for p in preguntas if str(p).startswith("abrir ")][-1][6:]
check("se armo el archivo", os.path.exists(ruta))
contenido = open(ruta, encoding="utf-8").read()
check("con el nombre", "Juan P&eacute;rez" in contenido or "Juan Pérez" in contenido)
check("con el logo", "data:image/png;base64," in contenido)
v.whatsapp()
check("abre WhatsApp (tiene telefono)", preguntas[-1] == "navegador")
check("y deja el mensaje copiado", "Hola Juan" in v.clipboard_get())

print("\n--- quitar de la lista ---")
v.quitar_cliente()
al_dia()
check("con historia queda archivado", not v.datos.cliente(cid)["activo"])
check("vuelve al resumen", v.sel is None)
check("ya no sale en la lista", str(cid) not in v.tv_cli.get_children())
v.var_archivados.set(True)
v.recargar_clientes()
check("sale con 'Mostrar archivados'", str(cid) in v.tv_cli.get_children())

print("\n--- resumen ---")
ana = [c for c in v.datos.clientes() if c["nombre"] == "Ana Soto"][0]["id"]
v.datos.anotar(ana, "Asado", 20000)
v.mostrar_inicio()
v.recargar_todo()
al_dia()
check("sale en los que deben", str(ana) in v.tv_mayores.get_children())
check("tarjeta por cobrar", v.tarjetas["por_cobrar"][1].cget("text") == "$20.000")

print("\n--- el resto de los botones ---")
v._ordenar("deuda")
check("ordenar por deuda: Ana primero", v.tv_cli.get_children()[0] == str(ana))
v._ordenar("nombre")
v.tv_mayores.selection_set(str(ana))
v._abrir_mayor()
al_dia()
check("doble clic en el resumen abre la hoja", v.sel == ana)
v.datos.anotar(ana, "Pollo", 5000)
v.datos.anotar(ana, "Longaniza", 3000)
v.recargar_todo()
v.tv_compras.selection_set(v.tv_compras.get_children())
v.marcar_pagadas()
al_dia()
check("marcar varias pagadas de una vez", v.datos.deuda(ana) == 0)
v.cambiar_filtro("todas")
v.tv_compras.selection_set(v.tv_compras.get_children())
v.marcar_pendientes()
al_dia()
check("y volverlas pendientes de una vez", v.datos.deuda(ana) == 28000)
v.mostrar_inicio()
v.abrir_cliente(cid)
v.reactivar_cliente()
al_dia()
check("un archivado vuelve a la lista", v.datos.cliente(cid)["activo"] == 1)
v.como_se_usa()
v.acerca_de()
check("ayuda y acerca de abren", preguntas[-2:] == ["Cómo se usa", "Acerca de"])
v.mostrar_inicio()
al_dia()

print("\n--- cerrar deja la copia del dia ---")
v.cerrar()
copias = os.listdir(os.path.join(N.carpeta_datos(), "respaldos"))
check("hay copia de hoy", any(N.date.today().isoformat() in c for c in copias))

print("\n--- la pantalla de carga al abrir ---")
os.environ["LIBRO_PRESENTACION_SEGUNDOS"] = "1"
visto = {}
v = app.App(presentacion=True)
check("mientras carga, la ventana esta escondida", v.state() == "withdrawn")
check("y se ve la pantalla de carga", v._splash is not None and v._splash.winfo_exists())
check("con el nombre del local", any(
    getattr(w, "cget", None) and "Carnicería El Buen Corte" in str(w.cget("text"))
    for w in v._splash.winfo_children()[0].winfo_children() if isinstance(w, app.tk.Label)))
check("dice lo que esta cargando", "Cargando" in v._splash.lbl.cget("text"))

def despues_de_cargar():
    visto["estado"] = v.state()
    visto["splash"] = v._splash
    v.cerrar()
v.after(2500, despues_de_cargar)
v.mainloop()
check("despues se abre la ventana", visto.get("estado") in ("normal", "zoomed"))
check("y la pantalla de carga se va", visto.get("splash", 1) is None)

print()
if fallas:
    print("FALLARON %d PRUEBAS:" % len(fallas))
    for f in fallas:
        print("  - " + f)
    sys.stdout.flush()
    os._exit(1)
print("Todo bien.")
sys.stdout.flush()
os._exit(0)
