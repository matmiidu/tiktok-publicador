"""Arma un video vertical de historia narrada, al estilo de las historias de Reddit.

    python hacer_video.py historias/001_x.txt [--voz es-MX-JorgeNeural] [--velocidad +15%] [--fondo ...]

La historia es un .txt: la primera línea es el título (la pregunta o el gancho),
después una línea en blanco y el cuerpo. El video sale en salida/<nombre>.mp4, y
al lado salida/<nombre>.txt con la descripción para TikTok (incluye el crédito
del fondo, que las licencias CC BY exigen).

--fondo puede ser un video, una carpeta (elige uno al azar) o "animado". Por
defecto usa la carpeta fondos/ si tiene videos, y si no, la animación propia
(pelotas que rebotan dentro de un anillo). De cada video toma un tramo al azar,
recortado a 9:16. Los créditos de cada fondo están en fondos/creditos.json.
"""
import argparse
import asyncio
import colorsys
import glob
import json
import math
import os
import random
import subprocess
import sys
import textwrap

import edge_tts
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(AQUI, "fuentes")
ANCHO, ALTO, FPS = 1080, 1920, 30
PAUSA_TITULO = 0.45   # silencio entre el título y el cuerpo
COLA = 1.2            # segundos al final, para que no corte en seco
CUENTA = "@historias_y_cosas12"


def binario(nombre):
    hallados = glob.glob(os.path.expanduser(
        f"~/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*/bin/{nombre}.exe"))
    return hallados[0] if hallados else nombre


FFMPEG, FFPROBE = binario("ffmpeg"), binario("ffprobe")


def ff(*args, **kw):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True, **kw)


def duracion(ruta):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", ruta], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


# ---------- voz ----------

async def _narrar(texto, voz, velocidad, ruta):
    com = edge_tts.Communicate(texto, voz, rate=velocidad, boundary="WordBoundary")
    palabras = []
    with open(ruta, "wb") as f:
        async for trozo in com.stream():
            if trozo["type"] == "audio":
                f.write(trozo["data"])
            elif trozo["type"] == "WordBoundary":
                ini = trozo["offset"] / 1e7
                palabras.append([ini, ini + trozo["duration"] / 1e7, trozo["text"]])
    return palabras


def narrar(texto, voz, velocidad, ruta):
    return asyncio.run(_narrar(texto, voz, velocidad, ruta))


# ---------- subtítulos ----------

def agrupar(palabras, max_palabras=3, max_letras=16, pausa=0.18):
    """Junta palabras en grupos cortos. Corta en las pausas de la voz (que caen
    en comas y puntos), o si el grupo se pone largo."""
    grupos, actual = [], []
    for i, p in enumerate(palabras):
        actual.append(p)
        letras = sum(len(x[2]) for x in actual) + len(actual) - 1
        sig = palabras[i + 1] if i + 1 < len(palabras) else None
        corta = (sig is None or len(actual) >= max_palabras or letras >= max_letras
                 or sig[0] - p[1] > pausa
                 or letras + 1 + len(sig[2]) > max_letras + 4)
        if corta:
            grupos.append(actual)
            actual = []
    return grupos


def tiempo_ass(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def escribir_ass(palabras, ruta):
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ANCHO}
PlayResY: {ALTO}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,Montserrat Black,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,10,4,2,60,60,440,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    grupos = agrupar(palabras)
    for g, grupo in enumerate(grupos):
        fin_grupo = grupos[g + 1][0][0] if g + 1 < len(grupos) else grupo[-1][1] + 0.6
        for i, (ini, _, _) in enumerate(grupo):
            desde = grupo[0][0] if i == 0 else ini
            hasta = grupo[i + 1][0] if i + 1 < len(grupo) else fin_grupo
            texto = " ".join(
                ("{\\c&H00E6FF&}" + w.upper() + "{\\c&HFFFFFF&}") if j == i else w.upper()
                for j, (_, _, w) in enumerate(grupo))
            pop = "{\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            lineas.append(f"Dialogue: 0,{tiempo_ass(desde)},{tiempo_ass(hasta)},Base,,0,0,0,,{pop}{texto}")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(lineas) + "\n")


# ---------- tarjeta del título ----------

