/*  Libro de Fiados - la misma libreta, en el celular.
 *
 *  Las cuentas se hacen igual que en el programa del computador: una compra
 *  esta pagada cuando lo abonado alcanza su monto, y un abono se reparte
 *  desde la compra mas antigua. Los datos son los mismos: los dos hablan con
 *  la misma base de datos.
 */
"use strict";

const URL_NUBE = "https://zczlopvgnfwghlaykmph.supabase.co";
const ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpjemxvc" +
             "HZnbmZ3Z2hsYXlrbXBoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk1MjM4NzUsImV4cCI6MjEwNTA5OTg3NX0" +
             ".Nf4ZEI1bOM8Mhfxz6xI0bqM2SeH3ZI_vCWxknCuC_Ek";
const LOCAL_ID = "ce58ba0c-aedd-47ad-8ea1-b42138b05389";
const CADA = 10000;                       // cada cuanto se mira si hubo cambios

const sb = window.supabase.createClient(URL_NUBE, ANON);
const $ = (id) => document.getElementById(id);

let D = { clientes: [], compras: [], pagos: [], aplicaciones: [] };
let abierto = null;                       // cliente abierto
let filtro = "pendientes";
let pestana = "compras";
let ocupado = false;                      // hay una ventanita abierta

/* ============================================================ formatos */
function pesos(n) {
  n = Math.round(Number(n) || 0);
  const signo = n < 0 ? "-" : "";
  return signo + "$" + Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function leerMonto(texto) {
  const t = String(texto || "").replace(/[^\d]/g, "");
  const v = parseInt(t, 10);
  return v > 0 ? v : null;
}

const DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const DIAS_SIMPLE = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"];

const sinTildes = (t) => String(t || "").toLowerCase()
  .replace(/á/g, "a").replace(/é/g, "e").replace(/í/g, "i").replace(/ó/g, "o")
  .replace(/ú/g, "u").replace(/ü/g, "u").replace(/ñ/g, "n");

function iso(d) {
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" +
         String(d.getDate()).padStart(2, "0");
}
const hoyISO = () => iso(new Date());

function fechaValida(a, m, d) {
  const f = new Date(a, m - 1, d);
  return (f.getFullYear() === a && f.getMonth() === m - 1 && f.getDate() === d) ? iso(f) : null;
}

/* Entiende la fecha escrita como venga, igual que el programa del computador. */
function leerFecha(texto, hoy) {
  hoy = hoy || new Date();
  let t = sinTildes(texto).trim().replace(/,/g, " ");
  if (t === "" || t === "hoy") return iso(hoy);
  const menos = (n) => { const d = new Date(hoy); d.setDate(d.getDate() - n); return iso(d); };
  if (t === "ayer") return menos(1);
  if (t === "anteayer" || t === "antier") return menos(2);
  let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return fechaValida(+m[1], +m[2], +m[3]);

  let diaSemana = null;
  const palabras = [];
  t.split(/\s+/).forEach((p) => {
    if (DIAS_SIMPLE.indexOf(p) >= 0) diaSemana = DIAS_SIMPLE.indexOf(p);
    else if (MESES.indexOf(sinTildes(p)) >= 0) palabras.push("/", String(MESES.indexOf(sinTildes(p)) + 1));
    else if (["el", "de", "del", "dia", "pasado"].indexOf(p) < 0) palabras.push(p);
  });
  t = palabras.join(" ").trim();

  if (!t) {
    if (diaSemana === null) return null;
    const hoyDia = (hoy.getDay() + 6) % 7;            // lunes = 0
    return menos((hoyDia - diaSemana + 7) % 7);
  }
  const partes = t.split(/[/\-. ]+/).filter((p) => p !== "");
  if (!partes.length || partes.length > 3 || partes.some((p) => !/^\d+$/.test(p))) return null;
  const n = partes.map(Number);
  if (n.length === 1) {
    if (diaSemana !== null) {                          // "martes 13"
      let a = hoy.getFullYear(), mes = hoy.getMonth() + 1;
      for (let i = 0; i < 15; i++) {
        const f = fechaValida(a, mes, n[0]);
        if (f && f <= iso(hoy) && (new Date(a, mes - 1, n[0]).getDay() + 6) % 7 === diaSemana) return f;
        if (mes > 1) { mes--; } else { mes = 12; a--; }
      }
    }
    let f = fechaValida(hoy.getFullYear(), hoy.getMonth() + 1, n[0]);
    if (f && f > iso(hoy)) {
      const ant = new Date(hoy.getFullYear(), hoy.getMonth(), 0);
      f = fechaValida(ant.getFullYear(), ant.getMonth() + 1, n[0]);
    }
    return f;
  }
  if (n.length === 2) {
    let f = fechaValida(hoy.getFullYear(), n[1], n[0]);
    if (f && f > iso(hoy)) f = fechaValida(hoy.getFullYear() - 1, n[1], n[0]);
    return f;
  }
  return fechaValida(n[2] < 100 ? 2000 + n[2] : n[2], n[1], n[0]);
}

function fechaCorta(f) {
  if (!f) return "";
  const p = String(f).slice(0, 10).split("-");
  return p[2] + "/" + p[1] + (p[0] === String(new Date().getFullYear()) ? "" : "/" + p[0].slice(2));
}
function fechaTxt(f) {
  if (!f) return "";
  const p = String(f).slice(0, 10).split("-");
  return p[2] + "/" + p[1] + "/" + p[0];
}
function haceCuanto(f) {
  if (!f) return "";
  const dias = Math.round((new Date(hoyISO()) - new Date(String(f).slice(0, 10))) / 86400000);
  if (dias <= 0) return "hoy";
  if (dias === 1) return "ayer";
  if (dias < 60) return "hace " + dias + " días";
  return "hace " + Math.floor(dias / 30) + " meses";
}
function diaYFecha(f) {
  const d = new Date(String(f).slice(0, 10) + "T12:00:00");
  return DIAS[(d.getDay() + 6) % 7] + " " + fechaCorta(f);
}
function telefonoWhatsapp(tel) {
  const d = String(tel || "").replace(/\D/g, "");
  if (d.length === 8) return "569" + d;
  if (d.length === 9 && d[0] === "9") return "56" + d;
  if (d.length === 11 && d.slice(0, 2) === "56") return d;
  return null;
}
const escapar = (t) => String(t == null ? "" : t)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/* ======================================================== los datos */
async function cargar() {
  const pedir = (tabla) => sb.from(tabla).select("*").eq("local_id", LOCAL_ID)
                             .eq("borrado", false).limit(5000);
  const [cl, co, pa, ap] = await Promise.all(
    ["clientes", "compras", "pagos", "aplicaciones"].map(pedir));
  for (const r of [cl, co, pa, ap]) if (r.error) throw r.error;
  D = { clientes: cl.data, compras: co.data, pagos: pa.data, aplicaciones: ap.data };
  recalcular();
}

function recalcular() {
  const abonado = {}, pagadaEl = {};
  const pagoPorId = {};
  D.pagos.forEach((p) => { pagoPorId[p.id] = p; });
  D.aplicaciones.forEach((a) => {
    abonado[a.compra_id] = (abonado[a.compra_id] || 0) + a.monto;
    const p = pagoPorId[a.pago_id];
    if (p && (!pagadaEl[a.compra_id] || p.fecha > pagadaEl[a.compra_id])) {
      pagadaEl[a.compra_id] = p.fecha;
    }
  });
  D.compras.forEach((c) => {
    c.abonado = abonado[c.id] || 0;
    c.falta = c.monto - c.abonado;
    c.estado = c.falta <= 0 ? "pagada" : (c.abonado > 0 ? "parcial" : "pendiente");
    c.pagada_el = c.estado === "pagada" ? pagadaEl[c.id] : null;
  });
  D.clientes.forEach((cl) => {
    const suyas = D.compras.filter((c) => c.cliente_id === cl.id);
    const pend = suyas.filter((c) => c.falta > 0);
    cl.deuda = pend.reduce((s, c) => s + c.falta, 0);
    cl.pendientes = pend.length;
    cl.mas_antigua = pend.length ? pend.map((c) => c.fecha).sort()[0] : null;
    const pagos = D.pagos.filter((p) => p.cliente_id === cl.id).map((p) => p.fecha).sort();
    cl.ultimo_pago = pagos.length ? pagos[pagos.length - 1] : null;
  });
  D.clientes.sort((a, b) => sinTildes(a.nombre).localeCompare(sinTildes(b.nombre)));
  D.compras.sort((a, b) => (b.fecha + b.creado).localeCompare(a.fecha + a.creado));
  D.pagos.sort((a, b) => (b.fecha + b.creado).localeCompare(a.fecha + a.creado));
}

const nuevoId = () => (crypto.randomUUID ? crypto.randomUUID() :
  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16);
  }));

