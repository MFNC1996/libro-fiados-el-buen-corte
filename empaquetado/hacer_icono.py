# -*- coding: utf-8 -*-
"""
Arma los iconos y la marca de la ventana a partir del logo real del local.

    python empaquetado/hacer_icono.py

Necesita Pillow, pero solo aqui: el programa que se instala no lo usa.
Lee empaquetado/logo-original.jpeg (el logo tal como llego, con esquinas
negras) y deja:

    empaquetado/logo.png     el logo recortado en circulo, fondo transparente
    empaquetado/icono.ico    icono del .exe y del instalador
    imagen_marca.py          el logo en texto, para que la ventana lo muestre
                             sin depender de un archivo suelto al lado del .exe
"""
import base64
import io
import os

from PIL import Image, ImageChops, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(AQUI, ".."))

# El circulo del logo dentro de la foto original (medido a mano).
CENTRO_X, CENTRO_Y, RADIO = 517, 512.5, 499
# Las cuchillas cruzadas y los animales: lo unico que se distingue en 16 px.
CENTRO_DEL_LOGO = (232, 262, 800, 662)
VERDE = (32, 118, 59, 255)


def circulo(tam, radio=None, sobre=4):
    """Mascara circular suavizada de tam x tam."""
    radio = radio if radio is not None else tam / 2.0
    m = Image.new("L", (tam * sobre, tam * sobre), 0)
    c = tam * sobre / 2.0
    r = radio * sobre
    ImageDraw.Draw(m).ellipse((c - r, c - r, c + r, c + r), fill=255)
    return m.resize((tam, tam), Image.LANCZOS)


def logo_recortado():
    im = Image.open(os.path.join(AQUI, "logo-original.jpeg")).convert("RGB")
    lado = int(RADIO * 2) + 2
    x0, y0 = int(CENTRO_X - RADIO) - 1, int(CENTRO_Y - RADIO) - 1
    cuadro = im.crop((x0, y0, x0 + lado, y0 + lado)).convert("RGBA")
    cuadro.putalpha(circulo(lado, RADIO))
    return cuadro


def icono_chico(tam):
    """Para 16-32 px el logo entero es una mancha: anillo verde y cuchillas."""
    grande = 256
    base = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    ImageDraw.Draw(base).ellipse((0, 0, grande - 1, grande - 1), fill=VERDE)
    blanco = Image.new("RGBA", (grande, grande), (255, 255, 255, 255))
    borde = int(grande * 0.085)
    mascara = Image.new("L", (grande, grande), 0)
    ImageDraw.Draw(mascara).ellipse((borde, borde, grande - borde, grande - borde),
                                    fill=255)
    base.paste(blanco, (0, 0), mascara)

    original = Image.open(os.path.join(AQUI, "logo-original.jpeg")).convert("RGBA")
    centro = original.crop(CENTRO_DEL_LOGO)
    ancho = int(grande * 0.78)
    alto = int(centro.height * ancho / centro.width)
    centro = centro.resize((ancho, alto), Image.LANCZOS)
    recorte = Image.new("L", (grande, grande), 0)
    ImageDraw.Draw(recorte).ellipse((borde, borde, grande - borde, grande - borde),
                                    fill=255)
    capa = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    capa.paste(centro, ((grande - ancho) // 2, (grande - alto) // 2 + 6))
    base.paste(capa, (0, 0), ImageChops.multiply(capa.split()[3], recorte))
    return base.resize((tam, tam), Image.LANCZOS)


def en_png(imagen):
    b = io.BytesIO()
    imagen.save(b, "PNG", optimize=True)
    return b.getvalue()


def main():
    logo = logo_recortado()
    logo.save(os.path.join(AQUI, "logo.png"))
    print("logo.png: %dx%d" % logo.size)

    # Icono de Windows: el logo entero donde se alcanza a leer, y la version
    # simple (anillo verde con las cuchillas) en los tamanos chicos.
    tamanos = [256, 128, 64, 48, 32, 24, 16]
    capas = []
    for n in tamanos:
        capas.append(logo.resize((n, n), Image.LANCZOS) if n >= 48 else icono_chico(n))
    ruta_ico = os.path.join(AQUI, "icono.ico")
    capas[0].save(ruta_ico, format="ICO", sizes=[(n, n) for n in tamanos],
                  append_images=capas[1:])
    print("icono.ico: %d bytes" % os.path.getsize(ruta_ico))
    icono_chico(256).save(os.path.join(AQUI, "icono-chico.png"))

    # La marca para la ventana: cabecera, pantalla de inicio e icono de la
    # barra de titulo. Tambien la del estado de cuenta que se imprime.
    piezas = {
        "CABECERA": en_png(logo.resize((66, 66), Image.LANCZOS)),
        "INICIO": en_png(logo.resize((190, 190), Image.LANCZOS)),
        "VENTANA": en_png(icono_chico(32)),
        "IMPRESO": en_png(logo.resize((220, 220), Image.LANCZOS)),
    }
    destino = os.path.join(RAIZ, "imagen_marca.py")
    with open(destino, "w") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write('"""El logo del local en PNG (base64). Generado por '
                'empaquetado/hacer_icono.py; no editar a mano."""\n')
        for nombre, datos in piezas.items():
            f.write('\n%s = """%s"""\n' % (nombre, base64.b64encode(datos).decode()))
    print("imagen_marca.py: %d KB" % (os.path.getsize(destino) // 1024))


if __name__ == "__main__":
    main()