def tarjeta(titulo, ruta):
    w, pad = 940, 44
    f_titulo = ImageFont.truetype(os.path.join(FUENTES, "Montserrat-ExtraBold.ttf"), 54)
    f_cuenta = ImageFont.truetype(os.path.join(FUENTES, "Montserrat-SemiBold.ttf"), 34)
    f_ini = ImageFont.truetype(os.path.join(FUENTES, "Montserrat-Black.ttf"), 44)
    lineas = textwrap.wrap(titulo, width=28)
    alto_titulo = len(lineas) * 68
    h = pad + 90 + 26 + alto_titulo + 30 + 50 + pad
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 14, w + 10, h + 14], 40, fill=(0, 0, 0, 90))       # sombra
    d.rounded_rectangle([0, 0, w, h], 40, fill=(255, 255, 255, 255))
    d.ellipse([pad, pad, pad + 90, pad + 90], fill=(254, 44, 85, 255))
    d.text((pad + 45, pad + 45), "H", font=f_ini, fill="white", anchor="mm")
    d.text((pad + 115, pad + 45), CUENTA, font=f_cuenta, fill=(30, 30, 30), anchor="lm")
    y = pad + 90 + 26
    for linea in lineas:
        d.text((pad, y), linea, font=f_titulo, fill=(15, 15, 15))
        y += 68
    y += 30
    d.text((pad, y), "Historia completa", font=f_cuenta, fill=(140, 140, 140))
    img.save(ruta)


# ---------- fondo ----------

def fondo_animado(segundos, ruta, semilla):
    """Pelotas que rebotan dentro de un anillo y dejan estela. Crecen con cada
    rebote; al llegar al tope se achican y aparece otra."""
    rnd = random.Random(semilla)
    W, H = ANCHO // 2, ALTO // 2
    cx, cy, R = W / 2, H * 0.40, 225
    g = 0.32
    tono_base = rnd.random()

    def nueva():
        ang = rnd.uniform(0, 2 * math.pi)
        return {"x": cx + rnd.uniform(-60, 60), "y": cy - 120, "vx": 7 * math.cos(ang),
                "vy": 7 * math.sin(ang), "r": 14.0, "h": rnd.random()}

    bolas = [nueva() for _ in range(2)]
    oscuro = Image.new("RGB", (W, H), (9, 9, 16))
    img = oscuro.copy()
    proc = subprocess.Popen(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-vf", f"scale={ANCHO}:{ALTO}:flags=lanczos", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", ruta], stdin=subprocess.PIPE)
    for n in range(int(segundos * FPS) + 1):
        img = Image.blend(img, oscuro, 0.09)
        d = ImageDraw.Draw(img)
        tono = (tono_base + n / 900) % 1
        anillo = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(tono, 0.55, 1))
        d.ellipse([cx - R - 7, cy - R - 7, cx + R + 7, cy + R + 7], outline=anillo, width=7)
        for b in list(bolas):
            for _ in range(2):  # dos subpasos: menos rebotes perdidos
                b["vy"] += g / 2
                b["x"] += b["vx"] / 2
                b["y"] += b["vy"] / 2
                dx, dy = b["x"] - cx, b["y"] - cy
                dist = math.hypot(dx, dy)
                if dist + b["r"] > R:
                    nx, ny = dx / dist, dy / dist
                    punto = b["vx"] * nx + b["vy"] * ny
                    b["vx"] -= 2 * punto * nx
                    b["vy"] -= 2 * punto * ny
                    # un empujoncito para que no pierdan energía
                    rapidez = math.hypot(b["vx"], b["vy"])
                    if rapidez < 11:
                        b["vx"] *= 1.04
                        b["vy"] *= 1.04
                    b["x"], b["y"] = cx + nx * (R - b["r"]), cy + ny * (R - b["r"])
                    b["r"] += 2.2
                    b["h"] = (b["h"] + 0.09) % 1
                    if b["r"] > 85:
                        b["r"] = 14.0
                        if len(bolas) < 4:
                            bolas.append(nueva())
            color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(b["h"], 0.75, 1))
            d.ellipse([b["x"] - b["r"], b["y"] - b["r"], b["x"] + b["r"], b["y"] + b["r"]],
                      fill=color, outline=(255, 255, 255), width=3)
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit("FFmpeg falló al hacer el fondo")


def elegir_fondo(opcion, semilla):
    """Devuelve la ruta de un video de fondo, o None para la animación."""
    if opcion == "animado":
        return None
    carpeta = opcion or os.path.join(AQUI, "fondos")
    if os.path.isfile(carpeta):
        return carpeta
    videos = sorted(glob.glob(os.path.join(carpeta, "*.mp4")))
    if not videos:
        if opcion:
            sys.exit(f"No hay videos .mp4 en {carpeta}")
        return None
    return random.Random(semilla).choice(videos)