async function insertar(tabla, fila) {
  const { error } = await sb.from(tabla).insert(Object.assign(
    { id: nuevoId(), local_id: LOCAL_ID }, fila));
  if (error) throw error;
}
async function cambiar(tabla, id, campos) {
  const { error } = await sb.from(tabla).update(campos).eq("id", id);
  if (error) throw error;
}

/* ================================================== las operaciones */
async function anotar(clienteId, detalle, monto, fecha) {
  await insertar("compras", { cliente_id: clienteId, fecha: fecha,
                              detalle: String(detalle || "").trim(), monto: monto });
}

async function marcarPagada(compra) {
  if (compra.falta <= 0) return 0;
  const pago = nuevoId();
  let { error } = await sb.from("pagos").insert({
    id: pago, local_id: LOCAL_ID, cliente_id: compra.cliente_id,
    fecha: hoyISO(), monto: compra.falta, nota: "" });
  if (error) throw error;
  await insertar("aplicaciones", { pago_id: pago, compra_id: compra.id, monto: compra.falta });
  return compra.falta;
}

async function marcarPendiente(compra) {
  const apls = D.aplicaciones.filter((a) => a.compra_id === compra.id);
  for (const a of apls) {
    await cambiar("aplicaciones", a.id, { borrado: true });
    const pago = D.pagos.find((p) => p.id === a.pago_id);
    if (!pago) continue;
    const queda = pago.monto - a.monto;
    await cambiar("pagos", pago.id, queda > 0 ? { monto: queda } : { borrado: true, monto: 1 });
    pago.monto = queda;
  }
  return compra.abonado;
}

