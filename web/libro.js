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
let firma = "";                           // para no redibujar si nada cambio
let instalador = null;                    // el aviso del celular para instalarla

/* Las cuentas viven en cuentas.js, probadas aparte con node. */
const C = window.Cuentas;
const pesos = C.pesos, leerMonto = C.leerMonto, leerFecha = C.leerFecha;
const fechaCorta = C.fechaCorta, fechaTxt = C.fechaTxt, haceCuanto = C.haceCuanto;
const sinTildes = C.sinTildes, escapar = C.escapar, hoyISO = C.hoyISO;
const telefonoWhatsapp = C.telefonoWhatsapp;

/* ======================================================== los datos */
/*
 * El servidor entrega como maximo 1000 filas por consulta, asi que se pide por
 * tandas hasta que no venga nada mas. Con un libro de anios, igual se trae todo.
 */
async function traerTodo(tabla) {
  const TANDA = 1000;
  let desde = 0, filas = [];
  for (;;) {
    const { data, error } = await sb.from(tabla).select("*")
      .eq("local_id", LOCAL_ID).eq("borrado", false)
      .order("creado", { ascending: true }).range(desde, desde + TANDA - 1);
    if (error) throw error;
    filas = filas.concat(data);
    if (data.length < TANDA) return filas;
    desde += TANDA;
    if (desde > 100000) return filas;              // tope de seguridad
  }
}

async function cargar() {
  const [clientes, compras, pagos, aplicaciones] = await Promise.all(
    ["clientes", "compras", "pagos", "aplicaciones"].map(traerTodo));
  D = { clientes, compras, pagos, aplicaciones };
  recalcular();
}

const recalcular = () => C.recalcular(D);

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
  const pend = D.compras.filter((c) => c.cliente_id === cliente.id && c.falta > 0);
  const deuda = pend.reduce((s, c) => s + c.falta, 0);
  if (deuda <= 0) throw new Error("No hay nada pendiente que pagar.");
  if (monto > deuda) throw new Error("Está pagando " + pesos(monto) + ", pero debe " +
    pesos(deuda) + ". El libro no guarda saldo a favor.");
  const partes = C.repartir(pend, monto);
  const pago = nuevoId();
  let { error } = await sb.from("pagos").insert({
    id: pago, local_id: LOCAL_ID, cliente_id: cliente.id, fecha: fecha, monto: monto, nota: "" });
  if (error) throw error;
  for (const p of partes) {
    await insertar("aplicaciones", { pago_id: pago, compra_id: p.compra.id, monto: p.monto });
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
  // Solo los que estan en la lista, igual que en el computador.
  const total = D.clientes.filter((c) => c.activo !== false)
                          .reduce((s, c) => s + c.deuda, 0);
  $("por-cobrar").textContent = pesos(total);
  pintarResumen();
  pintarLista();
  if (abierto) {
    const cl = D.clientes.find((c) => c.id === abierto);
    if (!cl) { volverALaLista(); } else { pintarHoja(cl); }
  }
}

/* Lo mismo que muestran las tarjetas del resumen en el computador. */
function pintarResumen() {
  const mes = hoyISO().slice(0, 7);
  const delMes = (filas) => filas.filter((f) => String(f.fecha).slice(0, 7) === mes)
                                 .reduce((s, f) => s + f.monto, 0);
  const enLista = D.clientes.filter((c) => c.activo !== false);
  const deben = enLista.filter((c) => c.deuda > 0).length;
  const activos = enLista.length;
  $("resumen").innerHTML =
    "Deben <b>" + deben + "</b> de " + activos + " clientes" +
    "  ·  fiado este mes <b>" + pesos(delMes(D.compras)) + "</b>" +
    "  ·  cobrado <b>" + pesos(delMes(D.pagos)) + "</b>";
}