def credito(ruta_fondo):
    if not ruta_fondo:
        return ""
    with open(os.path.join(AQUI, "fondos", "creditos.json"), encoding="utf-8") as f:
        c = json.load(f).get(os.path.basename(ruta_fondo))
    if not c:
        return f"Fondo: {os.path.basename(ruta_fondo)} (sin crédito registrado en fondos/creditos.json)"
    return (f"Gameplay de fondo: {c['autor']} ({c['url']}), licencia {c['licencia']}. "
            "Editado del original.")


def fondo_de_video(origen, segundos, ruta, semilla):
    total = duracion(origen)
    if total < segundos:
        sys.exit(f"El fondo dura {total:.0f}s y el video necesita {segundos:.0f}s")
    ini = random.Random(semilla).uniform(0, total - segundos)
    ff("-ss", f"{ini:.2f}", "-t", f"{segundos:.2f}", "-i", origen, "-an",
       "-vf", f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,crop={ANCHO}:{ALTO},fps={FPS}",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", ruta)


# ---------- armado ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("historia")
    ap.add_argument("--voz", default="es-MX-JorgeNeural")
    ap.add_argument("--velocidad", default="+15%")
    ap.add_argument("--fondo")
    a = ap.parse_args()

    nombre = os.path.splitext(os.path.basename(a.historia))[0]
    tmp = os.path.join(AQUI, "salida", "tmp", nombre)
    os.makedirs(tmp, exist_ok=True)
    with open(a.historia, encoding="utf-8") as f:
        titulo, _, cuerpo = f.read().strip().partition("\n")
    cuerpo = " ".join(cuerpo.split())

    print("Narrando…")
    narrar(titulo, a.voz, a.velocidad, os.path.join(tmp, "titulo.mp3"))
    palabras = narrar(cuerpo, a.voz, a.velocidad, os.path.join(tmp, "cuerpo.mp3"))
    t_titulo = duracion(os.path.join(tmp, "titulo.mp3"))
    desfase = t_titulo + PAUSA_TITULO
    for p in palabras:
        p[0] += desfase
        p[1] += desfase
    total = desfase + duracion(os.path.join(tmp, "cuerpo.mp3")) + COLA
    ff("-i", os.path.join(tmp, "titulo.mp3"), "-i", os.path.join(tmp, "cuerpo.mp3"),
       "-filter_complex", f"[0:a]apad=pad_dur={PAUSA_TITULO}[a];[a][1:a]concat=n=2:v=0:a=1,apad=pad_dur={COLA}[o]",
       "-map", "[o]", "-ar", "44100", os.path.join(tmp, "voz.wav"))

    escribir_ass(palabras, os.path.join(tmp, "subs.ass"))
    tarjeta(titulo, os.path.join(tmp, "tarjeta.png"))

    print(f"Fondo ({total:.0f} s)…")
    fondo = os.path.join(tmp, "fondo.mp4")
    origen = elegir_fondo(a.fondo, nombre)
    if origen:
        print(f"  usando {os.path.basename(origen)}")
        fondo_de_video(origen, total, fondo, nombre)
    else:
        fondo_animado(total, fondo, nombre)

    print("Armando…")
    salida = os.path.join(AQUI, "salida", f"{nombre}.mp4")
    sale = t_titulo + 0.1
    # Rutas relativas a tmp: el filtro ass no se lleva bien con "C:\" en Windows.
    fuentes_rel = os.path.relpath(FUENTES, tmp).replace("\\", "/")
    ff("-i", "fondo.mp4", "-loop", "1", "-framerate", str(FPS), "-i", "tarjeta.png", "-i", "voz.wav",
       "-filter_complex",
       f"[1:v]format=rgba,fade=in:st=0:d=0.25:alpha=1,fade=out:st={sale:.2f}:d=0.3:alpha=1[c];"
       f"[0:v][c]overlay=(W-w)/2:H*0.40-h/2:enable='lte(t,{sale + 0.35:.2f})'[v1];"
       f"[v1]ass=subs.ass:fontsdir={fuentes_rel}[v]",
       "-map", "[v]", "-map", "2:a", "-t", f"{total:.2f}",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.abspath(salida), cwd=tmp)
    descripcion = (f"{titulo}\n\n#historias #reddit #historiasdereddit #relatos #storytime\n\n"
                   f"{credito(origen)}").strip()
    with open(os.path.join(AQUI, "salida", f"{nombre}.txt"), "w", encoding="utf-8") as f:
        f.write(descripcion + "\n")
    print(f"Listo: {salida} ({total:.0f} s)")
    print(f"Descripción para TikTok (salida/{nombre}.txt):\n{descripcion}")


if __name__ == "__main__":
    main()