/* El abono se descuenta desde la compra mas antigua, igual que en el computador. */
async function recibirPago(cliente, monto, fecha) {
  const pend = D.compras.filter((c) => c.cliente_id === cliente.id && c.falta > 0)
                        .sort((a, b) => (a.fecha + a.creado).localeCompare(b.fecha + b.creado));
  const deuda = pend.reduce((s, c) => s + c.falta, 0);
  if (deuda <= 0) throw new Error("No hay nada pendiente que pagar.");
  if (monto > deuda) throw new Error("Está pagando " + pesos(monto) + ", pero debe " +
    pesos(deuda) + ". El libro no guarda saldo a favor.");
  const pago = nuevoId();
  let { error } = await sb.from("pagos").insert({
    id: pago, local_id: LOCAL_ID, cliente_id: cliente.id, fecha: fecha, monto: monto, nota: "" });
  if (error) throw error;
  let resto = monto;
  for (const c of pend) {
    if (resto <= 0) break;
    const parte = Math.min(resto, c.falta);
    await insertar("aplicaciones", { pago_id: pago, compra_id: c.id, monto: parte });
    resto -= parte;
  }
}

async function borrarPago(pago) {
  for (const a of D.aplicaciones.filter((x) => x.pago_id === pago.id)) {
    await cambiar("aplicaciones", a.id, { borrado: true });
  }
  await cambiar("pagos", pago.id, { borrado: true });
}

/* ========================================================= pantallas */
function mostrarAviso(texto, malo) {
  const a = $("aviso");
  a.textContent = texto;
  a.className = "aviso " + (malo ? "mal" : "ok");
  clearTimeout(mostrarAviso.reloj);
  mostrarAviso.reloj = setTimeout(() => a.classList.add("oculto"), 6000);
}

function pintar() {
  const total = D.clientes.reduce((s, c) => s + c.deuda, 0);
  $("por-cobrar").textContent = pesos(total);
  pintarLista();
  if (abierto) {
    const cl = D.clientes.find((c) => c.id === abierto);
    if (!cl) { volverALaLista(); } else { pintarHoja(cl); }
  }
}