function pintarLista() {
  const busca = sinTildes($("buscar").value).trim();
  const soloDeben = $("solo-deben").checked;
  const verArchivados = $("ver-archivados").checked;
  let lista = verArchivados ? D.clientes.slice() : D.clientes.filter((c) => c.activo !== false);
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
    const archivado = c.activo === false ? " (archivado)" : "";
    return '<button class="cliente" data-cliente="' + c.id + '">' +
      '<span class="quien"><b>' + escapar(c.nombre) + archivado + "</b><small>" +
      escapar(det) + "</small></span>" +
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
  $("p-compras").textContent = cuenta.pendientes
    ? "Compras (" + cuenta.pendientes + " por pagar)" : "Compras";
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
      await refrescar(false);
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
    await refrescar(false);
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
    await refrescar(false);
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
    await refrescar(false);
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
async function refrescar(forzar) {
  try {
    await cargar();
  } catch (e) {
    return mostrarAviso(navigator.onLine === false
      ? "Sin internet: lo que se ve puede estar atrasado."
      : "No se pudo leer: " + (e.message || e), true);
  }
  // Solo se vuelve a dibujar si de verdad cambio algo, para que la pantalla no
  // parpadee ni se mueva de lugar mientras el dueno esta mirando.
  const ahora = JSON.stringify([D.clientes.length, D.compras.length, D.pagos.length,
    D.aplicaciones.length,
    D.clientes.map((c) => c.id + c.nombre + c.deuda + c.activo).join(),
    D.compras.map((c) => c.id + c.monto + c.falta + c.detalle + c.fecha).join(),
    D.pagos.map((p) => p.id + p.monto + p.fecha).join()]);
  if (forzar !== false && ahora === firma) return;
  firma = ahora;
  pintar();
}

/* -------------------------------------------- acceso directo en el celular */
function yaEstaInstalada() {
  return window.matchMedia("(display-mode: standalone)").matches ||
         window.navigator.standalone === true;
}

function esiPhone() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
         (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function prepararInstalacion() {
  const caja = $("caja-instalar");
  const mostrar = () => caja.classList.remove("oculto");
  if (yaEstaInstalada()) return;                 // ya la tiene: no se molesta
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    instalador = e;                              // Android: se instala de una
    mostrar();
  });
  if (esiPhone()) mostrar();                     // iPhone: se explica como
  $("btn-instalar").addEventListener("click", async () => {
    if (instalador) {
      instalador.prompt();
      const r = await instalador.userChoice;
      instalador = null;
      if (r && r.outcome === "accepted") {
        caja.classList.add("oculto");
        mostrarAviso("Listo: el libro quedó en la pantalla de inicio.");
      }
      return;
    }
    comoInstalarla();
  });
  window.addEventListener("appinstalled", () => {
    caja.classList.add("oculto");
    mostrarAviso("Listo: el libro quedó en la pantalla de inicio.");
  });
}

function comoInstalarla() {
  const iphone = esiPhone();
  ventanita("Tenerlo en la pantalla de inicio",
    "Queda con el logo del local, igual que cualquier otra aplicación.",
    '<ol class="pasos">' + (iphone
      ? "<li>Abajo, toca el botón <b>Compartir</b> (el cuadrado con la flecha hacia arriba).</li>" +
        "<li>Desliza y elige <b>Agregar a pantalla de inicio</b>.</li>" +
        "<li>Toca <b>Agregar</b>, arriba a la derecha.</li>"
      : "<li>Arriba a la derecha, toca los <b>tres puntitos</b> del navegador.</li>" +
        "<li>Elige <b>Agregar a la pantalla principal</b> (o <b>Instalar aplicación</b>).</li>" +
        "<li>Confirma con <b>Agregar</b>.</li>") + "</ol>",
    async () => {}, "Entendido", "verde");
  const cancelar = document.getElementById("v-cancelar");
  if (cancelar) cancelar.classList.add("oculto");
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
  await refrescar(false);
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
  $("ver-archivados").addEventListener("change", pintarLista);
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
  const texto = C.textoWhatsapp(cl, D.compras.filter((c) => c.cliente_id === cl.id));
  const numero = telefonoWhatsapp(cl.telefono);
  window.open(numero ? "https://wa.me/" + numero + "?text=" + encodeURIComponent(texto)
                     : "https://wa.me/?text=" + encodeURIComponent(texto), "_blank");
}

(async function arrancar() {
  conectarBotones();
  prepararInstalacion();
  const { data } = await sb.auth.getSession();
  if (data && data.session) {
    conectado(true);
    await refrescar(false);
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
