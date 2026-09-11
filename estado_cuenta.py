# -*- coding: utf-8 -*-
"""
Estado de cuenta de un cliente, listo para imprimir o guardar como PDF.

Se arma como una pagina HTML y se abre en el navegador del computador: asi
se imprime con el dialogo de siempre de Windows (y ahi mismo se puede elegir
"Microsoft Print to PDF" para mandarlo por correo o WhatsApp).
"""
import html
import os
import re
from datetime import date, datetime

import nucleo as N

try:
    import imagen_marca
    LOGO = imagen_marca.IMPRESO
except Exception:                     # sin la imagen el papel igual sirve
    LOGO = ""


def _e(texto):
    return html.escape(str(texto or ""))


def armar(datos, cid, hoy=None):
    """Devuelve el HTML del estado de cuenta."""
    hoy = hoy or date.today()
    cl = datos.cliente(cid)
    if not cl:
        raise ValueError("Ese cliente ya no existe.")
    compras = datos.compras_de(cid)
    pend = sorted([c for c in compras if c["estado"] != N.PAGADA],
                  key=lambda c: (c["fecha"], c["id"]))
    movs = datos.movimientos(cid)
    total_fiado = sum(m["cargo"] for m in movs)
    total_pagado = sum(m["abono"] for m in movs)

    filas_pend = []
    for c in pend:
        filas_pend.append(
            "<tr><td>%s</td><td>%s</td><td class='n'>%s</td><td class='n'>%s</td>"
            "<td class='n fuerte'>%s</td></tr>"
            % (N.fecha_txt(c["fecha"]), _e(c["detalle"] or "Compra"),
               N.pesos(c["monto"]), N.pesos(c["abonado"]) if c["abonado"] else "&ndash;",
               N.pesos(c["falta"])))
    if not filas_pend:
        filas_pend.append("<tr><td colspan='5' class='vacio'>No hay nada pendiente. "
                          "La cuenta est&aacute; al d&iacute;a.</td></tr>")

    filas_mov = []
    for m in movs:
        es_pago = m["tipo"] == "pago"
        filas_mov.append(
            "<tr class='%s'><td>%s</td><td>%s</td><td class='n'>%s</td>"
            "<td class='n'>%s</td><td class='n'>%s</td></tr>"
            % ("pago" if es_pago else "", N.fecha_txt(m["fecha"]),
               ("Pago" + (" &middot; " + _e(m["detalle"]) if m["detalle"] != "Pago" else ""))
               if es_pago else _e(m["detalle"] or "Compra"),
               N.pesos(m["cargo"]) if m["cargo"] else "",
               N.pesos(m["abono"]) if m["abono"] else "",
               N.pesos(m["saldo"])))

    contacto = " &middot; ".join(x for x in (_e(cl["telefono"]), _e(cl["nota"])) if x)
    logo = ("<img class='logo' src='data:image/png;base64,%s' alt=''>" % LOGO) if LOGO else ""

    return PLANTILLA % {
        "titulo": _e("Estado de cuenta - %s" % cl["nombre"]),
        "logo": logo,
        "negocio": _e(N.NEGOCIO),
        "ciudad": _e(N.CIUDAD),
        "fecha": _e(N.fecha_larga(hoy.isoformat())),
        "cliente": _e(cl["nombre"]),
        "contacto": contacto,
        "deuda": N.pesos(cl["deuda"]),
        "estado": "Debe" if cl["deuda"] > 0 else "Al d&iacute;a",
        "clase_deuda": "debe" if cl["deuda"] > 0 else "aldia",
        "n_pend": len(pend),
        "total_fiado": N.pesos(total_fiado),
        "total_pagado": N.pesos(total_pagado),
        "filas_pend": "\n".join(filas_pend),
        "filas_mov": "\n".join(filas_mov) or
                     "<tr><td colspan='5' class='vacio'>Sin movimientos.</td></tr>",
        "generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def guardar(datos, cid, carpeta=None):
    """Escribe el estado de cuenta en la carpeta de datos y devuelve la ruta."""
    carpeta = carpeta or os.path.join(N.carpeta_datos(), "estados de cuenta")
    os.makedirs(carpeta, exist_ok=True)
    cl = datos.cliente(cid)
    nombre = re.sub(r"[^\w\- ]+", "", N._sin_tildes(cl["nombre"])).strip().replace(" ", "-")
    ruta = os.path.join(carpeta, "estado-%s-%s.html" % (nombre or "cliente",
                                                        date.today().isoformat()))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(armar(datos, cid))
    return ruta


PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>%(titulo)s</title>
<style>
  :root { --rojo:#C8202D; --rojo-osc:#A60D2B; --verde:#1F7A3D; --tinta:#1B1715;
          --suave:#6C625C; --linea:#DED7CF; --papel:#F4F1EC; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--papel); color:var(--tinta);
         font:14px/1.45 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
  .hoja { max-width:820px; margin:24px auto; background:#fff; padding:36px 44px 30px;
          box-shadow:0 1px 3px rgba(0,0,0,.12); border-top:6px solid var(--verde); }
  header { display:flex; align-items:center; gap:22px; padding-bottom:18px;
           border-bottom:2px solid var(--rojo-osc); }
  .logo { width:104px; height:104px; }
  .local h1 { margin:0; font-size:26px; color:var(--rojo); font-style:italic; }
  .local p { margin:2px 0 0; color:var(--suave); font-size:12px; letter-spacing:.08em;
             text-transform:uppercase; font-weight:600; }
  .doc { margin-left:auto; text-align:right; }
  .doc .t { font-size:12px; letter-spacing:.1em; text-transform:uppercase;
            color:var(--suave); font-weight:700; }
  .doc .f { font-size:13px; }
  .cliente { display:flex; justify-content:space-between; align-items:flex-end;
             gap:20px; margin:24px 0 8px; }
  .cliente .rot { font-size:11px; letter-spacing:.1em; text-transform:uppercase;
                  color:var(--suave); font-weight:700; }
  .cliente .nom { font-size:22px; font-weight:700; }
  .cliente .con { color:var(--suave); }
  .saldo { text-align:right; }
  .saldo .monto { font-size:32px; font-weight:800; line-height:1.1; }
  .debe .monto { color:var(--rojo-osc); }
  .aldia .monto { color:var(--verde); }
  .cifras { display:flex; gap:28px; color:var(--suave); font-size:13px; margin:6px 0 22px; }
  .cifras b { color:var(--tinta); }
  h2 { font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--suave);
       margin:26px 0 8px; }
  table { width:100%%; border-collapse:collapse; }
  th { text-align:left; font-size:11px; letter-spacing:.06em; text-transform:uppercase;
       color:#fff; background:var(--tinta); padding:7px 9px; }
  td { padding:7px 9px; border-bottom:1px solid var(--linea); vertical-align:top; }
  .n { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
  th.n { text-align:right; }
  .fuerte { font-weight:700; }
  tr.pago td { color:var(--verde); }
  tfoot td { font-weight:800; border-bottom:none; border-top:2px solid var(--tinta);
             font-size:15px; }
  .vacio { color:var(--suave); text-align:center; padding:18px; }
  footer { margin-top:30px; padding-top:12px; border-top:1px solid var(--linea);
           color:var(--suave); font-size:11px; display:flex; justify-content:space-between; }
  .acciones { max-width:820px; margin:18px auto 0; text-align:right; }
  .acciones button { font:inherit; font-weight:700; background:var(--rojo); color:#fff;
                     border:0; padding:10px 22px; cursor:pointer; border-radius:3px; }
  .acciones button:hover { background:var(--rojo-osc); }
  .acciones span { color:var(--suave); font-size:12px; margin-right:14px; }
  @media print {
    body { background:#fff; }
    .hoja { box-shadow:none; margin:0; max-width:none; padding:0; border-top:none; }
    .acciones { display:none; }
    th { -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  }
</style></head>
<body>
<div class="acciones">
  <span>Para guardarlo como PDF, elige &laquo;Microsoft Print to PDF&raquo; al imprimir.</span>
  <button onclick="window.print()">Imprimir</button>
</div>
<div class="hoja">
  <header>
    %(logo)s
    <div class="local"><h1>%(negocio)s</h1><p>%(ciudad)s</p></div>
    <div class="doc"><div class="t">Estado de cuenta</div><div class="f">%(fecha)s</div></div>
  </header>

  <section class="cliente">
    <div>
      <div class="rot">Cliente</div>
      <div class="nom">%(cliente)s</div>
      <div class="con">%(contacto)s</div>
    </div>
    <div class="saldo %(clase_deuda)s">
      <div class="rot">%(estado)s</div>
      <div class="monto">%(deuda)s</div>
    </div>
  </section>
  <div class="cifras">
    <span>Compras pendientes: <b>%(n_pend)s</b></span>
    <span>Total fiado: <b>%(total_fiado)s</b></span>
    <span>Total pagado: <b>%(total_pagado)s</b></span>
  </div>

  <h2>Lo que est&aacute; pendiente</h2>
  <table>
    <thead><tr><th>Fecha</th><th>Detalle</th><th class="n">Valor</th>
      <th class="n">Abonado</th><th class="n">Falta</th></tr></thead>
    <tbody>
%(filas_pend)s
    </tbody>
    <tfoot><tr><td colspan="4">Total pendiente</td><td class="n">%(deuda)s</td></tr></tfoot>
  </table>

  <h2>Historial de la cuenta</h2>
  <table>
    <thead><tr><th>Fecha</th><th>Movimiento</th><th class="n">Fiado</th>
      <th class="n">Pag&oacute;</th><th class="n">Saldo</th></tr></thead>
    <tbody>
%(filas_mov)s
    </tbody>
  </table>

  <footer><span>%(negocio)s &middot; %(ciudad)s</span>
          <span>Emitido el %(generado)s &middot; Libro de Fiados by Macoem</span></footer>
</div>
</body></html>
"""