function pintarLista() {
  const busca = sinTildes($("buscar").value).trim();
  const soloDeben = $("solo-deben").checked;
  let lista = D.clientes.filter((c) => c.activo !== false);
  if (soloDeben) lista = lista.filter((c) => c.deuda > 0);
  if (busca) lista = lista.filter((c) => sinTildes(c.nombre).indexOf(busca) >= 0 ||
                                          sinTildes(c.telefono).indexOf(busca) >= 0);
  const caja = $("lista");
  if (!lista.length) {
    caja.innerHTML = '<p class="vacio">' + (busca ? "Nadie se llama así."
      : "Todavía no hay clientes. Agrega el primero con el botón rojo.") + "</p>";
    return;
  }
  caja.innerHTML = lista.map((c) => {
    const det = c.deuda > 0
      ? c.pendientes + (c.pendientes === 1 ? " compra sin pagar" : " compras sin pagar") +
        " · desde " + haceCuanto(c.mas_antigua)
      : (c.ultimo_pago ? "Último pago: " + fechaCorta(c.ultimo_pago) : "No debe nada");
    return '<button class="cliente" data-cliente="' + c.id + '">' +
      '<span class="quien"><b>' + escapar(c.nombre) + "</b><small>" + escapar(det) + "</small></span>" +
      '<span class="debe' + (c.deuda > 0 ? '"' : ' aldia"') + ">" +
      (c.deuda > 0 ? pesos(c.deuda) : "al día") + "</span></button>";
  }).join("");
}

function pintarHoja(cl) {
  $("h-nombre").textContent = cl.nombre;
  const datos = [];
  if (cl.telefono) datos.push("Tel. " + cl.telefono);
  if (cl.nota) datos.push(cl.nota);
  $("h-datos").textContent = datos.join("   ·   ");
  const deuda = $("h-deuda");
  if (cl.deuda > 0) {
    $("h-rotulo").textContent = "Debe";
    deuda.textContent = pesos(cl.deuda);
    deuda.className = "monto";
    $("h-detalle").textContent = cl.pendientes + (cl.pendientes === 1 ? " compra" : " compras") +
      " sin pagar · desde " + haceCuanto(cl.mas_antigua);
  } else {
    $("h-rotulo").textContent = "Cuenta";
    deuda.textContent = "AL DÍA";
    deuda.className = "monto aldia";
    $("h-detalle").textContent = cl.ultimo_pago ? "Último pago: " + fechaCorta(cl.ultimo_pago)
                                                : "No debe nada";
  }
  $("btn-abonar").disabled = cl.deuda <= 0;
  $("btn-pago-todo").disabled = cl.deuda <= 0;

  const suyas = D.compras.filter((c) => c.cliente_id === cl.id);
  const cuenta = { todas: suyas.length,
                   pendientes: suyas.filter((c) => c.estado !== "pagada").length,
                   pagadas: suyas.filter((c) => c.estado === "pagada").length };
  document.querySelectorAll("[data-filtro]").forEach((b) => {
    const base = { pendientes: "Por pagar", todas: "Todas", pagadas: "Pagadas" }[b.dataset.filtro];
    b.textContent = base + "  " + cuenta[b.dataset.filtro];
    b.classList.toggle("activa", b.dataset.filtro === filtro);
  });
  const ver = filtro === "todas" ? suyas
    : suyas.filter((c) => (filtro === "pagadas") === (c.estado === "pagada"));
  $("compras").innerHTML = ver.length ? ver.map((c) => {
    const estado = c.estado === "pagada" ? "Pagada el " + fechaCorta(c.pagada_el)
      : (c.estado === "parcial" ? "Abonó " + pesos(c.abonado) : "Pendiente");
    return '<div class="compra ' + c.estado + '">' +
      '<button class="check" data-check="' + c.id + '" title="Marcar">' +
        (c.estado === "pagada" ? "☑" : "☐") + "</button>" +
      '<span class="que"><b>' + escapar(c.detalle || "—") + "</b><small>" +
        fechaCorta(c.fecha) + " · " + estado + "</small></span>" +
      '<span class="plata"><b>' + pesos(c.monto) + "</b>" +
        (c.falta > 0 && c.abonado > 0 ? "<small>falta " + pesos(c.falta) + "</small>" : "") +
      "</span>" +
      '<button class="mas" data-compra="' + c.id + '" title="Corregir o borrar">⋯</button></div>';
  }).join("") : '<p class="vacio">' + { pendientes: "No hay nada por pagar.",
      pagadas: "Todavía no hay compras pagadas.",
      todas: "Todavía no se le ha anotado nada." }[filtro] + "</p>";

  const pagos = D.pagos.filter((p) => p.cliente_id === cl.id);
  $("p-pagos").textContent = "Pagos y abonos (" + pagos.length + ")";
  $("pagos").innerHTML = pagos.length ? pagos.map((p) => {
    const aque = D.aplicaciones.filter((a) => a.pago_id === p.id).map((a) => {
      const c = D.compras.find((x) => x.id === a.compra_id);
      return c ? fechaCorta(c.fecha) + " " + (c.detalle || "compra") +
                 (a.monto < c.monto ? " (abono " + pesos(a.monto) + ")" : "") : "";
    }).filter(Boolean).join(",  ");
    return '<div class="compra">' +
      '<span class="que"><b>' + pesos(p.monto) + "</b><small>" + fechaCorta(p.fecha) +
        (aque ? " · se descontó de " + escapar(aque) : "") + "</small></span>" +
      '<button class="mas" data-pago="' + p.id + '" title="Deshacer">⋯</button></div>';
  }).join("") : '<p class="vacio">Todavía no hay pagos ni abonos.</p>';
}

