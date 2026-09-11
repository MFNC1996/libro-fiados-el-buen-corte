# Libro de Fiados · El Buen Corte

Libro de fiados para Windows de **Carnicería El Buen Corte**, Loncoche.
Una hoja por cliente: lo que se anotó, cuánto vale, lo que ya pagó y lo que queda pendiente.

**Para instalarlo:** en *Releases* descarga `LibroDeFiados-Setup.exe` y dale doble clic.
El manual de uso está en [LEEME.txt](LEEME.txt).

## Qué hace

- Lista de clientes con lo que debe cada uno, buscador y orden por deuda.
- Anotar es una sola fila: fecha (vacía = hoy), qué lleva y monto. Enter y listo.
- Check de pagado en cada compra, y **Abonar** para lo que el cliente entrega a cuenta
  (ej.: debe $45.000, abona $30.000 y queda debiendo $15.000). Solo se escribe el monto: queda con la fecha del día,
  y se descuenta desde la compra más antigua.
- Al anotar, la fecha se escribe como se dice: `hoy`, `ayer`, `martes`, `13`, `martes 13`, `13 de octubre`, `13/10`.
- Se puede deshacer todo: volver una compra a pendiente o deshacer un abono completo.
- Estado de cuenta listo para imprimir o guardar como PDF, y mensaje para WhatsApp.
- Copia de seguridad automática cada día; copia manual y restauración desde el menú Archivo.

## Cómo está hecho

Python con tkinter (viene con Python, sin dependencias) y SQLite.

| Archivo | Qué es |
|---|---|
| `app.py` | La ventana |
| `nucleo.py` | Datos y cuentas; no depende de la ventana |
| `estado_cuenta.py` | El estado de cuenta imprimible (HTML) |
| `instancia.py` | Una sola ventana abierta a la vez |
| `imagen_marca.py` | El logo en texto; lo genera `empaquetado/hacer_icono.py` |
| `probar_nucleo.py`, `probar_ventana.py` | Pruebas |
| `empaquetado/` | Receta del `.exe` (PyInstaller), instalador (Inno Setup), íconos y capturas |

Para probarlo en el computador:

```bash
python probar_nucleo.py && python probar_ventana.py && python app.py
```

Cada push a `main` hace que GitHub Actions, en Windows: corra las pruebas, arme el `.exe`,
lo abra y le saque capturas, arme el instalador, lo instale, lo abra, lo desinstale, y publique
la versión en *Releases*.

Los datos del local no están en el repositorio: viven en
`%LOCALAPPDATA%\LibroDeFiados\fiados.sqlite3` del computador donde se usa.

Desarrollado por Macoem.
