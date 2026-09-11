# -*- coding: utf-8 -*-
"""
Llena la base con clientes y compras de ejemplo para fotografiar la aplicacion
durante la compilacion. No forma parte del programa que se instala.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from datetime import date, timedelta

import nucleo as N

HOY = date.today()


def f(dias_atras):
    """Fecha relativa: asi el ejemplo sirve cualquier dia que se compile."""
    return (HOY - timedelta(days=dias_atras)).isoformat()


d = N.Datos()
if d.total_clientes():
    print("ya tenia clientes"); sys.exit(0)

juan = d.agregar_cliente("Juan Pérez", "9 8765 4321", "Vecino del frente, paga los viernes")
ana = d.agregar_cliente("Ana Soto", "9 1234 5678")
carlos = d.agregar_cliente("Carlos Mena", "", "Trabaja en el aserradero")
rosa = d.agregar_cliente("Rosa Huenchul", "9 5555 1212")
pedro = d.agregar_cliente("Pedro Catrileo")
d.agregar_cliente("Marta Riquelme", "9 4444 3333")

for dias, det, monto in [(12, "Molida especial 1 kg", 8990), (9, "Costillar 2 kg", 15800),
                         (6, "Pollo entero", 6500), (4, "Longaniza 1/2 kg", 3490),
                         (1, "Posta negra 1 kg", 10990)]:
    d.anotar(juan, det, monto, f(dias))
d.recibir_pago(juan, 12000, f(5), "efectivo")          # salda la molida, abona el costillar

for dias, det, monto in [(20, "Asado de tira 1,5 kg", 14900), (15, "Chuletas de cerdo", 7200),
                         (3, "Filete 1/2 kg", 9900)]:
    d.anotar(ana, det, monto, f(dias))
d.recibir_pago(ana, 22100, f(10), "transferencia")

for dias, det, monto in [(40, "Carne para cazuela", 5600), (33, "Pulpa de cerdo 2 kg", 11800),
                         (2, "Molida corriente 1 kg", 6490)]:
    d.anotar(carlos, det, monto, f(dias))

d.anotar(rosa, "Pechuga de pollo 1 kg", 5990, f(2))
d.anotar(rosa, "Huevos (bandeja)", 5500, f(2))
d.marcar_pagada(d.compras_de(rosa)[1]["id"], f(1))

d.anotar(pedro, "Asado para el domingo", 32500, f(8))
d.recibir_pago(pedro, 32500, f(1))

print("sembrados %d clientes; por cobrar %s" % (d.total_clientes(),
                                                N.pesos(d.resumen()["por_cobrar"])))