function abrirCliente(id) {
  abierto = id;
  filtro = "pendientes";
  $("panel").classList.add("chico");
  if (window.innerWidth < 900) $("panel").classList.add("oculto");
  $("hoja").classList.remove("oculto");
  window.scrollTo(0, 0);
  pintar();
}

function volverALaLista() {
  abierto = null;
  $("hoja").classList.add("oculto");
  $("panel").classList.remove("oculto");
  pintar();
}

/* ======================================================= ventanitas */
function ventanita(titulo, subtitulo, cuerpo, alAceptar, textoOk, estiloOk) {
  ocupado = true;
  $("ventanita").innerHTML =
    '<div class="fondo"><div class="ventanita"><h2>' + escapar(titulo) + "</h2>" +
    (subtitulo ? '<p class="sub">' + subtitulo + "</p>" : "") + cuerpo +
    '<p class="error oculto" id="v-error"></p>' +
    '<div class="pie"><button class="boton" id="v-cancelar">Cancelar</button>' +
    '<button class="boton ' + (estiloOk || "rojo") + '" id="v-ok">' +
    escapar(textoOk || "Guardar") + "</button></div></div></div>";
  const cerrar = () => { ocupado = false; $("ventanita").innerHTML = ""; };
  $("v-cancelar").onclick = cerrar;
  $("v-ok").onclick = async () => {
    $("v-ok").disabled = true;
    try {
      await alAceptar();
      cerrar();
      await refrescar();
    } catch (e) {
      $("v-error").textContent = e.message || String(e);
      $("v-error").classList.remove("oculto");
      $("v-ok").disabled = false;
    }
  };
  document.querySelectorAll(".ventanita input").forEach(marcarMilesEn);
  const primero = document.querySelector(".ventanita input");
  if (primero) primero.focus();
  return cerrar;
}

function campo(id, rotulo, valor, extra) {
  return '<label class="campo"><span class="rotulo">' + rotulo + "</span>" +
         '<input type="text" id="' + id + '" value="' + escapar(valor || "") + '" ' +
         (extra || "") + "></label>";
}

function nuevoCliente() {
  ventanita("Nuevo cliente", "Cada cliente tiene su propia hoja.",
    campo("v-nombre", "Nombre", $("buscar").value, 'placeholder="Ej: Juan Pérez"') +
    campo("v-tel", "Teléfono (opcional)", "", 'inputmode="tel" placeholder="Ej: 9 1234 5678"') +
    campo("v-nota", "Nota (opcional)", "", 'placeholder="Ej: vecino del frente"'),
    async () => {
      const nombre = $("v-nombre").value.trim().replace(/\s+/g, " ");
      if (!nombre) throw new Error("Escribe el nombre del cliente.");
      if (D.clientes.some((c) => c.activo !== false &&
          sinTildes(c.nombre).trim() === sinTildes(nombre).trim())) {
        throw new Error('Ya hay un cliente que se llama "' + nombre + '".');
      }
      await insertar("clientes", { nombre: nombre, telefono: $("v-tel").value.trim(),
                                   nota: $("v-nota").value.trim() });
      mostrarAviso("Cliente agregado.");
    }, "Agregar cliente");
}

function editarCliente(cl) {
  ventanita("Editar datos", escapar(cl.nombre),
    campo("v-nombre", "Nombre", cl.nombre) +
    campo("v-tel", "Teléfono (opcional)", cl.telefono, 'inputmode="tel"') +
    campo("v-nota", "Nota (opcional)", cl.nota),
    async () => {
      const nombre = $("v-nombre").value.trim().replace(/\s+/g, " ");
      if (!nombre) throw new Error("El nombre no puede quedar vacío.");
      await cambiar("clientes", cl.id, { nombre: nombre, telefono: $("v-tel").value.trim(),
                                         nota: $("v-nota").value.trim() });
      mostrarAviso("Datos guardados.");
    });
}

