"""Arma un video vertical de historia narrada, al estilo de las historias de Reddit.

    python hacer_video.py historias/001_x.txt [--voz es-MX-JorgeNeural] [--velocidad +15%] [--fondo ...]

La historia es un .txt: la primera línea es el título (la pregunta o el gancho) y
después el cuerpo, o varias respuestas con su tarjeta y su voz (el formato está
en leer_historia). El video sale en salida/<nombre>.mp4, y
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
import wave

import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(AQUI, "fuentes")
ANCHO, ALTO, FPS = 1080, 1920, 30
PAUSA_TITULO = 0.3    # silencio entre el título y el cuerpo
PAUSA_TRAMO = 0.5    # silencio entre una respuesta y la siguiente
PAUSA_MAX = 0.15      # silencio máximo entre dos palabras del cuerpo
TASA = 24000          # edge-tts entrega mp3 mono a 24 kHz
COLA = 1.2            # segundos al final, para que no corte en seco
CUENTA = "@historias_y_cosas12"
NOMBRE_EN_PANTALLA = "Usuario de Reddit"   # en las tarjetas de comentario, en vez del u/nombre real


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
    """Narra a ruta (.wav) y devuelve [inicio, fin, palabra] de cada palabra.
    Edge hace pausas largas en cada punto y coma; en TikTok eso bota gente,
    así que se recortan los silencios entre palabras a PAUSA_MAX."""
    mp3 = ruta[:-4] + ".mp3"
    palabras = asyncio.run(_narrar(texto, voz, velocidad, mp3))
    crudo = subprocess.run([FFMPEG, "-loglevel", "error", "-i", mp3, "-f", "s16le", "-ac", "1",
                            "-ar", str(TASA), "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(crudo, dtype=np.int16)
    trozos, quitado, cursor = [], 0.0, 0.0
    # los bordes también: poco silencio antes de la primera palabra y después de la última
    limites = [(0.0, palabras[0][0], 0.05)]
    limites += [(a[1], b[0], PAUSA_MAX) for a, b in zip(palabras, palabras[1:])]
    limites.append((palabras[-1][1], len(audio) / TASA, 0.12))
    ajustes = []
    for fin_ant, ini_sig, maximo in limites:
        hueco = ini_sig - fin_ant
        sobra = hueco - maximo
        if sobra > 0.01:
            corte_ini = fin_ant + maximo * 0.6   # deja más aire después de la palabra
            trozos.append(audio[int(cursor * TASA):int(corte_ini * TASA)])
            cursor = corte_ini + sobra
            quitado += sobra
        ajustes.append(quitado)
    trozos.append(audio[int(cursor * TASA):])
    for p, desplazamiento in zip(palabras, ajustes):
        p[0] -= desplazamiento
        p[1] -= desplazamiento
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TASA)
        w.writeframes(np.concatenate(trozos).tobytes())
    return palabras


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

def tarjeta(titulo, pie, ruta):
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
    d.text((pad, y), pie, font=f_cuenta, fill=(140, 140, 140))
    img.save(ruta)



def votos_txt(n):
    if n >= 1000:
        return f"{n / 1000:.1f}".replace(".", ",").replace(",0", "") + " mil"
    return str(n)


def comentario(usuario, votos, subreddit, texto, ruta):
    """Comentario al estilo Reddit: avatar, usuario, votos y la primera frase
    de la respuesta. Queda arriba mientras se narra esa respuesta."""
    w, pad = 940, 38
    f_user = ImageFont.truetype(os.path.join(FUENTES, "Montserrat-ExtraBold.ttf"), 36)
    f_meta = ImageFont.truetype(os.path.join(FUENTES, "Montserrat-SemiBold.ttf"), 30)
    f_texto = ImageFont.truetype(os.path.join(FUENTES, "Montserrat-SemiBold.ttf"), 40)
    frase = texto.split(". ")[0].rstrip(".") + "…"
    lineas = textwrap.wrap(frase, width=36)
    if len(lineas) > 3:
        lineas = lineas[:3]
        lineas[-1] = lineas[-1].rstrip(" ,.…") + "…"
    h = pad + 76 + 22 + len(lineas) * 52 + 26 + 44 + pad
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 14, w + 10, h + 14], 34, fill=(0, 0, 0, 90))
    d.rounded_rectangle([0, 0, w, h], 34, fill=(255, 255, 255, 255))
    # avatar: color fijo por usuario, inicial en blanco
    tono = (sum(map(ord, usuario)) % 360) / 360
    color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(tono, 0.6, 0.9))
    d.ellipse([pad, pad, pad + 76, pad + 76], fill=color)
    # El nombre real no se muestra (regla del canal: proteger a los autores);
    # solo sirve para variar el color del avatar entre respuestas.
    d.text((pad + 38, pad + 38), "U", font=f_user, fill="white", anchor="mm")
    d.text((pad + 96, pad + 20), NOMBRE_EN_PANTALLA, font=f_user, fill=(26, 26, 27), anchor="lm")
    d.text((pad + 96, pad + 58), subreddit, font=f_meta, fill=(120, 124, 126), anchor="lm")
    y = pad + 76 + 22
    for linea in lineas:
        d.text((pad, y), linea, font=f_texto, fill=(26, 26, 27))
        y += 52
    y += 26
    # flecha de voto (triángulo) + votos
    d.polygon([(pad, y + 30), (pad + 16, y + 8), (pad + 32, y + 30)], fill=(255, 69, 0))
    d.text((pad + 46, y + 20), votos_txt(votos), font=f_meta, fill=(255, 69, 0), anchor="lm")
    d.text((pad + 250, y + 20), "Responder   ·   Compartir", font=f_meta, fill=(135, 138, 140), anchor="lm")
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

def leer_historia(ruta, voz_defecto):
    """Formato del .txt:

        Título (la pregunta o el gancho)
        # tarjeta: texto bajo el título      # fuente: url   # voz: ...   # subreddit: r/...

        Cuerpo de una sola historia, narrado de corrido.

    o, para varias respuestas, un tramo por respuesta:

        == u/usuario | votos | voz | r/subreddit   (voz y subreddit son opcionales)
        texto de la respuesta
        == narrador | voz
        texto sin tarjeta (p. ej. la actualización que escribe otra persona)
        == cierre
        ¿Pregunta final?

    Cada respuesta sale con su tarjeta de comentario y su propia voz; el
    narrador y el cierre van sin tarjeta, con la voz del título salvo que se
    indique otra."""
    with open(ruta, encoding="utf-8") as f:
        lineas = [l.strip() for l in f.read().strip().splitlines()]
    datos = {}
    for l in lineas:
        if l.startswith("#"):
            k, _, v = l[1:].partition(":")
            datos.setdefault(k.strip(), []).append(v.strip())
    lineas = [l for l in lineas if l and not l.startswith("#")]
    titulo, resto = lineas[0], lineas[1:]
    voz = datos.get("voz", [voz_defecto])[-1]
    tramos, actual = [], None
    for l in resto:
        if l.startswith("=="):
            partes = [x.strip() for x in l[2:].split("|")]
            if partes[0].lower() in ("cierre", "narrador"):
                actual = {"usuario": None, "votos": 0, "texto": "",
                          "voz": partes[1] if len(partes) > 1 and partes[1] else voz}
            else:
                actual = {"usuario": partes[0], "votos": int(partes[1]),
                          "voz": partes[2] if len(partes) > 2 and partes[2] else voz,
                          "subreddit": partes[3] if len(partes) > 3 else None, "texto": ""}
            tramos.append(actual)
        else:
            if actual is None:
                actual = {"usuario": None, "votos": 0, "voz": voz, "texto": ""}
                tramos.append(actual)
            actual["texto"] = (actual["texto"] + " " + l).strip()
    return titulo, datos, tramos


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
    titulo, datos, tramos = leer_historia(a.historia, a.voz)
    pie = datos.get("tarjeta", ["Historia completa"])[-1]
    subreddit = datos.get("subreddit", ["r/AskReddit"])[-1]
    fuentes = datos.get("fuente", [])
    voz_titulo = datos.get("voz", [a.voz])[-1]

    print("Narrando…")
    narrar(titulo, voz_titulo, a.velocidad, os.path.join(tmp, "titulo.wav"))
    t_titulo = duracion(os.path.join(tmp, "titulo.wav"))
    t = t_titulo + PAUSA_TITULO
    palabras, audios, pausas, tarjetas = [], ["titulo.wav"], [PAUSA_TITULO], []
    for i, tramo in enumerate(tramos):
        wav = f"tramo{i}.wav"
        ps = narrar(tramo["texto"], tramo["voz"], a.velocidad, os.path.join(tmp, wav))
        for p in ps:
            p[0] += t
            p[1] += t
        palabras += ps
        dur = duracion(os.path.join(tmp, wav))
        if tramo["usuario"]:
            png = f"comentario{i}.png"
            comentario(tramo["usuario"], tramo["votos"], tramo.get("subreddit") or subreddit,
                       tramo["texto"], os.path.join(tmp, png))
            tarjetas.append((png, t - 0.15, t + dur, "ARRIBA"))
        audios.append(wav)
        pausas.append(PAUSA_TRAMO if i + 1 < len(tramos) else COLA)
        t += dur + pausas[-1]
    total = t
    entradas = sum((["-i", os.path.join(tmp, x)] for x in audios), [])
    filtro = "".join(f"[{i}:a]apad=pad_dur={pa}[a{i}];" for i, pa in enumerate(pausas))
    filtro += "".join(f"[a{i}]" for i in range(len(audios))) + f"concat=n={len(audios)}:v=0:a=1[o]"
    ff(*entradas, "-filter_complex", filtro, "-map", "[o]", "-ar", "44100", os.path.join(tmp, "voz.wav"))

    escribir_ass(palabras, os.path.join(tmp, "subs.ass"))
    tarjeta(titulo, pie, os.path.join(tmp, "tarjeta.png"))
    tarjetas.insert(0, ("tarjeta.png", 0.0, t_titulo + 0.1, "CENTRO"))

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
    # Rutas relativas a tmp: el filtro ass no se lleva bien con "C:\" en Windows.
    fuentes_rel = os.path.relpath(FUENTES, tmp).replace("\\", "/")
    entradas = ["-i", "fondo.mp4", "-i", "voz.wav"]
    filtro, previo = "", "0:v"
    for k, (png, desde, hasta, lugar) in enumerate(tarjetas):
        entradas += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.2f}", "-i", png]
        y = "H*0.40-h/2" if lugar == "CENTRO" else "150"
        filtro += (f"[{k + 2}:v]format=rgba,fade=in:st={max(desde, 0):.2f}:d=0.2:alpha=1,"
                   f"fade=out:st={hasta:.2f}:d=0.25:alpha=1[c{k}];"
                   f"[{previo}][c{k}]overlay=(W-w)/2:{y}:enable='between(t,{desde:.2f},{hasta + 0.3:.2f})'[v{k}];")
        previo = f"v{k}"
    filtro += f"[{previo}]ass=subs.ass:fontsdir={fuentes_rel}[v]"
    ff(*entradas, "-filter_complex", filtro,
       "-map", "[v]", "-map", "1:a", "-t", f"{total:.2f}",
       "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.abspath(salida), cwd=tmp)
    # Gancho y hashtags propios de cada historia (REGLAS.md); si faltan, el título y unos genéricos.
    gancho = datos.get("descripcion", [titulo])[-1]
    hashtags = datos.get("hashtags", ["#historiasdereddit #reddit #historiasreales #storytime #parati"])[-1]
    descripcion = (f"{gancho}\n\n{hashtags}\n\n"
                   + "".join(f"Historias de Reddit, adaptadas: {u}\n" for u in fuentes)
                   + credito(origen)).strip()
    with open(os.path.join(AQUI, "salida", f"{nombre}.txt"), "w", encoding="utf-8") as f:
        f.write(descripcion + "\n")
    print(f"Listo: {salida} ({total:.0f} s)")
    print(f"Descripción para TikTok (salida/{nombre}.txt):\n{descripcion}")


if __name__ == "__main__":
    main()
