# -*- coding: utf-8 -*-
"""
Libro de Fiados - Carniceria El Buen Corte
Aplicacion de escritorio. No necesita internet ni servidor.

    python app.py
"""

import os
import subprocess
import sys
import traceback
import urllib.parse
import webbrowser
from datetime import date, datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nucleo as N
import instancia
import estado_cuenta

# Paleta del logo del local
ROJO = "#C8202D"          # las letras
ROJO_OSCURO = "#A60D2B"   # las cintas
ROJO_CLARO = "#FBE8E9"
VERDE = "#1F7A3D"         # el anillo
VERDE_OSCURO = "#165E2E"
VERDE_CLARO = "#E3F1E7"
AMBAR = "#8A5A00"
AMBAR_CLARO = "#FBF0DC"
TINTA = "#1B1715"
PAPEL = "#F4F1EC"
BLANCO = "#FFFFFF"
LINEA = "#DED7CF"
SUAVE = "#6C625C"
PISTA = "#A39B94"

VERSION = "1.1.2"
AUTOR = "Macoem"
TITULO = "Libro de Fiados  -  El Buen Corte   |   by %s" % AUTOR

FUENTE = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
MONO = "Consolas" if sys.platform.startswith("win") else "Menlo"

# Cuantos pixeles reales es un pixel "de diseno". En Windows con la pantalla
# al 125 % o 150 % las letras crecen solas; esto hace crecer tambien anchos
# de columnas y altos de filas, para que nada quede cortado.
ESCALA = 1.0


def px(n):
    return int(round(n * ESCALA))


# ================================================================ controles
class Boton(tk.Label):
    """
    Boton plano con los colores del local. Se hace con una etiqueta para que
    se vea igual en cualquier Windows (y en el Mac donde se programa).
    """
    ESTILOS = {
        #          fondo     letra   fondo al pasar  borde
        "rojo":   (ROJO,     BLANCO, ROJO_OSCURO,    ROJO),
        "verde":  (VERDE,    BLANCO, VERDE_OSCURO,   VERDE),
        "oscuro": (TINTA,    BLANCO, "#3B332F",      TINTA),
        "claro":  (BLANCO,   TINTA,  "#EFEAE4",      LINEA),
        "elegido": (TINTA,   BLANCO, TINTA,          TINTA),
        "link":   (None,     ROJO,   None,           None),
    }

    def __init__(self, padre, texto, comando=None, estilo="claro", tam="normal"):
        self.comando = comando
        self.activo = True
        self._fondo_padre = padre.cget("bg")
        fuente = {"grande": (FUENTE, 12, "bold"), "normal": (FUENTE, 10, "bold"),
                  "chico": (FUENTE, 9, "bold")}[tam]
        relleno = {"grande": (24, 10), "normal": (14, 6), "chico": (10, 3)}[tam]
        tk.Label.__init__(self, padre, text=texto, font=fuente, padx=relleno[0],
                          pady=relleno[1], cursor="hand2", takefocus=1,
                          highlightthickness=1)
        self.estilo(estilo)
        self.bind("<Enter>", lambda e: self._pintar(True))
        self.bind("<Leave>", lambda e: self._pintar(False))
        self.bind("<ButtonRelease-1>", self._clic)
        self.bind("<Return>", self._clic)
        self.bind("<space>", self._clic)

    def estilo(self, nombre):
        self._estilo = nombre
        self._pintar(False)

    def _pintar(self, encima):
        fondo, letra, fondo_h, borde = self.ESTILOS[self._estilo]
        if fondo is None:
            fondo = fondo_h = borde = self._fondo_padre
        if not self.activo:
            fondo_h = fondo
            letra = PISTA if self._estilo in ("claro", "link") else "#EDE7E2"
            if self._estilo not in ("claro", "link"):
                fondo = fondo_h = borde = "#BDB5AE"
        self.config(bg=fondo_h if encima else fondo, fg=letra,
                    highlightbackground=borde, highlightcolor=TINTA,
                    activebackground=fondo_h, cursor="hand2" if self.activo else "arrow")

    def _clic(self, evento=None):
        if evento is not None and evento.type == tk.EventType.ButtonRelease:
            # Soltar fuera del boton no cuenta como clic.
            if not (0 <= evento.x < self.winfo_width() and 0 <= evento.y < self.winfo_height()):
                return
        if self.activo and self.comando:
            self.comando()
        return "break"

    def activar(self, si=True):
        self.activo = bool(si)
        self._pintar(False)


class Campo(tk.Entry):
    """Casilla de texto plana, con una pista gris cuando esta vacia."""

    def __init__(self, padre, pista="", ancho=20, tam=11):
        tk.Entry.__init__(self, padre, relief="flat", bd=0, bg=BLANCO, fg=TINTA,
                          insertbackground=TINTA, highlightthickness=1,
                          highlightbackground=LINEA, highlightcolor=ROJO,
                          font=(FUENTE, tam), width=ancho,
                          disabledbackground=PAPEL)
        self.pista = pista
        self._con_pista = False
        self.bind("<FocusIn>", self._entrar, add="+")
        self.bind("<FocusOut>", self._salir, add="+")
        self._salir()

    def _entrar(self, evento=None):
        if self._con_pista:
            self.delete(0, "end")
            self.config(fg=TINTA)
            self._con_pista = False

    def _salir(self, evento=None):
        if not tk.Entry.get(self) and self.pista:
            self.insert(0, self.pista)
            self.config(fg=PISTA)
            self._con_pista = True

    def valor(self):
        return "" if self._con_pista else tk.Entry.get(self).strip()

    def poner(self, texto):
        self._entrar()
        self.delete(0, "end")
        self.insert(0, texto)
        if self.focus_get() is not self:
            self._salir()

    def limpiar(self):
        self.poner("")