function quitarCliente(cl) {
  if (cl.deuda > 0) {
    return mostrarAviso(cl.nombre + " todavía debe " + pesos(cl.deuda) +
                        ": no se puede quitar.", true);
  }
  const tiene = D.compras.some((c) => c.cliente_id === cl.id) ||
                D.pagos.some((p) => p.cliente_id === cl.id);
  ventanita("Quitar de la lista", "¿Quitar a " + escapar(cl.nombre) + "?",
    "<p>" + (tiene ? "Como tiene compras anotadas, queda archivado con toda su historia."
                   : "No tiene nada anotado, así que se borra.") + "</p>",
    async () => {
      await cambiar("clientes", cl.id, tiene ? { activo: false } : { borrado: true });
      abierto = null;
      mostrarAviso(cl.nombre + (tiene ? " quedó archivado." : " se borró."));
    }, "Quitar");
}

function abonar(cl) {
  ventanita("Abonar", "Debe <b>" + pesos(cl.deuda) + "</b>",
    campo("v-monto", "¿Cuánto abona?", "", 'inputmode="numeric" placeholder="$"') +
    '<p class="previa" id="v-previa"></p>',
    async () => {
      const monto = leerMonto($("v-monto").value);
      if (!monto) throw new Error("Escribe cuánto abona.");
      await recibirPago(cl, monto, hoyISO());
      mostrarAviso("Abono de " + pesos(monto) + " anotado.");
    }, "Registrar abono", "verde");
  const previa = () => {
    const monto = leerMonto($("v-monto").value);
    const p = $("v-previa");
    if (!monto) { p.textContent = ""; return; }
    if (monto > cl.deuda) {
      p.style.color = "var(--rojo)";
      p.textContent = "Es más de lo que debe. El vuelto es " + pesos(monto - cl.deuda) + ".";
    } else {
      p.style.color = "var(--verde)";
      p.textContent = monto === cl.deuda ? "Queda al día."
        : "Queda debiendo " + pesos(cl.deuda - monto) + ".";
    }
  };
  $("v-monto").addEventListener("input", previa);
}

function pagoTodo(cl) {
  ventanita("Pagó todo", "¿" + escapar(cl.nombre) + " pagó todo lo que debe?",
    "<p>Se anota un pago de <b>" + pesos(cl.deuda) + "</b> con fecha de hoy y todas sus " +
    "compras quedan pagadas.</p>",
    async () => {
      await recibirPago(cl, cl.deuda, hoyISO());
      mostrarAviso(cl.nombre + " quedó al día.");
    }, "Sí, pagó todo", "verde");
}

function tocarCompra(c) {
  const pagada = c.estado === "pagada";
  ventanita(c.detalle || "Compra",
    fechaCorta(c.fecha) + " · " + pesos(c.monto) +
      (c.abonado ? " · abonado " + pesos(c.abonado) : ""),
    campo("v-fecha", "Fecha", fechaTxt(c.fecha)) +
    campo("v-detalle", "Qué llevó", c.detalle) +
    campo("v-monto", "Monto", pesos(c.monto).slice(1), 'inputmode="numeric"') +
    '<button class="boton ancho" id="v-borrar" style="margin-top:6px">Borrar esta compra</button>',
    async () => {
      const fecha = leerFecha($("v-fecha").value);
      if (!fecha) throw new Error("No entiendo la fecha.");
      if (fecha > hoyISO()) throw new Error("Esa fecha todavía no llega.");
      const monto = leerMonto($("v-monto").value);
      if (!monto) throw new Error("Escribe el monto.");
      if (monto < c.abonado) {
        throw new Error("Ya le abonaron " + pesos(c.abonado) + ": no puede valer menos.");
      }
      await cambiar("compras", c.id, { fecha: fecha, detalle: $("v-detalle").value.trim(),
                                       monto: monto });
      mostrarAviso("Compra corregida.");
    }, "Guardar");
  $("v-borrar").onclick = async () => {
    if (c.abonado > 0) {
      $("v-error").textContent = "Esta compra tiene " + pesos(c.abonado) +
        " abonados. Primero déjala pendiente (toca el ☑) y después la puedes borrar.";
      return $("v-error").classList.remove("oculto");
    }
    await cambiar("compras", c.id, { borrado: true });
    $("ventanita").innerHTML = "";
    ocupado = false;
    mostrarAviso("Compra borrada.");
    await refrescar();
  };
  if (pagada) $("v-ok").textContent = "Guardar";
}

