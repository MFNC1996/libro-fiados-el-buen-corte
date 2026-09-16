/*  Las cuentas del libro, aparte de la pantalla.
 *
 *  Esta es la misma logica que usa el programa del computador (nucleo.py):
 *  como se escribe la plata, como se entiende una fecha escrita a mano, cuando
 *  una compra esta pagada, y como se reparte un abono. Va en un archivo aparte
 *  para poder probarla sola, sin navegador: web/probar_cuentas.js.
 */
(function (raiz) {
  "use strict";

  var DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
  var DIAS_SIMPLE = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"];
  var MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"];
  var PENDIENTE = "pendiente", PARCIAL = "parcial", PAGADA = "pagada";

  /* 12500 -> "$12.500" */
  function pesos(n) {
    n = Math.round(Number(n) || 0);
    var signo = n < 0 ? "-" : "";
    return signo + "$" + Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  /* Lo que se escriba en la casilla del monto: "12.500", "$12.500" -> 12500 */
  function leerMonto(texto) {
    var t = String(texto == null ? "" : texto).replace(/[^\d]/g, "");
    var v = parseInt(t, 10);
    return v > 0 ? v : null;
  }

  function sinTildes(t) {
    return String(t == null ? "" : t).toLowerCase()
      .replace(/á/g, "a").replace(/é/g, "e").replace(/í/g, "i").replace(/ó/g, "o")
      .replace(/ú/g, "u").replace(/ü/g, "u").replace(/ñ/g, "n");
  }

  function iso(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" +
           String(d.getDate()).padStart(2, "0");
  }
  function hoyISO() { return iso(new Date()); }

  function fechaValida(a, m, d) {
    var f = new Date(a, m - 1, d);
    return (f.getFullYear() === a && f.getMonth() === m - 1 && f.getDate() === d) ? iso(f) : null;
  }

  /*
   * Entiende la fecha escrita como venga, igual que el computador:
   *   (vacio) hoy | ayer | 7 | 7/9 | 7/9/26 | 13 de octubre | martes | martes 13
   */
  function leerFecha(texto, hoy) {
    hoy = hoy || new Date();
    var t = sinTildes(texto).trim().replace(/,/g, " ");
    function menos(n) { var d = new Date(hoy); d.setDate(d.getDate() - n); return iso(d); }
    if (t === "" || t === "hoy") return iso(hoy);
    if (t === "ayer") return menos(1);
    if (t === "anteayer" || t === "antier") return menos(2);
    var m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (m) return fechaValida(+m[1], +m[2], +m[3]);

    var diaSemana = null, palabras = [];
    t.split(/\s+/).forEach(function (p) {
      var i = DIAS_SIMPLE.indexOf(p);
      var j = MESES.map(sinTildes).indexOf(sinTildes(p));
      if (i >= 0) diaSemana = i;
      else if (j >= 0) palabras.push("/", String(j + 1));
      else if (["el", "de", "del", "dia", "pasado"].indexOf(p) < 0) palabras.push(p);
    });
    t = palabras.join(" ").trim();

    if (!t) {
      if (diaSemana === null) return null;
      return menos(((hoy.getDay() + 6) % 7 - diaSemana + 7) % 7);
    }
    var partes = t.split(/[/\-. ]+/).filter(function (p) { return p !== ""; });
    if (!partes.length || partes.length > 3 ||
        partes.some(function (p) { return !/^\d+$/.test(p); })) return null;
    var n = partes.map(Number), f;
    if (n.length === 1) {
      if (diaSemana !== null) {                       // "martes 13": el ultimo que cayo martes
        var a = hoy.getFullYear(), mes = hoy.getMonth() + 1;
        for (var i = 0; i < 15; i++) {
          f = fechaValida(a, mes, n[0]);
          if (f && f <= iso(hoy) &&
              (new Date(a, mes - 1, n[0]).getDay() + 6) % 7 === diaSemana) return f;
          if (mes > 1) { mes--; } else { mes = 12; a--; }
        }
      }
      f = fechaValida(hoy.getFullYear(), hoy.getMonth() + 1, n[0]);
      if (f && f > iso(hoy)) {                        // el 28 escrito un dia 3: mes pasado
        var ant = new Date(hoy.getFullYear(), hoy.getMonth(), 0);
        f = fechaValida(ant.getFullYear(), ant.getMonth() + 1, n[0]);
      }
      return f;
    }
    if (n.length === 2) {
      f = fechaValida(hoy.getFullYear(), n[1], n[0]);
      if (f && f > iso(hoy)) f = fechaValida(hoy.getFullYear() - 1, n[1], n[0]);
      return f;
    }
    return fechaValida(n[2] < 100 ? 2000 + n[2] : n[2], n[1], n[0]);
  }

  function fechaCorta(f, hoy) {
    if (!f) return "";
    var p = String(f).slice(0, 10).split("-");
    var anio = String((hoy || new Date()).getFullYear());
    return p[2] + "/" + p[1] + (p[0] === anio ? "" : "/" + p[0].slice(2));
  }
  function fechaTxt(f) {
    if (!f) return "";
    var p = String(f).slice(0, 10).split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
  }
  function haceCuanto(f, hoy) {
    if (!f) return "";
    var dias = Math.round((new Date(iso(hoy || new Date())) -
                           new Date(String(f).slice(0, 10))) / 86400000);
    if (dias <= 0) return "hoy";
    if (dias === 1) return "ayer";
    if (dias < 60) return "hace " + dias + " días";
    return "hace " + Math.floor(dias / 30) + " meses";
  }
  function diaYFecha(f) {
    var d = new Date(String(f).slice(0, 10) + "T12:00:00");
    return DIAS[(d.getDay() + 6) % 7] + " " + fechaCorta(f);
  }

  /* Numero para abrir WhatsApp (Chile), o null. */
  function telefonoWhatsapp(tel) {
    var d = String(tel == null ? "" : tel).replace(/\D/g, "");
    if (d.length === 8) return "569" + d;
    if (d.length === 9 && d[0] === "9") return "56" + d;
    if (d.length === 11 && d.slice(0, 2) === "56") return d;
    return null;
  }

  function escapar(t) {
    return String(t == null ? "" : t).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /*
   * Deja cada compra con lo abonado, lo que falta y su estado, y cada cliente
   * con lo que debe. Es la misma cuenta que hace el computador.
   */
  function recalcular(D) {
    var abonado = {}, pagadaEl = {}, pagoPorId = {};
    D.pagos.forEach(function (p) { pagoPorId[p.id] = p; });
    D.aplicaciones.forEach(function (a) {
      abonado[a.compra_id] = (abonado[a.compra_id] || 0) + a.monto;
      var p = pagoPorId[a.pago_id];
      if (p && (!pagadaEl[a.compra_id] || p.fecha > pagadaEl[a.compra_id])) {
        pagadaEl[a.compra_id] = p.fecha;
      }
    });
    D.compras.forEach(function (c) {
      c.abonado = abonado[c.id] || 0;
      c.falta = c.monto - c.abonado;
      c.estado = c.falta <= 0 ? PAGADA : (c.abonado > 0 ? PARCIAL : PENDIENTE);
      c.pagada_el = c.estado === PAGADA ? (pagadaEl[c.id] || null) : null;
    });
    D.clientes.forEach(function (cl) {
      var suyas = D.compras.filter(function (c) { return c.cliente_id === cl.id; });
      var pend = suyas.filter(function (c) { return c.falta > 0; });
      cl.deuda = pend.reduce(function (s, c) { return s + c.falta; }, 0);
      cl.pendientes = pend.length;
      cl.mas_antigua = pend.length
        ? pend.map(function (c) { return c.fecha; }).sort()[0] : null;
      var pagos = D.pagos.filter(function (p) { return p.cliente_id === cl.id; })
                         .map(function (p) { return p.fecha; }).sort();
      cl.ultimo_pago = pagos.length ? pagos[pagos.length - 1] : null;
      cl.total_fiado = suyas.reduce(function (s, c) { return s + c.monto; }, 0);
    });
    D.clientes.sort(function (a, b) {
      return sinTildes(a.nombre).localeCompare(sinTildes(b.nombre));
    });
    var nuevoPrimero = function (a, b) {
      return (b.fecha + (b.creado || "")).localeCompare(a.fecha + (a.creado || ""));
    };
    D.compras.sort(nuevoPrimero);
    D.pagos.sort(nuevoPrimero);
    return D;
  }

  /*
   * Como se reparte un abono: desde la compra mas antigua, igual que en el
   * computador. Devuelve a que compra va cada parte.
   */
  function repartir(pendientes, monto) {
    var orden = pendientes.slice().sort(function (a, b) {
      return (a.fecha + (a.creado || "")).localeCompare(b.fecha + (b.creado || ""));
    });
    var resto = monto, partes = [];
    orden.forEach(function (c) {
      if (resto <= 0) return;
      var parte = Math.min(resto, c.falta);
      partes.push({ compra: c, monto: parte });
      resto -= parte;
    });
    return partes;
  }

  function textoWhatsapp(cliente, compras, negocio) {
    negocio = negocio || "Carnicería El Buen Corte";
    var nombre = String(cliente.nombre || "").split(" ")[0];
    var pend = compras.filter(function (c) { return c.falta > 0; })
                      .sort(function (a, b) { return a.fecha.localeCompare(b.fecha); });
    if (!pend.length) {
      return "Hola " + nombre + ", te saludamos de " + negocio + ". Tu cuenta está al día, " +
             "no tienes nada pendiente. ¡Gracias!";
    }
    var total = pend.reduce(function (s, c) { return s + c.falta; }, 0);
    return "Hola " + nombre + ", te saludamos de " + negocio + ".\n" +
      "Te dejamos el detalle de tu cuenta pendiente:\n\n" +
      pend.map(function (c) {
        return "- " + fechaCorta(c.fecha) + "  " + (c.detalle || "Compra") + "  " +
               pesos(c.falta) + (c.abonado ? " (abonado " + pesos(c.abonado) + ")" : "");
      }).join("\n") + "\n\nTotal pendiente: " + pesos(total) + "\n\n¡Gracias!";
  }

  var Cuentas = {
    DIAS: DIAS, MESES: MESES,
    PENDIENTE: PENDIENTE, PARCIAL: PARCIAL, PAGADA: PAGADA,
    pesos: pesos, leerMonto: leerMonto, sinTildes: sinTildes, iso: iso, hoyISO: hoyISO,
    leerFecha: leerFecha, fechaCorta: fechaCorta, fechaTxt: fechaTxt,
    haceCuanto: haceCuanto, diaYFecha: diaYFecha, telefonoWhatsapp: telefonoWhatsapp,
    escapar: escapar, recalcular: recalcular, repartir: repartir,
    textoWhatsapp: textoWhatsapp
  };

  if (typeof module !== "undefined" && module.exports) module.exports = Cuentas;
  else raiz.Cuentas = Cuentas;
})(typeof self !== "undefined" ? self : this);