# ================================================================== ventana
class App(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        global ESCALA
        try:
            ESCALA = max(1.0, self.winfo_fpixels("1i") / 96.0)
        except tk.TclError:
            ESCALA = 1.0
        if sys.platform == "darwin":
            ESCALA = 1.0            # el Mac ya escala todo solo

        self.datos = N.Datos()
        try:
            self.datos.respaldar()
        except Exception:
            pass

        self.title(TITULO)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # En un notebook comun (1366 x 768) no sobra nada: se usa la pantalla
        # entera, y se achican un poco el panel de clientes y las filas.
        self.pantalla_chica = sw < px(1280) or sh < px(860)
        ancho = min(px(1200), sw - 40)
        alto = min(px(760), sh - px(130))           # que no quede bajo la barra de tareas
        self.geometry("%dx%d+%d+%d" % (ancho, alto, max(0, (sw - ancho) // 2),
                                       max(0, (sh - px(80) - alto) // 3)))
        self.minsize(min(px(900), ancho), min(px(560), alto))
        if self.pantalla_chica and sys.platform.startswith("win"):
            self.state("zoomed")
        self.configure(bg=PAPEL)
        self._icono()

        self.sel = None                 # cliente abierto
        self.orden = "nombre"           # como se ordena la lista de clientes
        self.filtro = "pendientes"      # que compras se ven
        self._pintando = False
        self._aviso_id = None

        self._estilos()
        self._menu()
        self._cabecera()
        self._pie()
        cuerpo = tk.Frame(self, bg=PAPEL)
        cuerpo.pack(fill="both", expand=True)
        self._panel_clientes(cuerpo)
        der = tk.Frame(cuerpo, bg=PAPEL)
        der.pack(side="left", fill="both", expand=True)
        self._vista_inicio(der)
        self._vista_cliente(der)

        self._atajos()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.recargar_todo()
        self.mostrar_inicio()
        self.after(200, lambda: self.e_buscar.focus_set())

    # ------------------------------------------------------------ apariencia
    def _icono(self):
        self.img_ventana = None
        try:
            import imagen_marca
            self.img_ventana = tk.PhotoImage(data=imagen_marca.VENTANA)
            self.iconphoto(True, self.img_ventana)
        except Exception:
            pass

    def _estilos(self):
        e = ttk.Style(self)
        try:
            e.theme_use("clam")
        except tk.TclError:
            pass
        e.configure(".", background=PAPEL, foreground=TINTA, font=(FUENTE, 10),
                    fieldbackground=BLANCO)
        e.configure("TNotebook", background=PAPEL, borderwidth=0, tabmargins=(0, 0, 0, 0))
        e.configure("TNotebook.Tab", padding=(px(18), px(8)), font=(FUENTE, 10, "bold"),
                    background=PAPEL, foreground=SUAVE, borderwidth=0)
        e.map("TNotebook.Tab", background=[("selected", BLANCO)],
              foreground=[("selected", ROJO)])
        e.configure("TFrame", background=PAPEL)
        e.configure("Blanco.TCheckbutton", background=BLANCO, foreground=SUAVE,
                    font=(FUENTE, 9))
        e.map("Blanco.TCheckbutton", background=[("active", BLANCO)])
        e.configure("Treeview", rowheight=px(28 if self.pantalla_chica else 30),
                    fieldbackground=BLANCO,
                    background=BLANCO, font=(FUENTE, 10), borderwidth=0)
        e.configure("Treeview.Heading", font=(FUENTE, 9, "bold"),
                    background=TINTA, foreground=PAPEL, padding=(px(6), px(7)),
                    borderwidth=0, relief="flat")
        e.map("Treeview.Heading", background=[("active", "#3B332F")])
        e.map("Treeview", background=[("selected", ROJO)],
              foreground=[("selected", BLANCO)])
        e.configure("Clientes.Treeview", rowheight=px(30 if self.pantalla_chica else 34),
                    font=(FUENTE, 11))
        e.configure("Vertical.TScrollbar", background=PAPEL, troughcolor=BLANCO,
                    borderwidth=0, arrowcolor=SUAVE)

    def _menu(self):
        barra = tk.Menu(self)
        archivo = tk.Menu(barra, tearoff=0)
        archivo.add_command(label="Nuevo cliente", accelerator="Ctrl+N",
                            command=self.nuevo_cliente)
        archivo.add_command(label="Buscar cliente", accelerator="Ctrl+B",
                            command=self.ir_a_buscar)
        archivo.add_separator()
        archivo.add_command(label="Guardar una copia de seguridad...",
                            command=self.copia_manual)
        archivo.add_command(label="Restaurar desde una copia...",
                            command=self.restaurar_copia)
        archivo.add_command(label="Abrir la carpeta de datos",
                            command=self.abrir_carpeta_datos)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.cerrar)
        barra.add_cascade(label="Archivo", menu=archivo)
        cliente = tk.Menu(barra, tearoff=0)
        cliente.add_command(label="Anotar lo que lleva", command=self._foco_anotar)
        cliente.add_command(label="Abonar / recibir pago...", accelerator="Ctrl+R",
                            command=self.recibir_pago)
        cliente.add_command(label="Pagó todo", command=self.pago_todo)
        cliente.add_separator()
        cliente.add_command(label="Estado de cuenta (imprimir)", accelerator="Ctrl+P",
                            command=self.imprimir_estado)
        cliente.add_command(label="Mandar por WhatsApp", command=self.whatsapp)
        cliente.add_command(label="Editar datos...", command=self.editar_cliente)
        cliente.add_separator()
        cliente.add_command(label="Volver al resumen", accelerator="Esc",
                            command=self.mostrar_inicio)
        barra.add_cascade(label="Cliente", menu=cliente)
        ayuda = tk.Menu(barra, tearoff=0)
        ayuda.add_command(label="Cómo se usa", command=self.como_se_usa)
        ayuda.add_command(label="Acerca de", command=self.acerca_de)
        barra.add_cascade(label="Ayuda", menu=ayuda)
        self.config(menu=barra)

    def _cabecera(self):
        barra = tk.Frame(self, bg=BLANCO)
        barra.pack(fill="x", side="top")

        # El logo del local.
        self.img_marca = None
        try:
            import imagen_marca
            self.img_marca = tk.PhotoImage(data=imagen_marca.CABECERA)
            logo = tk.Label(barra, image=self.img_marca, bg=BLANCO, cursor="hand2")
            logo.pack(side="left", padx=(16, 0), pady=6)
            logo.bind("<Button-1>", lambda e: self.mostrar_inicio())
        except Exception:
            pass                      # sin la imagen la ventana igual sirve

        cont = tk.Frame(barra, bg=BLANCO)
        cont.pack(side="left", padx=12, pady=6)
        tk.Label(cont, text="El Buen Corte", bg=BLANCO, fg=ROJO,
                 font=(FUENTE, 19, "bold italic")).pack(anchor="w")
        tk.Label(cont, text="LONCOCHE  ·  LIBRO DE FIADOS", bg=BLANCO, fg=SUAVE,
                 font=(FUENTE, 8, "bold")).pack(anchor="w", pady=(1, 0))

        derecha = tk.Frame(barra, bg=BLANCO)
        derecha.pack(side="right", padx=22, pady=5)
        tk.Label(derecha, text="POR COBRAR EN TOTAL", bg=BLANCO, fg=SUAVE,
                 font=(FUENTE, 8, "bold")).pack(anchor="e")
        self.lbl_por_cobrar = tk.Label(derecha, text="$0", bg=BLANCO, fg=ROJO_OSCURO,
                                       font=(FUENTE, 20, "bold"), cursor="hand2")
        self.lbl_por_cobrar.pack(anchor="e")
        self.lbl_por_cobrar.bind("<Button-1>", lambda e: self.mostrar_inicio())
        self.lbl_autor = tk.Label(derecha, text="by %s" % AUTOR, bg=BLANCO, fg=ROJO,
                                  font=(FUENTE, 9, "bold italic"))
        self.lbl_autor.pack(anchor="e")
        # Las franjas del logo: verde del anillo y rojo de las cintas.
        tk.Frame(self, bg=VERDE, height=4).pack(fill="x")
        tk.Frame(self, bg=ROJO_OSCURO, height=2).pack(fill="x")

    def _pie(self):
        pie = tk.Frame(self, bg=BLANCO, highlightthickness=0)
        pie.pack(fill="x", side="bottom")
        tk.Frame(pie, bg=LINEA, height=1).pack(fill="x", side="top")
        self.lbl_aviso = tk.Label(pie, text="", bg=BLANCO, fg=VERDE, anchor="w",
                                  font=(FUENTE, 10, "bold"))
        self.lbl_aviso.pack(side="left", padx=16, pady=5)
        self.lbl_respaldo = tk.Label(pie, text="", bg=BLANCO, fg=SUAVE,
                                     font=(FUENTE, 8), cursor="hand2")
        self.lbl_respaldo.pack(side="right", padx=16)
        self.lbl_respaldo.bind("<Button-1>", lambda e: self.abrir_carpeta_datos())

    def _atajos(self):
        for tecla, accion in (("n", self.nuevo_cliente), ("b", self.ir_a_buscar),
                              ("f", self.ir_a_buscar), ("r", self.recibir_pago),
                              ("p", self.imprimir_estado)):
            # En minuscula y en mayuscula, por si esta el Bloq Mayus puesto.
            for t in (tecla, tecla.upper()):
                self.bind_all("<Control-%s>" % t, lambda e, a=accion: (a(), "break")[1])
        self.bind("<Escape>", lambda e: self.mostrar_inicio())

    # ======================================================== lista CLIENTES
    def _panel_clientes(self, padre):
        izq = tk.Frame(padre, bg=BLANCO, width=px(262 if self.pantalla_chica else 300))
        izq.pack(side="left", fill="y")
        izq.pack_propagate(False)
        tk.Frame(padre, bg=LINEA, width=1).pack(side="left", fill="y")

        arriba = tk.Frame(izq, bg=BLANCO)
        arriba.pack(fill="x", padx=(14, 4), pady=(10, 6))
        tk.Label(arriba, text="CLIENTES", bg=BLANCO, fg=SUAVE,
                 font=(FUENTE, 9, "bold")).pack(side="left")
        self.lbl_n_clientes = tk.Label(arriba, text="", bg=BLANCO, fg=SUAVE,
                                       font=(FUENTE, 9))
        self.lbl_n_clientes.pack(side="left", padx=(6, 0))
        Boton(arriba, "Ver resumen", self.mostrar_inicio, "link", "chico").pack(side="right")

        self.e_buscar = Campo(izq, pista="Buscar por nombre o teléfono...", tam=11)
        self.e_buscar.pack(fill="x", padx=14, ipady=px(6))
        self.e_buscar.bind("<KeyRelease>", self._al_buscar)
        self.e_buscar.bind("<Return>", self._buscar_enter)
        self.e_buscar.bind("<Down>", self._buscar_bajar)

        self.btn_nuevo = Boton(izq, "+   Nuevo cliente", self.nuevo_cliente, "rojo")
        self.btn_nuevo.pack(fill="x", padx=14, pady=(10, 10))

        abajo = tk.Frame(izq, bg=BLANCO)
        abajo.pack(side="bottom", fill="x", padx=10, pady=(4, 10))
        self.var_solo_deben = tk.BooleanVar(value=False)
        self.var_archivados = tk.BooleanVar(value=False)
        ttk.Checkbutton(abajo, text="Solo los que deben", variable=self.var_solo_deben,
                        style="Blanco.TCheckbutton",
                        command=self.recargar_clientes).pack(anchor="w")
        ttk.Checkbutton(abajo, text="Mostrar archivados", variable=self.var_archivados,
                        style="Blanco.TCheckbutton",
                        command=self.recargar_clientes).pack(anchor="w")

        marco = tk.Frame(izq, bg=BLANCO)
        marco.pack(fill="both", expand=True, padx=(14, 6))
        self.tv_cli = ttk.Treeview(marco, columns=("nombre", "debe"), show="headings",
                                   selectmode="browse", style="Clientes.Treeview")
        self.tv_cli.heading("nombre", text="Nombre  ▲", anchor="w",
                            command=lambda: self._ordenar("nombre"))
        self.tv_cli.heading("debe", text="Debe", anchor="e",
                            command=lambda: self._ordenar("deuda"))
        # Angostas a proposito: el nombre se estira solo y "Debe" nunca se corta.
        self.tv_cli.column("nombre", width=px(110), stretch=True, anchor="w")
        self.tv_cli.column("debe", width=px(84), stretch=False, anchor="e")
        self.tv_cli.tag_configure("aldia", foreground=SUAVE)
        self.tv_cli.tag_configure("debe", foreground=TINTA)
        self.tv_cli.tag_configure("archivado", foreground=PISTA)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tv_cli.yview)
        self.tv_cli.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_cli.pack(side="left", fill="both", expand=True)
        self.tv_cli.bind("<<TreeviewSelect>>", self._al_elegir_cliente)
        self.tv_cli.bind("<Return>", lambda e: self._foco_anotar())

        self.lbl_sin_resultados = tk.Label(izq, text="", bg=BLANCO, fg=SUAVE,
                                           font=(FUENTE, 9), wraplength=px(260),
                                           justify="left")

    def _ordenar(self, por):
        self.orden = por
        self.tv_cli.heading("nombre", text="Nombre  ▲" if por == "nombre" else "Nombre")
        self.tv_cli.heading("debe", text="Debe  ▼" if por == "deuda" else "Debe")
        self.recargar_clientes()

    def _al_buscar(self, evento=None):
        if evento is not None and evento.keysym in ("Return", "Down", "Up", "Tab"):
            return
        self.recargar_clientes()

    def _buscar_enter(self, evento=None):
        hijos = self.tv_cli.get_children()
        if len(hijos) == 1:
            self.abrir_cliente(int(hijos[0]))
            self._foco_anotar()
        elif not hijos and self.e_buscar.valor():
            self.nuevo_cliente(self.e_buscar.valor())
        return "break"

    def _buscar_bajar(self, evento=None):
        hijos = self.tv_cli.get_children()
        if hijos:
            self.tv_cli.focus_set()
            self.tv_cli.focus(hijos[0])
            self.tv_cli.selection_set(hijos[0])
        return "break"

    def _al_elegir_cliente(self, evento=None):
        if self._pintando:
            return
        sel = self.tv_cli.selection()
        # El aviso de seleccion llega despues, tambien cuando la marcamos
        # nosotros; si ya esta abierto ese cliente no hay nada que hacer.
        if sel and int(sel[0]) != self.sel:
            self.abrir_cliente(int(sel[0]))

    def ir_a_buscar(self):
        self.e_buscar.focus_set()
        self.e_buscar.select_range(0, "end")

    # ====================================================== vista de INICIO
    def _vista_inicio(self, padre):
        v = self.vista_inicio = tk.Frame(padre, bg=PAPEL)
        v.place(relx=0, rely=0, relwidth=1, relheight=1)

        arriba = tk.Frame(v, bg=PAPEL)
        arriba.pack(fill="x", padx=26, pady=(20, 10))
        self.img_inicio = None
        try:
            import imagen_marca
            self.img_inicio = tk.PhotoImage(data=imagen_marca.INICIO)
            if self.winfo_screenheight() < px(900):       # pantalla chica: logo a la mitad
                self.img_inicio = self.img_inicio.subsample(2, 2)
            tk.Label(arriba, image=self.img_inicio, bg=PAPEL).pack(side="left")
        except Exception:
            pass
        textos = tk.Frame(arriba, bg=PAPEL)
        textos.pack(side="left", padx=22, fill="y")
        tk.Label(textos, text="Libro de Fiados", bg=PAPEL, fg=TINTA,
                 font=(FUENTE, 26, "bold")).pack(anchor="w", pady=(18, 0))
        tk.Label(textos, text="Carnicería El Buen Corte  ·  Loncoche", bg=PAPEL,
                 fg=ROJO, font=(FUENTE, 13, "bold italic")).pack(anchor="w")
        self.lbl_hoy = tk.Label(textos, text="", bg=PAPEL, fg=SUAVE, font=(FUENTE, 11))
        self.lbl_hoy.pack(anchor="w", pady=(6, 0))

        tarjetas = tk.Frame(v, bg=PAPEL)
        tarjetas.pack(fill="x", padx=26, pady=(6, 14))
        self.tarjetas = {}
        for i, (clave, rotulo, color) in enumerate([
                ("por_cobrar", "POR COBRAR", ROJO_OSCURO),
                ("deben", "CLIENTES QUE DEBEN", TINTA),
                ("fiado_mes", "FIADO ESTE MES", AMBAR),
                ("cobrado_mes", "COBRADO ESTE MES", VERDE)]):
            t = tk.Frame(tarjetas, bg=BLANCO, highlightthickness=1,
                         highlightbackground=LINEA)
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            tarjetas.columnconfigure(i, weight=1, uniform="t")
            tk.Frame(t, bg=color, height=4).pack(fill="x")
            r = tk.Label(t, text=rotulo, bg=BLANCO, fg=SUAVE, font=(FUENTE, 8, "bold"))
            r.pack(anchor="w", padx=14, pady=(10, 0))
            n = tk.Label(t, text="", bg=BLANCO, fg=color, font=(FUENTE, 20, "bold"))
            n.pack(anchor="w", padx=14, pady=(0, 12))
            self.tarjetas[clave] = (r, n)

        # Los que mas deben
        self.caja_mayores = tk.Frame(v, bg=PAPEL)
        self.caja_mayores.pack(fill="both", expand=True, padx=26, pady=(0, 8))
        enc = tk.Frame(self.caja_mayores, bg=PAPEL)
        enc.pack(fill="x", pady=(0, 6))
        tk.Label(enc, text="LOS QUE DEBEN, DE MAYOR A MENOR", bg=PAPEL, fg=SUAVE,
                 font=(FUENTE, 9, "bold")).pack(side="left")
        tk.Label(enc, text="Doble clic para abrir su hoja", bg=PAPEL, fg=PISTA,
                 font=(FUENTE, 9)).pack(side="right")
        marco = tk.Frame(self.caja_mayores, bg=BLANCO, highlightthickness=1,
                         highlightbackground=LINEA)
        marco.pack(fill="both", expand=True)
        cols = ("nombre", "debe", "pend", "desde", "pago")
        self.tv_mayores = ttk.Treeview(marco, columns=cols, show="headings",
                                       selectmode="browse")
        for c, t, a, al in zip(cols, ("Cliente", "Debe", "Sin pagar", "Debe desde",
                                      "Último pago"),
                               (160, 90, 76, 150, 96), ("w", "e", "center", "w", "w")):
            self.tv_mayores.heading(c, text=t, anchor=al)
            self.tv_mayores.column(c, width=px(a), minwidth=px(50), anchor=al,
                                   stretch=(c in ("nombre", "desde")))
        self.tv_mayores.tag_configure("viejo", foreground=ROJO_OSCURO)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tv_mayores.yview)
        self.tv_mayores.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_mayores.pack(side="left", fill="both", expand=True)
        self.tv_mayores.bind("<Double-1>", self._abrir_mayor)
        self.tv_mayores.bind("<Return>", self._abrir_mayor)

        # Primera vez: todavia no hay clientes.
        self.caja_bienvenida = tk.Frame(v, bg=BLANCO, highlightthickness=1,
                                        highlightbackground=LINEA)
        tk.Label(self.caja_bienvenida, text="Todavía no hay clientes en el libro",
                 bg=BLANCO, fg=TINTA, font=(FUENTE, 15, "bold")).pack(pady=(26, 6))
        tk.Label(self.caja_bienvenida, bg=BLANCO, fg=SUAVE, font=(FUENTE, 11),
                 justify="center",
                 text="Agrega a cada persona a la que le fías. Cada una tiene su propia\n"
                      "hoja, donde anotas lo que lleva y vas marcando lo que paga.").pack()
        Boton(self.caja_bienvenida, "+   Agregar el primer cliente", self.nuevo_cliente,
              "rojo", "grande").pack(pady=(18, 28))

    def _abrir_mayor(self, evento=None):
        sel = self.tv_mayores.selection()
        if sel and sel[0] != "nadie":
            self.abrir_cliente(int(sel[0]))
            self._foco_anotar()

    def mostrar_inicio(self):
        if self.grab_current() is not None:
            return                      # hay un dialogo abierto
        self.sel = None
        self._pintando = True
        self.tv_cli.selection_remove(self.tv_cli.selection())
        self._pintando = False
        self.pintar_inicio()
        self.vista_inicio.tkraise()

    def pintar_inicio(self):
        r = self.datos.resumen()
        self.lbl_hoy.config(text="Hoy es " + N.fecha_larga(date.today().isoformat()))
        self.tarjetas["por_cobrar"][1].config(text=N.pesos(r["por_cobrar"]))
        self.tarjetas["deben"][1].config(
            text="%d de %d" % (r["deben"], r["clientes"]) if r["clientes"] else "0")
        self.tarjetas["fiado_mes"][1].config(text=N.pesos(r["fiado_mes"]))
        self.tarjetas["cobrado_mes"][1].config(text=N.pesos(r["cobrado_mes"]))

        if r["clientes"] == 0:
            self.caja_mayores.pack_forget()
            self.caja_bienvenida.pack(fill="x", padx=26, pady=(4, 8))
            return
        self.caja_bienvenida.pack_forget()
        self.caja_mayores.pack(fill="both", expand=True, padx=26, pady=(0, 8))
        self.tv_mayores.delete(*self.tv_mayores.get_children())
        for c in r["mayores"]:
            dias = N.dias_desde(c["mas_antigua"])
            desde = "%s  (%s)" % (N.fecha_corta(c["mas_antigua"]),
                                  N.hace_cuanto(c["mas_antigua"]))
            pago = N.fecha_corta(c["ultimo_pago"]) if c["ultimo_pago"] else "nunca"
            self.tv_mayores.insert("", "end", iid=str(c["id"]),
                                   tags=("viejo",) if dias > 30 else (),
                                   values=(c["nombre"], N.pesos(c["deuda"]),
                                           c["pendientes"], desde, pago))
        if not r["mayores"]:
            self.tv_mayores.insert("", "end", iid="nadie", values=(
                "Nadie debe nada. Todas las cuentas están al día.", "", "", "", ""))

    # ===================================================== vista de CLIENTE
    def _vista_cliente(self, padre):
        v = self.vista_cliente = tk.Frame(padre, bg=PAPEL)
        v.place(relx=0, rely=0, relwidth=1, relheight=1)

        # -- ficha: quien es y cuanto debe
        ficha = tk.Frame(v, bg=BLANCO, highlightthickness=1, highlightbackground=LINEA)
        ficha.pack(fill="x", padx=18, pady=(12, 10))
        arriba = tk.Frame(ficha, bg=BLANCO)
        arriba.pack(fill="x", padx=18, pady=(10, 0))
        # Lo que debe se arma primero: asi, si falta espacio, nunca se corta.
        der = tk.Frame(arriba, bg=BLANCO)
        der.pack(side="right", anchor="n")
        self.lbl_debe_rot = tk.Label(der, text="DEBE", bg=BLANCO, fg=SUAVE,
                                     font=(FUENTE, 9, "bold"))
        self.lbl_debe_rot.pack(anchor="e")
        self.lbl_deuda = tk.Label(der, text="", bg=BLANCO, fg=ROJO_OSCURO,
                                  font=(FUENTE, 28, "bold"))
        self.lbl_deuda.pack(anchor="e")
        self.lbl_deuda_det = tk.Label(der, text="", bg=BLANCO, fg=SUAVE,
                                      font=(FUENTE, 9))
        self.lbl_deuda_det.pack(anchor="e")
        izq = tk.Frame(arriba, bg=BLANCO)
        izq.pack(side="left", fill="x", expand=True, anchor="n")
        self.lbl_nombre = tk.Label(izq, text="", bg=BLANCO, fg=TINTA, anchor="w",
                                   font=(FUENTE, 20, "bold"))
        self.lbl_nombre.pack(anchor="w", fill="x")
        self.lbl_datos = tk.Label(izq, text="", bg=BLANCO, fg=SUAVE, anchor="w",
                                  font=(FUENTE, 10), justify="left")
        self.lbl_datos.pack(anchor="w", fill="x")
        self.lbl_archivado = tk.Label(izq, text="", bg=AMBAR_CLARO, fg=AMBAR,
                                      font=(FUENTE, 9, "bold"), padx=10, pady=4)

        abajo = tk.Frame(ficha, bg=BLANCO)
        abajo.pack(fill="x", padx=18, pady=(8, 12))
        bots = tk.Frame(abajo, bg=BLANCO)
        bots.pack(side="right")
        self.btn_pagar_todo = Boton(bots, "Pagó todo", self.pago_todo, "claro")
        self.btn_pagar_todo.pack(side="left", padx=(0, 8))
        self.btn_recibir = Boton(bots, "ABONAR", self.recibir_pago, "verde")
        self.btn_recibir.pack(side="left")
        acciones = tk.Frame(abajo, bg=BLANCO)
        acciones.pack(side="left")
        Boton(acciones, "Editar", self.editar_cliente, "claro",
              "chico").pack(side="left", padx=(0, 6))
        Boton(acciones, "Imprimir cuenta", self.imprimir_estado,
              "claro", "chico").pack(side="left", padx=(0, 6))
        self.btn_whatsapp = Boton(acciones, "WhatsApp", self.whatsapp, "claro", "chico")
        self.btn_whatsapp.pack(side="left", padx=(0, 6))
        self.btn_quitar = Boton(acciones, "Quitar", self.quitar_cliente, "claro", "chico")
        self.btn_quitar.pack(side="left")

        # -- anotar: la fila del dia a dia
        an = tk.Frame(v, bg=BLANCO, highlightthickness=1, highlightbackground=LINEA)
        an.pack(fill="x", padx=18, pady=(0, 10))
        tk.Frame(an, bg=ROJO, width=5).pack(side="left", fill="y")
        f = tk.Frame(an, bg=BLANCO)
        f.pack(side="left", fill="x", expand=True, padx=14, pady=(8, 10))
        titulo = tk.Frame(f, bg=BLANCO)
        titulo.grid(row=0, column=0, columnspan=4, sticky="we", pady=(0, 2))
        tk.Label(titulo, text="ANOTAR LO QUE LLEVA", bg=BLANCO, fg=ROJO,
                 font=(FUENTE, 9, "bold")).pack(side="left")
        self.lbl_ayuda_anotar = tk.Label(
            titulo, text="Enter pasa al siguiente y anota   ·   Monto: 12500, 12.500 o 12 mil",
            bg=BLANCO, fg=PISTA, font=(FUENTE, 8))
        self.lbl_ayuda_anotar.pack(side="right")
        cf = tk.Frame(f, bg=BLANCO)
        cf.grid(row=1, column=0, sticky="w")
        tk.Label(cf, text="Fecha", bg=BLANCO, fg=SUAVE, font=(FUENTE, 9)).pack(side="left")
        self.lbl_fecha_ok = tk.Label(cf, text="", bg=BLANCO, fg=SUAVE, font=(FUENTE, 8))
        self.lbl_fecha_ok.pack(side="left", padx=(6, 0))
        for col, texto in ((1, "Qué lleva"), (2, "Monto")):
            tk.Label(f, text=texto, bg=BLANCO, fg=SUAVE, font=(FUENTE, 9)).grid(
                row=1, column=col, sticky="w", padx=(0, 10))
        self.e_fecha = Campo(f, pista="hoy", ancho=11, tam=12)
        self.e_fecha.grid(row=2, column=0, sticky="we", padx=(0, 10), ipady=px(5))
        self.e_detalle = Campo(f, pista="Ej: 1 kg de molida, 2 chuletas", ancho=26, tam=12)
        self.e_detalle.grid(row=2, column=1, sticky="we", padx=(0, 10), ipady=px(5))
        self.e_monto = Campo(f, pista="$", ancho=10, tam=12)
        self.e_monto.grid(row=2, column=2, sticky="we", padx=(0, 10), ipady=px(5))
        self.btn_anotar = Boton(f, "ANOTAR", self.anotar, "rojo")
        self.btn_anotar.grid(row=2, column=3, sticky="ns")
        f.columnconfigure(1, weight=1)
        self.e_fecha.bind("<KeyRelease>", self._revisar_fecha)
        self.e_fecha.bind("<FocusOut>", self._revisar_fecha, add="+")
        self.e_fecha.bind("<Return>", lambda e: (self.e_detalle.focus_set(), "break")[1])
        self.e_detalle.bind("<Return>", lambda e: (self.e_monto.focus_set(), "break")[1])
        self.e_monto.bind("<Return>", lambda e: (self.anotar(), "break")[1])

        # -- compras y pagos
        self.nb = ttk.Notebook(v)
        self.nb.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        self._tab_compras()
        self._tab_pagos()

    def _tab_compras(self):
        p = tk.Frame(self.nb, bg=BLANCO)
        self.nb.add(p, text="  Compras  ")
        self.tab_compras = p

        barra = tk.Frame(p, bg=BLANCO)
        barra.pack(fill="x", padx=12, pady=(10, 8))
        tk.Label(barra, text="Ver:", bg=BLANCO, fg=SUAVE, font=(FUENTE, 9)).pack(
            side="left", padx=(0, 6))
        self.btn_filtros = {}
        for clave, texto in (("pendientes", "Por pagar"), ("todas", "Todas"),
                             ("pagadas", "Pagadas")):
            b = Boton(barra, texto, lambda c=clave: self.cambiar_filtro(c), "claro", "chico")
            b.pack(side="left", padx=(0, 4))
            self.btn_filtros[clave] = b
        tk.Label(barra, text="Clic en  ☐ Pagar  y queda pagada",
                 bg=BLANCO, fg=PISTA, font=(FUENTE, 9)).pack(side="right")

        marco = tk.Frame(p, bg=BLANCO)
        marco.pack(fill="both", expand=True, padx=12)
        cols = ("chk", "fecha", "detalle", "monto", "falta", "estado")
        self.tv_compras = ttk.Treeview(marco, columns=cols, show="headings",
                                       selectmode="extended")
        for c, t, a, al in zip(cols,
                               ("Pagado", "Fecha", "Qué llevó", "Valor", "Falta", "Estado"),
                               (100, 92, 190, 88, 88, 136),
                               ("w", "center", "w", "e", "e", "w")):
            self.tv_compras.heading(c, text=t, anchor=al)
            self.tv_compras.column(c, width=px(a), minwidth=px(60), anchor=al,
                                   stretch=(c == "detalle"))
        self.tv_compras.tag_configure("pagada", foreground="#4E7A5E", background="#F4F9F5")
        self.tv_compras.tag_configure("parcial", foreground=AMBAR, background=AMBAR_CLARO)
        self.tv_compras.tag_configure("vacio", foreground=PISTA)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tv_compras.yview)
        self.tv_compras.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_compras.pack(side="left", fill="both", expand=True)
        self.tv_compras.bind("<Button-1>", self._clic_en_compra)
        self.tv_compras.bind("<Double-1>", self._doble_clic_en_compra)
        self.tv_compras.bind("<space>", lambda e: (self.cambiar_pagada(), "break")[1])
        self.tv_compras.bind("<Delete>", lambda e: self.borrar_compra())
        self.tv_compras.bind("<<TreeviewSelect>>", lambda e: self._botones_compra())

        abajo = tk.Frame(p, bg=BLANCO)
        abajo.pack(fill="x", padx=12, pady=10)
        self.btn_pagada = Boton(abajo, "✓  Marcar pagada", self.marcar_pagadas,
                                "verde", "chico")
        self.btn_pagada.pack(side="left", padx=(0, 6))
        self.btn_pendiente = Boton(abajo, "Volver a pendiente", self.marcar_pendientes,
                                   "claro", "chico")
        self.btn_pendiente.pack(side="left", padx=(0, 6))
        self.btn_editar_compra = Boton(abajo, "Corregir", self.editar_compra,
                                       "claro", "chico")
        self.btn_editar_compra.pack(side="left", padx=(0, 6))
        self.btn_borrar_compra = Boton(abajo, "Borrar", self.borrar_compra,
                                       "claro", "chico")
        self.btn_borrar_compra.pack(side="left")
        self.lbl_total_vista = tk.Label(abajo, text="", bg=BLANCO, fg=SUAVE,
                                        font=(FUENTE, 10))
        self.lbl_total_vista.pack(side="right")

    def _tab_pagos(self):
        p = tk.Frame(self.nb, bg=BLANCO)
        self.nb.add(p, text="  Pagos y abonos  ")
        self.tab_pagos = p
        tk.Label(p, text="Cada vez que el cliente entregó plata (un abono o el pago "
                         "completo), y a qué compras se descontó.", bg=BLANCO, fg=SUAVE,
                 font=(FUENTE, 9)).pack(
            anchor="w", padx=12, pady=(10, 8))
        marco = tk.Frame(p, bg=BLANCO)
        marco.pack(fill="both", expand=True, padx=12)
        cols = ("fecha", "monto", "nota", "aplicado")
        self.tv_pagos = ttk.Treeview(marco, columns=cols, show="headings",
                                     selectmode="browse")
        for c, t, a, al in zip(cols, ("Fecha", "Entregó", "Nota", "Se descontó de"),
                               (92, 90, 140, 260), ("center", "e", "w", "w")):
            self.tv_pagos.heading(c, text=t, anchor=al)
            self.tv_pagos.column(c, width=px(a), minwidth=px(60), anchor=al,
                                 stretch=(c == "aplicado"))
        self.tv_pagos.tag_configure("vacio", foreground=PISTA)
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tv_pagos.yview)
        self.tv_pagos.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_pagos.pack(side="left", fill="both", expand=True)
        self.tv_pagos.bind("<<TreeviewSelect>>", lambda e: self._botones_pago())
        self.tv_pagos.bind("<Delete>", lambda e: self.deshacer_pago())
        abajo = tk.Frame(p, bg=BLANCO)
        abajo.pack(fill="x", padx=12, pady=10)
        self.btn_deshacer = Boton(abajo, "Deshacer", self.deshacer_pago, "claro", "chico")
        self.btn_deshacer.pack(side="left")
        tk.Label(abajo, text="Si se anotó por error, deshacerlo deja otra vez "
                             "pendiente lo que cubría.",
                 bg=BLANCO, fg=PISTA, font=(FUENTE, 9)).pack(side="left", padx=10)

    # ---------------------------------------------------------- abrir/pintar
    def abrir_cliente(self, cid):
        cambio = cid != self.sel
        self.sel = cid
        if cambio:
            self.filtro = "pendientes"
            self.e_detalle.limpiar()
            self.e_monto.limpiar()
            self.e_fecha.limpiar()
            self._revisar_fecha()
            self.nb.select(self.tab_compras)
        self._marcar_en_lista()
        self.pintar_cliente()
        self.vista_cliente.tkraise()

    def _foco_anotar(self):
        if self.sel is not None and self.grab_current() is None:
            self.e_detalle.focus_set()

    def _marcar_en_lista(self):
        self._pintando = True
        try:
            iid = str(self.sel) if self.sel is not None else None
            if iid and self.tv_cli.exists(iid):
                self.tv_cli.selection_set(iid)
                self.tv_cli.see(iid)
            else:
                self.tv_cli.selection_remove(self.tv_cli.selection())
        finally:
            self._pintando = False

    def pintar_cliente(self):
        cl = self.datos.cliente(self.sel)
        if not cl:
            self.sel = None
            return self.mostrar_inicio()
        self._cl = cl
        self.lbl_nombre.config(text=cl["nombre"])
        datos = []
        if cl["telefono"]:
            datos.append("Tel. " + cl["telefono"])
        if cl["nota"]:
            datos.append(cl["nota"])
        if not datos:
            datos.append("Sin teléfono ni nota. Puedes agregarlos con «Editar».")
        self.lbl_datos.config(text="   ·   ".join(datos))
        if cl["activo"]:
            self.lbl_archivado.pack_forget()
            self.btn_quitar.config(text="Quitar")
            self.btn_quitar.comando = self.quitar_cliente
        else:
            self.lbl_archivado.config(text="ARCHIVADO: no aparece en la lista de clientes")
            self.lbl_archivado.pack(anchor="w", pady=(6, 0))
            self.btn_quitar.config(text="Volver a la lista")
            self.btn_quitar.comando = self.reactivar_cliente

        if cl["deuda"] > 0:
            self.lbl_debe_rot.config(text="DEBE")
            self.lbl_deuda.config(text=N.pesos(cl["deuda"]), fg=ROJO_OSCURO)
            n = cl["pendientes"]
            self.lbl_deuda_det.config(
                text="%d compra%s sin pagar  ·  desde %s" % (
                    n, "" if n == 1 else "s", N.hace_cuanto(cl["mas_antigua"])))
        else:
            self.lbl_debe_rot.config(text="CUENTA")
            self.lbl_deuda.config(text="AL DÍA", fg=VERDE)
            self.lbl_deuda_det.config(
                text="Último pago: %s" % N.fecha_txt(cl["ultimo_pago"])
                if cl["ultimo_pago"] else "No debe nada")
        self.btn_recibir.activar(cl["deuda"] > 0)
        self.btn_pagar_todo.activar(cl["deuda"] > 0)

        # compras
        todas = self.datos.compras_de(self.sel)
        cuenta = {"todas": len(todas),
                  "pendientes": len([c for c in todas if c["estado"] != N.PAGADA]),
                  "pagadas": len([c for c in todas if c["estado"] == N.PAGADA])}
        for clave, b in self.btn_filtros.items():
            base = {"pendientes": "Por pagar", "todas": "Todas", "pagadas": "Pagadas"}[clave]
            b.config(text="%s  %d" % (base, cuenta[clave]))
            b.estilo("elegido" if clave == self.filtro else "claro")
        if self.filtro == "pendientes":
            lista = [c for c in todas if c["estado"] != N.PAGADA]
        elif self.filtro == "pagadas":
            lista = [c for c in todas if c["estado"] == N.PAGADA]
        else:
            lista = todas
        elegidas = set(self.tv_compras.selection())
        self.tv_compras.delete(*self.tv_compras.get_children())
        for c in lista:
            if c["estado"] == N.PAGADA:
                chk, estado = "  ☑  Pagada", "Pagada el %s" % N.fecha_txt(c["pagada_el"])[:5]
            elif c["estado"] == N.PARCIAL:
                chk, estado = "  ☐  Pagar", "Abonó %s" % N.pesos(c["abonado"])
            else:
                chk, estado = "  ☐  Pagar", "Pendiente"
            self.tv_compras.insert(
                "", "end", iid=str(c["id"]), tags=(c["estado"],),
                values=(chk, N.fecha_txt(c["fecha"]), c["detalle"] or "—",
                        N.pesos(c["monto"]), N.pesos(c["falta"]) if c["falta"] else "",
                        estado))
        if not lista:
            texto = {"pendientes": "No hay nada por pagar.",
                     "pagadas": "Todavía no hay compras pagadas.",
                     "todas": "Todavía no se le ha anotado nada. Usa la fila de "
                              "arriba para anotar lo que lleva."}[self.filtro]
            self.tv_compras.insert("", "end", iid="vacio", tags=("vacio",),
                                   values=("", "", texto, "", "", ""))
        quedan = [i for i in elegidas if self.tv_compras.exists(i) and i != "vacio"]
        if quedan:
            self.tv_compras.selection_set(quedan)
        falta = sum(c["falta"] for c in lista)
        self.lbl_total_vista.config(
            text="%d compra%s  ·  falta pagar %s" % (len(lista), "" if len(lista) == 1
                                                    else "s", N.pesos(falta))
            if lista else "")
        self.nb.tab(self.tab_compras, text="  Compras (%d por pagar)  " % cuenta["pendientes"]
                    if cuenta["pendientes"] else "  Compras  ")

        # pagos
        pagos = self.datos.pagos_de(self.sel)
        self.tv_pagos.delete(*self.tv_pagos.get_children())
        for pg in pagos:
            partes = []
            for a in pg["aplicaciones"]:
                det = a["detalle"] or "compra"
                if a["monto"] < a["total"]:
                    partes.append("%s %s (abono %s)" % (N.fecha_txt(a["fecha"])[:5], det,
                                                         N.pesos(a["monto"])))
                else:
                    partes.append("%s %s" % (N.fecha_txt(a["fecha"])[:5], det))
            self.tv_pagos.insert("", "end", iid=str(pg["id"]),
                                 values=(N.fecha_txt(pg["fecha"]), N.pesos(pg["monto"]),
                                         pg["nota"], ",  ".join(partes)))
        if not pagos:
            self.tv_pagos.insert("", "end", iid="vacio", tags=("vacio",),
                                 values=("", "", "Todavía no hay pagos ni abonos.", ""))
        self.nb.tab(self.tab_pagos, text="  Pagos y abonos (%d)  " % len(pagos))
        self._botones_compra()
        self._botones_pago()

    def cambiar_filtro(self, filtro):
        self.filtro = filtro
        self.tv_compras.selection_remove(self.tv_compras.selection())
        self.pintar_cliente()

    def _compras_elegidas(self):
        return [int(i) for i in self.tv_compras.selection() if i != "vacio"]

    def _botones_compra(self):
        ids = self._compras_elegidas()
        estados = [self.tv_compras.item(str(i), "tags")[0] for i in ids]
        self.btn_pagada.activar(any(e != N.PAGADA for e in estados))
        self.btn_pendiente.activar(any(e != N.PENDIENTE for e in estados))
        self.btn_editar_compra.activar(len(ids) == 1)
        self.btn_borrar_compra.activar(len(ids) >= 1)

    def _botones_pago(self):
        sel = [i for i in self.tv_pagos.selection() if i != "vacio"]
        self.btn_deshacer.activar(bool(sel))

    # ------------------------------------------------------------- anotar
    def _revisar_fecha(self, evento=None):
        texto = self.e_fecha.valor()
        iso = N.leer_fecha(texto)
        if iso is None:
            self.lbl_fecha_ok.config(text="No entiendo esa fecha", fg=ROJO)
        elif not texto:
            self.lbl_fecha_ok.config(text="vacío = hoy", fg=PISTA)
        else:
            d = datetime.strptime(iso, "%Y-%m-%d")
            self.lbl_fecha_ok.config(
                text="%s %s" % (N.DIAS[d.weekday()], N.fecha_corta(iso)), fg=VERDE)
        return iso

    def anotar(self):
        if self.sel is None:
            return
        if not self._cl["activo"]:
            return messagebox.showinfo(
                "Cliente archivado", "%s está archivado.\n\nVuelve a ponerlo en la lista "
                "(botón «Volver a la lista») para anotarle compras." % self._cl["nombre"])
        fecha = self._revisar_fecha()
        if fecha is None:
            self.e_fecha.focus_set()
            return self.avisar("Revisa la fecha: escribe por ejemplo 7/9, ayer o déjala "
                               "vacía para hoy.", ROJO)
        if fecha > date.today().isoformat():
            if not messagebox.askyesno("Fecha futura", "La fecha %s todavía no llega.\n\n"
                                       "¿Anotarla igual?" % N.fecha_txt(fecha)):
                return
        monto = N.leer_monto(self.e_monto.valor())
        if not monto:
            self.e_monto.focus_set()
            return self.avisar("Falta el monto. Escríbelo así: 12500, 12.500 o 12 mil.",
                               ROJO)
        detalle = self.e_detalle.valor()
        try:
            cid = self.datos.anotar(self.sel, detalle, monto, fecha)
        except ValueError as e:
            return self.avisar(str(e), ROJO)
        self.e_detalle.limpiar()
        self.e_monto.limpiar()
        if self.filtro == "pagadas":
            self.filtro = "pendientes"
        self.nb.select(self.tab_compras)
        self.recargar_todo()
        if self.tv_compras.exists(str(cid)):
            self.tv_compras.selection_set(str(cid))
            self.tv_compras.see(str(cid))
        self.e_detalle.focus_set()
        self.avisar("Anotado a %s: %s  %s" % (self._cl["nombre"], detalle or "compra",
                                               N.pesos(monto)))

    # ----------------------------------------------------- pagado/pendiente
    def _clic_en_compra(self, evento):
        """Un clic en la columna Pagado cambia el check de esa compra."""
        if self.tv_compras.identify_region(evento.x, evento.y) != "cell":
            return
        if self.tv_compras.identify_column(evento.x) != "#1":
            return
        fila = self.tv_compras.identify_row(evento.y)
        if fila and fila != "vacio":
            self.tv_compras.selection_set(fila)
            self.cambiar_pagada(int(fila))
            return "break"

    def _doble_clic_en_compra(self, evento):
        # El doble clic sobre el cuadrado de pagado no abre el corrector.
        if self.tv_compras.identify_column(evento.x) == "#1":
            return "break"
        fila = self.tv_compras.identify_row(evento.y)
        if fila and fila != "vacio":
            self.editar_compra(int(fila))

    def cambiar_pagada(self, compra_id=None):
        if compra_id is None:
            ids = self._compras_elegidas()
            if len(ids) != 1:
                return
            compra_id = ids[0]
        c = self.datos._compra(compra_id)
        if c["estado"] == N.PAGADA:
            self._volver_pendiente([c])
        else:
            cobrado = self.datos.marcar_pagada(compra_id)
            self.recargar_todo()
            self.avisar("Pagada: %s  (%s recibidos)" % (c["detalle"] or "compra",
                                                        N.pesos(cobrado)))

    def marcar_pagadas(self):
        ids = self._compras_elegidas()
        total, n = 0, 0
        for i in ids:
            cobrado = self.datos.marcar_pagada(i)
            if cobrado:
                total += cobrado
                n += 1
        self.recargar_todo()
        if n:
            self.avisar("%d compra%s marcada%s pagada%s  (%s recibidos)" % (
                n, "" if n == 1 else "s", "" if n == 1 else "s", "" if n == 1 else "s",
                N.pesos(total)))

    def marcar_pendientes(self):
        compras = [self.datos._compra(i) for i in self._compras_elegidas()]
        compras = [c for c in compras if c["abonado"] > 0]
        if compras:
            self._volver_pendiente(compras)

    def _volver_pendiente(self, compras):
        total = sum(c["abonado"] for c in compras)
        if len(compras) == 1:
            c = compras[0]
            pregunta = ("«%s» del %s figura con %s pagados.\n\n¿Dejarla otra vez "
                        "pendiente? Ese pago se quita del libro."
                        % (c["detalle"] or "Compra", N.fecha_txt(c["fecha"]),
                           N.pesos(c["abonado"])))
        else:
            pregunta = ("Estas %d compras tienen %s pagados en total.\n\n¿Dejarlas otra "
                        "vez pendientes? Esos pagos se quitan del libro."
                        % (len(compras), N.pesos(total)))
        if not messagebox.askyesno("Volver a pendiente", pregunta, icon="warning"):
            return
        for c in compras:
            self.datos.marcar_pendiente(c["id"])
        self.recargar_todo()
        self.avisar("Vuelve a quedar pendiente: %s" % N.pesos(total), AMBAR)

    def editar_compra(self, compra_id=None):
        if compra_id is None:
            ids = self._compras_elegidas()
            if len(ids) != 1:
                return
            compra_id = ids[0]
        if DialogoCompra(self, self.datos._compra(compra_id)).mostrar():
            self.recargar_todo()
            self.avisar("Compra corregida.")

    def borrar_compra(self):
        compras = [self.datos._compra(i) for i in self._compras_elegidas()]
        if not compras:
            return
        con_abono = [c for c in compras if c["abonado"] > 0]
        if con_abono:
            return messagebox.showinfo(
                "No se puede borrar",
                "%s tiene pagos anotados.\n\nPrimero déjala pendiente (botón «Volver a "
                "pendiente») y después la puedes borrar." % (
                    "«%s»" % (con_abono[0]["detalle"] or "Esa compra")
                    if len(con_abono) == 1 else "Hay compras elegidas que"))
        if len(compras) == 1:
            c = compras[0]
            pregunta = "¿Borrar «%s» del %s por %s?\n\nEsto no se puede deshacer." % (
                c["detalle"] or "compra", N.fecha_txt(c["fecha"]), N.pesos(c["monto"]))
        else:
            pregunta = "¿Borrar estas %d compras (%s en total)?\n\nEsto no se puede " \
                       "deshacer." % (len(compras), N.pesos(sum(c["monto"] for c in compras)))
        if not messagebox.askyesno("Borrar", pregunta, icon="warning"):
            return
        for c in compras:
            self.datos.borrar_compra(c["id"])
        self.recargar_todo()
        self.avisar("Borrado.", AMBAR)

    # ---------------------------------------------------------------- pagos
    def recibir_pago(self):
        if self.sel is None or self._cl["deuda"] <= 0 or self.grab_current() is not None:
            return
        r = DialogoPago(self, self._cl, self.datos).mostrar()
        if r:
            self.nb.select(self.tab_compras)
            self.recargar_todo()
            self.avisar("Abono de %s: %s. Ahora debe %s." % (
                self._cl["nombre"], N.pesos(r["monto"]), N.pesos(self._cl["deuda"])))

    def pago_todo(self):
        if self.sel is None or self._cl["deuda"] <= 0 or self.grab_current() is not None:
            return
        cl = self._cl
        if not messagebox.askyesno(
                "Pagó todo", "¿%s pagó todo lo que debe?\n\nSe anota un pago de %s con "
                "fecha de hoy y todas sus compras quedan pagadas."
                % (cl["nombre"], N.pesos(cl["deuda"]))):
            return
        self.datos.recibir_pago(self.sel, cl["deuda"])
        self.recargar_todo()
        self.avisar("%s quedó al día. Pagó %s." % (cl["nombre"], N.pesos(cl["deuda"])))

    def deshacer_pago(self):
        sel = [i for i in self.tv_pagos.selection() if i != "vacio"]
        if not sel:
            return
        valores = self.tv_pagos.item(sel[0], "values")
        if not messagebox.askyesno(
                "Deshacer", "¿Deshacer lo que entregó el %s (%s)?\n\nLas compras que "
                "cubría vuelven a quedar pendientes." % (valores[0], valores[1]),
                icon="warning"):
            return
        self.datos.borrar_pago(int(sel[0]))
        self.recargar_todo()
        self.avisar("Deshecho. Ahora debe %s." % N.pesos(self._cl["deuda"]), AMBAR)

    # ------------------------------------------------------------- clientes
    def nuevo_cliente(self, nombre=""):
        if self.grab_current() is not None:
            return
        cid = DialogoCliente(self, self.datos, nombre=nombre).mostrar()
        if cid:
            self.e_buscar.limpiar()
            self.recargar_clientes()
            self.abrir_cliente(cid)
            self._foco_anotar()
            self.avisar("Cliente agregado. Ya puedes anotarle lo que lleva.")

    def editar_cliente(self):
        if self.sel is None or self.grab_current() is not None:
            return
        if DialogoCliente(self, self.datos, cliente=self._cl).mostrar():
            self.recargar_todo()
            self.avisar("Datos guardados.")

    def quitar_cliente(self):
        cl = self._cl
        if cl["deuda"] > 0:
            return messagebox.showinfo(
                "Todavía debe", "%s todavía debe %s.\n\nNo se puede quitar a alguien que "
                "tiene deuda." % (cl["nombre"], N.pesos(cl["deuda"])))
        if not messagebox.askyesno(
                "Quitar de la lista", "¿Quitar a %s de la lista de clientes?\n\nSi tiene "
                "compras o pagos anotados, queda archivado con toda su historia (se ve "
                "marcando «Mostrar archivados»)." % cl["nombre"]):
            return
        try:
            r = self.datos.quitar_cliente(self.sel)
        except ValueError as e:
            return messagebox.showwarning("No se pudo", str(e))
        self.mostrar_inicio()
        self.recargar_todo()
        self.avisar("%s %s." % (cl["nombre"], "quedó archivado" if r == "archivado"
                                else "se borró"), AMBAR)

    def reactivar_cliente(self):
        try:
            self.datos.reactivar_cliente(self.sel)
        except ValueError as e:
            return messagebox.showwarning("No se pudo", str(e))
        self.recargar_todo()
        self.avisar("%s vuelve a estar en la lista." % self._cl["nombre"])

    # --------------------------------------------------- papel y WhatsApp
    def imprimir_estado(self):
        if self.sel is None:
            return
        try:
            ruta = estado_cuenta.guardar(self.datos, self.sel)
        except Exception as e:
            return messagebox.showerror("No se pudo armar", str(e))
        self._abrir(ruta)
        self.avisar("Estado de cuenta abierto en el navegador. Ahí aprieta «Imprimir».")

    def whatsapp(self):
        if self.sel is None:
            return
        texto = N.texto_whatsapp(self._cl, self.datos.compras_de(self.sel))
        self.clipboard_clear()
        self.clipboard_append(texto)
        numero = N.telefono_whatsapp(self._cl["telefono"])
        if numero:
            webbrowser.open("https://wa.me/%s?text=%s" % (numero, urllib.parse.quote(texto)))
            self.avisar("Se abrió WhatsApp con el mensaje. También quedó copiado.")
        else:
            messagebox.showinfo(
                "Mensaje copiado",
                "El mensaje con la cuenta quedó copiado.\n\nAbre el chat de %s en "
                "WhatsApp y pégalo con Ctrl+V.\n\nSi le agregas el teléfono en «Editar "
                "datos», la próxima vez se abre WhatsApp directo." % self._cl["nombre"])

    # ============================================================ recargas
    def recargar_todo(self):
        r = self.datos.resumen()
        self.lbl_por_cobrar.config(text=N.pesos(r["por_cobrar"]))
        self.recargar_clientes()
        if self.sel is not None:
            self.pintar_cliente()
        else:
            self.pintar_inicio()
        fecha, n = self.datos.ultimo_respaldo()
        self.lbl_respaldo.config(
            text="Copia de seguridad automática: %s  (%d guardadas)" % (
                "hoy" if fecha == date.today().isoformat() else N.fecha_txt(fecha), n)
            if fecha else "Todavía sin copias de seguridad")

    def recargar_clientes(self):
        lista = self.datos.clientes(archivados=self.var_archivados.get(),
                                    buscar=self.e_buscar.valor())
        if self.var_solo_deben.get():
            lista = [c for c in lista if c["deuda"] > 0]
        if self.orden == "deuda":
            lista.sort(key=lambda c: (-c["deuda"], N._sin_tildes(c["nombre"])))
        else:
            lista.sort(key=lambda c: N._sin_tildes(c["nombre"]))
        self._pintando = True
        try:
            self.tv_cli.delete(*self.tv_cli.get_children())
            for c in lista:
                if not c["activo"]:
                    tag, debe = "archivado", "archivado"
                elif c["deuda"] > 0:
                    tag, debe = "debe", N.pesos(c["deuda"])
                else:
                    tag, debe = "aldia", "al día"
                self.tv_cli.insert("", "end", iid=str(c["id"]), tags=(tag,),
                                   values=(c["nombre"], debe))
        finally:
            self._pintando = False
        self._marcar_en_lista()
        total = len(self.datos.clientes(archivados=self.var_archivados.get()))
        self.lbl_n_clientes.config(
            text="%d de %d" % (len(lista), total) if len(lista) != total else str(total))
        if not lista and self.e_buscar.valor():
            self.lbl_sin_resultados.config(
                text="Nadie se llama así. Aprieta Enter para agregar a «%s» como "
                     "cliente nuevo." % self.e_buscar.valor())
            self.lbl_sin_resultados.place(x=14, rely=0.35, relwidth=0.9)
        else:
            self.lbl_sin_resultados.place_forget()

    # -------------------------------------------------------------- avisos
    def avisar(self, texto, color=VERDE):
        self.lbl_aviso.config(text=texto, fg=color)
        if self._aviso_id:
            self.after_cancel(self._aviso_id)
        self._aviso_id = self.after(10000, lambda: self.lbl_aviso.config(text=""))

    def report_callback_exception(self, tipo, valor, tb):
        """Un error inesperado no cierra la ventana: se avisa y se anota."""
        texto = "".join(traceback.format_exception(tipo, valor, tb))
        try:
            with open(os.path.join(N.carpeta_datos(), "errores.log"), "a",
                      encoding="utf-8") as f:
                f.write("\n=== %s  v%s\n%s" % (datetime.now().isoformat(" ", "seconds"),
                                              VERSION, texto))
        except Exception:
            pass
        messagebox.showerror("Algo salió mal",
                             "Ocurrió un error inesperado:\n\n%s\n\nSe anotó en "
                             "errores.log, en la carpeta de datos." % valor)

    # ------------------------------------------------------------ archivos
    @staticmethod
    def _abrir(ruta):
        try:
            if sys.platform.startswith("win"):
                os.startfile(ruta)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", ruta])
            else:
                subprocess.Popen(["xdg-open", ruta])
        except Exception:
            pass

    def abrir_carpeta_datos(self):
        self._abrir(N.carpeta_datos())

    def copia_manual(self):
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Guardar copia de seguridad", defaultextension=".sqlite3",
            initialfile="fiados-%s.sqlite3" % date.today().isoformat(),
            filetypes=[("Copia del Libro de Fiados", "*.sqlite3")])
        if not ruta:
            return
        try:
            self.datos.respaldar(ruta)
        except Exception as e:
            return messagebox.showerror("No se pudo copiar", str(e))
        messagebox.showinfo("Copia guardada", "Se guardó una copia en:\n%s\n\n"
                            "Guárdala en un pendrive o mándatela por correo." % ruta)

    def restaurar_copia(self):
        ruta = filedialog.askopenfilename(
            parent=self, title="Elegir la copia a restaurar",
            initialdir=self.datos.carpeta_respaldos(),
            filetypes=[("Copia del Libro de Fiados", "*.sqlite3"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            n = N.Datos.revisar_copia(ruta)
        except ValueError as e:
            return messagebox.showerror("No sirve", str(e))
        if not messagebox.askyesno(
                "Restaurar copia",
                "La copia tiene %d clientes, %d compras y %d pagos.\n\n¿Reemplazar TODO lo "
                "que hay ahora por lo de la copia?\n\nLo actual no se pierde: queda "
                "guardado en la carpeta de respaldos." % (n["clientes"], n["compras"],
                                                         n["pagos"]), icon="warning"):
            return
        try:
            antes = self.datos.restaurar(ruta)
        except Exception as e:
            return messagebox.showerror("No se pudo restaurar", str(e))
        self.sel = None
        self.recargar_todo()
        self.mostrar_inicio()
        messagebox.showinfo("Listo", "Se restauró la copia.\n\nLo que había antes quedó "
                            "guardado en:\n%s" % antes)

    def como_se_usa(self):
        messagebox.showinfo(
            "Cómo se usa",
            "1. CLIENTES\n"
            "Agrega a cada persona con «+ Nuevo cliente». Cada una tiene su hoja.\n\n"
            "2. ANOTAR\n"
            "Abre la hoja del cliente, escribe qué lleva y el monto, y aprieta Enter "
            "(o ANOTAR). La fecha, si la dejas vacía, es hoy.\n\n"
            "3. PAGOS Y ABONOS\n"
            "• Clic en «☐ Pagar» de una compra: queda pagada.\n"
            "• ABONAR: el cliente entrega una parte (por ejemplo $30.000 de $45.000). "
            "Solo escribes cuánto abona; queda con la fecha de hoy y se descuenta "
            "desde la compra más antigua.\n"
            "• Pagó todo: deja la cuenta al día de una vez.\n\n"
            "4. CORREGIR\n"
            "«Volver a pendiente» quita un pago de una compra. En «Pagos y abonos» "
            "puedes deshacer un abono o pago completo.\n\n"
            "5. COBRAR\n"
            "«Imprimir cuenta» abre el estado de cuenta listo para imprimir. "
            "«WhatsApp» arma el mensaje con el detalle.\n\n"
            "Se hace una copia de seguridad sola cada día (menú Archivo).")

    def acerca_de(self):
        messagebox.showinfo(
            "Acerca de",
            "Libro de Fiados  %s\n%s  ·  %s\n\nDesarrollado por %s.\n\n"
            "Los datos están en:\n%s" % (VERSION, N.NEGOCIO, N.CIUDAD, AUTOR,
                                         self.datos.ruta))

    def cerrar(self):
        # Al cerrar se renueva la copia del dia, con todo lo anotado hoy.
        try:
            self.datos.respaldar(reemplazar=True)
        except Exception:
            pass
        try:
            self.datos.cerrar()
        except Exception:
            pass
        self.destroy()


# ================================================================= dialogos
class Dialogo(tk.Toplevel):
    """Ventanita modal con campos, un boton para aceptar y otro para cancelar."""

    def __init__(self, padre, titulo, texto_ok="Guardar", estilo_ok="rojo"):
        tk.Toplevel.__init__(self, padre)
        self.withdraw()
        self.title(titulo)
        self.configure(bg=BLANCO)
        self.resizable(False, False)
        self.transient(padre)
        self.padre = padre
        self.resultado = None
        self.primero = None
        self.cuerpo = tk.Frame(self, bg=BLANCO)
        self.cuerpo.pack(fill="both", expand=True, padx=24, pady=(18, 4))
        self.lbl_error = tk.Label(self, text="", bg=BLANCO, fg=ROJO, justify="left",
                                  font=(FUENTE, 10, "bold"), wraplength=px(420), anchor="w")
        self.lbl_error.pack(fill="x", padx=24, pady=(0, 8))
        pie = tk.Frame(self, bg=PAPEL)
        pie.pack(fill="x", side="bottom")
        self.btn_ok = Boton(pie, texto_ok, self._ok, estilo_ok)
        self.btn_ok.pack(side="right", padx=(6, 18), pady=12)
        Boton(pie, "Cancelar", self.destroy, "claro").pack(side="right", pady=12)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def campo(self, fila, rotulo, pista="", valor="", ancho=34, ayuda=""):
        tk.Label(self.cuerpo, text=rotulo, bg=BLANCO, fg=SUAVE,
                 font=(FUENTE, 9, "bold")).grid(row=fila * 2, column=0, sticky="w",
                                                pady=(8, 2))
        c = Campo(self.cuerpo, pista=pista, ancho=ancho, tam=12)
        c.grid(row=fila * 2 + 1, column=0, sticky="we", ipady=px(6))
        if valor:
            c.poner(valor)
        if ayuda:
            tk.Label(self.cuerpo, text=ayuda, bg=BLANCO, fg=PISTA,
                     font=(FUENTE, 8)).grid(row=fila * 2 + 1, column=1, sticky="w", padx=8)
        if self.primero is None:
            self.primero = c
        return c

    def mostrar(self):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = self.padre.winfo_rootx() + (self.padre.winfo_width() - w) // 2
        y = self.padre.winfo_rooty() + max(0, (self.padre.winfo_height() - h) // 3)
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        if self.primero is not None:
            self.primero.focus_set()
            self.primero.select_range(0, "end")
        self.wait_window()
        return self.resultado

    def _ok(self):
        try:
            r = self.aceptar()
        except ValueError as e:
            self.lbl_error.config(text=str(e))
            return
        if r:
            self.resultado = r
            self.destroy()

    def aceptar(self):
        return True


class DialogoCliente(Dialogo):
    def __init__(self, padre, datos, cliente=None, nombre=""):
        Dialogo.__init__(self, padre, "Editar cliente" if cliente else "Nuevo cliente",
                         "Guardar" if cliente else "Agregar cliente")
        self.datos, self.cl = datos, cliente
        tk.Label(self.cuerpo, text="Editar datos del cliente" if cliente else
                 "Nuevo cliente", bg=BLANCO, fg=TINTA,
                 font=(FUENTE, 15, "bold")).grid(row=0, column=0, sticky="w")
        self.cuerpo.grid_rowconfigure(0, minsize=px(30))
        c = cliente or {}
        self.e_nombre = self.campo(1, "NOMBRE", "Ej: Juan Pérez", c.get("nombre") or nombre)
        self.e_tel = self.campo(2, "TELÉFONO  (opcional)", "Ej: 9 1234 5678",
                                c.get("telefono", ""))
        self.e_nota = self.campo(3, "NOTA  (opcional)", "Ej: vecino del frente, paga los "
                                 "viernes", c.get("nota", ""))

    def aceptar(self):
        if self.cl:
            self.datos.editar_cliente(self.cl["id"], self.e_nombre.valor(),
                                      self.e_tel.valor(), self.e_nota.valor())
            return self.cl["id"]
        return self.datos.agregar_cliente(self.e_nombre.valor(), self.e_tel.valor(),
                                          self.e_nota.valor())


class DialogoCompra(Dialogo):
    def __init__(self, padre, compra):
        Dialogo.__init__(self, padre, "Corregir compra")
        self.datos, self.c = padre.datos, compra
        tk.Label(self.cuerpo, text="Corregir compra", bg=BLANCO, fg=TINTA,
                 font=(FUENTE, 15, "bold")).grid(row=0, column=0, sticky="w")
        self.e_fecha = self.campo(1, "FECHA", "hoy", N.fecha_txt(compra["fecha"]), 14,
                                  ayuda="Ej: 7/9, ayer")
        self.e_det = self.campo(2, "QUÉ LLEVÓ", "", compra["detalle"])
        self.e_monto = self.campo(3, "MONTO", "$", N.pesos(compra["monto"]), 14)
        self.primero = self.e_det
        if compra["abonado"]:
            tk.Label(self.cuerpo, bg=BLANCO, fg=AMBAR, font=(FUENTE, 9),
                     text="Ya tiene %s abonados." % N.pesos(compra["abonado"])).grid(
                row=8, column=0, sticky="w", pady=(10, 0))

    def aceptar(self):
        fecha = N.leer_fecha(self.e_fecha.valor())
        if fecha is None:
            raise ValueError("No entiendo la fecha. Escríbela así: 7/9/2026.")
        self.datos.editar_compra(self.c["id"], fecha, self.e_det.valor(),
                                 self.e_monto.valor())
        return True


class DialogoPago(Dialogo):
    """Abono: solo se pregunta cuanto entrega. La fecha es la del dia."""

    def __init__(self, padre, cliente, datos):
        Dialogo.__init__(self, padre, "Abonar", "Registrar abono", "verde")
        self.datos, self.cl = datos, cliente
        tk.Label(self.cuerpo, text="Abono de %s" % cliente["nombre"], bg=BLANCO, fg=TINTA,
                 font=(FUENTE, 15, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(self.cuerpo, text="Debe %s" % N.pesos(cliente["deuda"]), bg=BLANCO,
                 fg=ROJO_OSCURO, font=(FUENTE, 12, "bold")).grid(row=1, column=0,
                                                                 sticky="w")
        self.e_monto = self.campo(1, "¿CUÁNTO ABONA?", "$", "", 18)
        self.lbl_prev = tk.Label(self.cuerpo, text="", bg=BLANCO, fg=VERDE,
                                 font=(FUENTE, 11, "bold"), justify="left",
                                 wraplength=px(360))
        self.lbl_prev.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.e_monto.bind("<KeyRelease>", lambda e: self._previa())
        self._previa()

    def _previa(self):
        """Antes de aceptar, cuanto va a quedar debiendo."""
        monto = N.leer_monto(self.e_monto.valor())
        deuda = self.cl["deuda"]
        if not monto:
            self.lbl_prev.config(text="", fg=VERDE)
        elif monto > deuda:
            self.lbl_prev.config(text="Es más de lo que debe. El vuelto es %s."
                                      % N.pesos(monto - deuda), fg=ROJO)
        elif monto == deuda:
            self.lbl_prev.config(text="Queda al día.", fg=VERDE)
        else:
            self.lbl_prev.config(text="Queda debiendo %s." % N.pesos(deuda - monto),
                                 fg=VERDE)

    def aceptar(self):
        fecha = date.today().isoformat()
        r = self.datos.recibir_pago(self.cl["id"], self.e_monto.valor(), fecha)
        r["fecha"] = fecha
        return r


# ==================================================================== inicio
def preparar_windows():
    """Letras nitidas con la pantalla escalada, y el icono propio en la barra."""
    if not sys.platform.startswith("win"):
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Macoem.LibroDeFiados")
    except Exception:
        pass


def main():
    # Antes de abrir nada: si ya hay una ventana, se trae esa y no se abre otra.
    if not instancia.tomar(N.carpeta_datos()):
        if not instancia.traer_al_frente(TITULO):
            raiz = tk.Tk()
            raiz.withdraw()
            messagebox.showinfo("Libro de Fiados",
                                "El programa ya está abierto.\n\n"
                                "Búscalo en la barra de tareas, abajo.")
            raiz.destroy()
        return 0
    preparar_windows()
    try:
        App().mainloop()
    except Exception:
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error", traceback.format_exc())
        except Exception:
            traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