function tocarPago(p) {
  ventanita("Deshacer", "Entregó " + pesos(p.monto) + " el " + fechaCorta(p.fecha),
    "<p>Las compras que cubría vuelven a quedar pendientes.</p>",
    async () => {
      await borrarPago(p);
      mostrarAviso("Deshecho.");
    }, "Deshacer", "rojo");
}

async function cambiarCheck(c) {
  if (c.estado === "pagada") {
    return ventanita("Volver a pendiente",
      escapar(c.detalle || "Compra") + " figura con " + pesos(c.abonado) + " pagados.",
      "<p>¿Dejarla otra vez pendiente? Ese pago se quita del libro.</p>",
      async () => { await marcarPendiente(c); mostrarAviso("Vuelve a quedar pendiente."); },
      "Sí, dejarla pendiente");
  }
  try {
    const cobrado = await marcarPagada(c);
    mostrarAviso("Pagada: " + (c.detalle || "compra") + " (" + pesos(cobrado) + ")");
    await refrescar();
  } catch (e) {
    mostrarAviso(e.message || String(e), true);
  }
}

/* ============================================================ anotar */
async function anotarDesdeLaFila() {
  const cl = D.clientes.find((c) => c.id === abierto);
  if (!cl) return;
  const fecha = leerFecha($("a-fecha").value);
  if (!fecha) return mostrarAviso("Revisa la fecha: escribe 7/9, ayer, o déjala vacía.", true);
  if (fecha > hoyISO()) return mostrarAviso("Esa fecha todavía no llega.", true);
  const monto = leerMonto($("a-monto").value);
  if (!monto) return mostrarAviso("Falta el monto.", true);
  const detalle = $("a-detalle").value;
  $("btn-anotar").disabled = true;
  try {
    await anotar(cl.id, detalle, monto, fecha);
    $("a-detalle").value = "";
    $("a-monto").value = "";
    mostrarAviso("Anotado a " + cl.nombre + ": " + (detalle.trim() || "compra") + "  " +
                 pesos(monto));
    await refrescar();
    $("a-detalle").focus();
  } catch (e) {
    mostrarAviso(e.message || String(e), true);
  }
  $("btn-anotar").disabled = false;
}

/* Los puntos de los miles se marcan solos, igual que en el computador. */
function marcarMilesEn(input) {
  if (!input || input.dataset.miles) return;
  if (input.getAttribute("inputmode") !== "numeric") return;
  input.dataset.miles = "1";
  input.addEventListener("input", () => {
    const antes = input.value.slice(0, input.selectionStart).replace(/\D/g, "").length;
    const digitos = input.value.replace(/\D/g, "").replace(/^0+/, "");
    const nuevo = digitos ? Number(digitos).toLocaleString("es-CL") : "";
    if (nuevo === input.value) return;
    input.value = nuevo;
    let i = 0, contados = 0;
    while (i < nuevo.length && contados < antes) { if (/\d/.test(nuevo[i])) contados++; i++; }
    input.setSelectionRange(i, i);
  });
}

/* ========================================================== arranque */
async function refrescar() {
  try {
    await cargar();
    pintar();
  } catch (e) {
    mostrarAviso("No se pudo leer: " + (e.message || e), true);
  }
}

function conectado(si) {
  $("entrar").classList.toggle("oculto", si);
  $("app").classList.toggle("oculto", !si);
}

async function entrar(ev) {
  ev.preventDefault();
  const btn = $("btn-entrar");
  btn.disabled = true;
  btn.textContent = "ENTRANDO...";
  const { error } = await sb.auth.signInWithPassword({
    email: $("correo").value.trim(), password: $("clave").value });
  btn.disabled = false;
  btn.textContent = "ENTRAR";
  if (error) {
    $("error-entrar").textContent = "El correo o la clave no son correctos.";
    return $("error-entrar").classList.remove("oculto");
  }
  $("error-entrar").classList.add("oculto");
  $("clave").value = "";
  conectado(true);
  await refrescar();
}

