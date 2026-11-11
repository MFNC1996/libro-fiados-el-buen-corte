/*
 * Prueba de las cuentas de la pagina del celular.
 *
 *     node web/probar_cuentas.js
 *
 * Son los mismos casos que las pruebas del computador (probar_nucleo.py): si
 * los dos pasan, el celular y el computador muestran exactamente lo mismo.
 */
"use strict";
const C = require("./cuentas.js");

let fallas = [];
function check(nombre, obtenido, esperado) {
  const ok = JSON.stringify(obtenido) === JSON.stringify(esperado);
  console.log((ok ? "  ok   " : "FALLA ") + nombre + "  ->  " + JSON.stringify(obtenido) +
              (ok ? "" : "   (esperado " + JSON.stringify(esperado) + ")"));
  if (!ok) fallas.push(nombre);
}

console.log("--- pesos ---");
check("miles", C.pesos(12500), "$12.500");
check("millones", C.pesos(1234567), "$1.234.567");
check("cero", C.pesos(0), "$0");
check("negativo", C.pesos(-500), "-$500");

console.log("\n--- montos escritos como venga ---");
[["12500", 12500], ["12.500", 12500], ["$12.500", 12500], ["12 500", 12500],
 ["", null], ["abc", null], ["0", null], ["-5", 5]].forEach(([t, e]) =>
  check("'" + t + "'", C.leerMonto(t), e));

console.log("\n--- fechas escritas como venga ---");
const hoy = new Date(2026, 8, 10);                 // 10 de septiembre de 2026
[["", "2026-09-10"], ["hoy", "2026-09-10"], ["ayer", "2026-09-09"], ["7", "2026-09-07"],
 ["28", "2026-08-28"], ["7/9", "2026-09-07"], ["7-9", "2026-09-07"],
 ["28/12", "2025-12-28"], ["7/9/26", "2026-09-07"], ["07/09/2026", "2026-09-07"],
 ["2026-09-07", "2026-09-07"], ["31/2", null], ["hola", null], ["1/2/3/4", null]
].forEach(([t, e]) => check("'" + t + "'", C.leerFecha(t, hoy), e));

console.log("\n--- fechas con dia de la semana y mes en palabras ---");
const martes20 = new Date(2026, 9, 20);            // un martes; el 13 tambien fue martes
[["martes", "2026-10-20"], ["el lunes", "2026-10-19"], ["miércoles", "2026-10-14"],
 ["Martes 13", "2026-10-13"], ["el martes, 13", "2026-10-13"],
 ["13 de octubre", "2026-10-13"], ["martes 13 de octubre", "2026-10-13"],
 ["2 de enero", "2026-01-02"], ["25 de diciembre", "2025-12-25"], ["marte", null]
].forEach(([t, e]) => check("'" + t + "'", C.leerFecha(t, martes20), e));
check("'martes 13' busca el ultimo 13 que cayo martes", C.leerFecha("martes 13", hoy),
      "2026-01-13");
check("fecha corta este anio", C.fechaCorta("2026-09-07", hoy), "07/09");
check("fecha corta otro anio", C.fechaCorta("2025-12-28", hoy), "28/12/25");
check("fecha larga", C.fechaTxt("2026-09-07"), "07/09/2026");
check("hace cuanto", C.haceCuanto("2026-09-01", hoy), "hace 9 días");
check("hoy", C.haceCuanto("2026-09-10", hoy), "hoy");

console.log("\n--- telefono para WhatsApp ---");
check("9 1234 5678", C.telefonoWhatsapp("9 1234 5678"), "56912345678");
check("+56 9 1234 5678", C.telefonoWhatsapp("+56 9 1234 5678"), "56912345678");
check("8 digitos", C.telefonoWhatsapp("12345678"), "56912345678");
check("fijo raro", C.telefonoWhatsapp("452"), null);

