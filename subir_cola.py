"""Sube a TikTok los videos de cola.txt, en orden, hasta llenar el cupo del día.

    python subir_cola.py

TikTok deja como máximo 5 subidas pendientes (sin publicar) por cuenta en
cualquier ventana de 24 horas; el cupo se libera 24 h después de cada subida,
o antes si el video se publica desde la notificación. Borrar la notificación
no lo libera. Por eso este script corre una vez al día (tarea programada
"TikTok - subir cola") y se detiene al primer rechazo por cupo: lo que no
alcanzó a subir queda en la cola para el día siguiente.

cola.txt: una ruta de .mp4 por línea (relativa a esta carpeta o absoluta).
Lo que se sube se borra de la cola y queda anotado en subidas.log.
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
COLA = os.path.join(AQUI, "cola.txt")
MAX_POR_DIA = 5


def main():
    # La tarea programada redirige la salida a cola.log; sin esto, Windows usa
    # cp1252 y cualquier carácter raro de la respuesta de TikTok revienta el print.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not os.path.exists(COLA):
        return
    with open(COLA, encoding="utf-8") as f:
        cola = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    subidos = 0
    while cola and subidos < MAX_POR_DIA:
        ruta = cola[0] if os.path.isabs(cola[0]) else os.path.join(AQUI, cola[0])
        if not os.path.exists(ruta):
            print(f"No existe {ruta}; lo saco de la cola.")
            cola.pop(0)
            continue
        r = subprocess.run([sys.executable, os.path.join(AQUI, "tiktok.py"), "subir", ruta],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        salida = r.stdout + r.stderr
        if "publish_id" not in salida:
            print(f"TikTok no aceptó {os.path.basename(ruta)}; sigue en la cola.\n{salida.strip()[-300:]}")
            break
        print(f"Subido {os.path.basename(ruta)}")
        cola.pop(0)
        subidos += 1
        with open(COLA, "w", encoding="utf-8") as f:
            f.write("".join(l + "\n" for l in cola))
        time.sleep(5)


if __name__ == "__main__":
    main()