function conectarBotones() {
  $("forma-entrar").addEventListener("submit", entrar);
  $("salir").addEventListener("click", async (e) => {
    e.preventDefault();
    await sb.auth.signOut();
    conectado(false);
  });
  $("buscar").addEventListener("input", pintarLista);
  $("solo-deben").addEventListener("change", pintarLista);
  $("btn-nuevo").addEventListener("click", nuevoCliente);
  $("btn-volver").addEventListener("click", volverALaLista);
  $("lista").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cliente]");
    if (b) abrirCliente(b.dataset.cliente);
  });
  const conCliente = (f) => () => {
    const cl = D.clientes.find((c) => c.id === abierto);
    if (cl) f(cl);
  };
  $("btn-editar").addEventListener("click", conCliente(editarCliente));
  $("btn-quitar").addEventListener("click", conCliente(quitarCliente));
  $("btn-abonar").addEventListener("click", conCliente(abonar));
  $("btn-pago-todo").addEventListener("click", conCliente(pagoTodo));
  $("btn-whatsapp").addEventListener("click", conCliente(mandarWhatsapp));
  $("btn-anotar").addEventListener("click", anotarDesdeLaFila);
  $("a-monto").addEventListener("keydown", (e) => { if (e.key === "Enter") anotarDesdeLaFila(); });
  $("a-detalle").addEventListener("keydown", (e) => { if (e.key === "Enter") $("a-monto").focus(); });
  marcarMilesEn($("a-monto"));
  $("compras").addEventListener("click", (e) => {
    const chk = e.target.closest("[data-check]");
    if (chk) return cambiarCheck(D.compras.find((c) => c.id === chk.dataset.check));
    const mas = e.target.closest("[data-compra]");
    if (mas) tocarCompra(D.compras.find((c) => c.id === mas.dataset.compra));
  });
  $("pagos").addEventListener("click", (e) => {
    const mas = e.target.closest("[data-pago]");
    if (mas) tocarPago(D.pagos.find((p) => p.id === mas.dataset.pago));
  });
  document.querySelectorAll("[data-filtro]").forEach((b) => {
    b.addEventListener("click", () => { filtro = b.dataset.filtro; pintar(); });
  });
  document.querySelectorAll("[data-pestana]").forEach((b) => {
    b.addEventListener("click", () => {
      pestana = b.dataset.pestana;
      document.querySelectorAll("[data-pestana]").forEach(
        (x) => x.classList.toggle("activa", x === b));
      $("caja-compras").classList.toggle("oculto", pestana !== "compras");
      $("caja-pagos").classList.toggle("oculto", pestana !== "pagos");
    });
  });
  $("logo-cabecera").addEventListener("click", volverALaLista);
}

function mandarWhatsapp(cl) {
  const pend = D.compras.filter((c) => c.cliente_id === cl.id && c.falta > 0)
                        .sort((a, b) => a.fecha.localeCompare(b.fecha));
  const nombre = (cl.nombre || "").split(" ")[0];
  let texto;
  if (!pend.length) {
    texto = "Hola " + nombre + ", te saludamos de Carnicería El Buen Corte. Tu cuenta " +
            "está al día, no tienes nada pendiente. ¡Gracias!";
  } else {
    texto = "Hola " + nombre + ", te saludamos de Carnicería El Buen Corte.\n" +
      "Te dejamos el detalle de tu cuenta pendiente:\n\n" +
      pend.map((c) => "- " + fechaCorta(c.fecha) + "  " + (c.detalle || "Compra") + "  " +
        pesos(c.falta) + (c.abonado ? " (abonado " + pesos(c.abonado) + ")" : "")).join("\n") +
      "\n\nTotal pendiente: " + pesos(cl.deuda) + "\n\n¡Gracias!";
  }
  const numero = telefonoWhatsapp(cl.telefono);
  window.open(numero ? "https://wa.me/" + numero + "?text=" + encodeURIComponent(texto)
                     : "https://wa.me/?text=" + encodeURIComponent(texto), "_blank");
}

(async function arrancar() {
  conectarBotones();
  const { data } = await sb.auth.getSession();
  if (data && data.session) {
    conectado(true);
    await refrescar();
  } else {
    conectado(false);
  }
  setInterval(() => {
    if (!ocupado && document.visibilityState === "visible" && !$("app").classList.contains("oculto")) {
      refrescar();
    }
  }, CADA);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !$("app").classList.contains("oculto")) refrescar();
  });
})();