console.log("\n--- las cuentas del libro ---");
// Juan: molida 8.990 (pagada), costillar 15.000 (abonado 11.010), pollo 6.500.
const D = {
  clientes: [{ id: "juan", nombre: "Juan Pérez", telefono: "912345678", activo: true },
             { id: "ana", nombre: "Ana Soto", telefono: "", activo: true }],
  compras: [
    { id: "c1", cliente_id: "juan", fecha: "2026-09-01", detalle: "Molida 1 kg", monto: 8990, creado: "1" },
    { id: "c2", cliente_id: "juan", fecha: "2026-09-03", detalle: "Costillar 2 kg", monto: 15000, creado: "2" },
    { id: "c3", cliente_id: "juan", fecha: "2026-09-05", detalle: "Pollo entero", monto: 6500, creado: "3" },
    { id: "c4", cliente_id: "ana", fecha: "2026-09-04", detalle: "Asado", monto: 20000, creado: "4" }],
  pagos: [{ id: "p1", cliente_id: "juan", fecha: "2026-09-08", monto: 20000, nota: "", creado: "5" }],
  aplicaciones: [{ id: "a1", pago_id: "p1", compra_id: "c1", monto: 8990 },
                 { id: "a2", pago_id: "p1", compra_id: "c2", monto: 11010 }]
};
C.recalcular(D);
const compra = (id) => D.compras.find((c) => c.id === id);
const cliente = (id) => D.clientes.find((c) => c.id === id);
check("la molida quedo pagada", compra("c1").estado, C.PAGADA);
check("con su fecha de pago", compra("c1").pagada_el, "2026-09-08");
check("el costillar quedo a medias", compra("c2").estado, C.PARCIAL);
check("con lo abonado", compra("c2").abonado, 11010);
check("y lo que falta", compra("c2").falta, 3990);
check("el pollo sigue pendiente", compra("c3").estado, C.PENDIENTE);
check("Juan debe", cliente("juan").deuda, 3990 + 6500);
check("con 2 compras sin pagar", cliente("juan").pendientes, 2);
check("la mas antigua sin pagar", cliente("juan").mas_antigua, "2026-09-03");
check("su ultimo pago", cliente("juan").ultimo_pago, "2026-09-08");
check("Ana debe lo suyo", cliente("ana").deuda, 20000);
check("el total por cobrar", D.clientes.reduce((s, c) => s + c.deuda, 0), 3990 + 6500 + 20000);
check("los clientes van en orden alfabetico", D.clientes.map((c) => c.nombre),
      ["Ana Soto", "Juan Pérez"]);
check("las compras van de la mas nueva a la mas vieja",
      D.compras.filter((c) => c.cliente_id === "juan").map((c) => c.id), ["c3", "c2", "c1"]);

console.log("\n--- un abono se reparte desde la compra mas antigua ---");
let pend = D.compras.filter((c) => c.cliente_id === "juan" && c.falta > 0);
let partes = C.repartir(pend, 5000);
check("primero termina de pagar el costillar", partes[0].compra.id, "c2");
check("con lo justo que le faltaba", partes[0].monto, 3990);
check("y el resto va al pollo", [partes[1].compra.id, partes[1].monto], ["c3", 1010]);
check("no se reparte de mas", partes.reduce((s, p) => s + p.monto, 0), 5000);
partes = C.repartir(pend, 3990);
check("un abono justo cubre una sola compra", partes.length, 1);
partes = C.repartir(pend, 10490);
check("pagando todo quedan las dos cubiertas", partes.length, 2);
check("y suma la deuda completa", partes.reduce((s, p) => s + p.monto, 0), 10490);

console.log("\n--- el mensaje de WhatsApp ---");
const texto = C.textoWhatsapp(cliente("juan"),
  D.compras.filter((c) => c.cliente_id === "juan"));
check("saluda por el primer nombre", texto.startsWith("Hola Juan,"), true);
check("dice el total", texto.includes("Total pendiente: $10.490"), true);
check("y avisa lo abonado", texto.includes("(abonado $11.010)"), true);
check("al dia", C.textoWhatsapp(cliente("ana"), []).includes("al día"), true);

console.log("\n--- lo que se escapa para que no rompa la pagina ---");
check("nombre con comillas y signos", C.escapar('Juan "El <Flaco>" & Co'),
      "Juan &quot;El &lt;Flaco&gt;&quot; &amp; Co");

(async function clave() {
  console.log("\n--- la clave de administrador ---");
  // El mismo valor que comprueba el computador (probar_nucleo.py): si no
  // coinciden, la clave puesta en un lado no serviria en el otro.
  check("la huella es la misma que en el computador",
        await C.huellaClave("mi-clave-1234", "00112233445566778899aabbccddeeff", 1000),
        "ecc0019d3181b6d8b78a608c6c6636bb4126931b9d10929147850569fcd90548");
  const sal = C.salNueva();
  const h = await C.huellaClave("abcd", sal, 1000);
  check("la clave correcta sirve", await C.claveCorrecta("abcd", h, sal, 1000), true);
  check("una parecida no", await C.claveCorrecta("abcde", h, sal, 1000), false);
  check("sin clave puesta no se pide nada", await C.claveCorrecta("x", "", "", 0), true);
  check("la sal es distinta cada vez", C.salNueva() === sal, false);

  console.log();
  if (fallas.length) {
    console.log("FALLARON " + fallas.length + " PRUEBAS:");
    fallas.forEach((f) => console.log("  - " + f));
    process.exit(1);
  }
  console.log("Todo bien.");
})();

if (false) {
  process.exit(1);
}
