"""Sube videos a los borradores de TikTok con la Content Posting API oficial.

Uso:
  python tiktok.py url                  # imprime el enlace de autorización
  python tiktok.py auth <código>        # canjea el código por un token (queda en token.json)
  python tiktok.py subir <video.mp4>    # sube el video a la bandeja de borradores
  python tiktok.py estado <publish_id>  # consulta cómo va una subida
"""
import json
import math
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(AQUI, "token.json")
API = "https://open.tiktokapis.com/v2"
MB = 1024 * 1024


def cargar_env():
    env = {}
    with open(os.path.join(AQUI, ".env"), encoding="utf-8") as f:
        for linea in f:
            if "=" in linea:
                k, v = linea.strip().split("=", 1)
                env[k] = v
    return env


def pedir(metodo, url, datos=None, headers=None, forma=False):
    headers = dict(headers or {})
    cuerpo = None
    if datos is not None:
        if forma:
            cuerpo = urllib.parse.urlencode(datos).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            cuerpo = json.dumps(datos).encode()
            headers["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=cuerpo, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"TikTok respondió {e.code}: {e.read().decode(errors='replace')}")


def guardar_token(t):
    t["vence"] = time.time() + int(t.get("expires_in", 0)) - 60
    t["refresh_vence"] = time.time() + int(t.get("refresh_expires_in", 0)) - 60
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(t, f, indent=2)


def token_vigente(env):
    if not os.path.exists(TOKEN_PATH):
        sys.exit("No hay token. Corre primero: python tiktok.py url")
    with open(TOKEN_PATH, encoding="utf-8") as f:
        t = json.load(f)
    if time.time() < t["vence"]:
        return t["access_token"]
    if time.time() >= t["refresh_vence"]:
        sys.exit("El token venció del todo. Vuelve a autorizar: python tiktok.py url")
    nuevo = pedir("POST", f"{API}/oauth/token/", forma=True, datos={
        "client_key": env["TIKTOK_CLIENT_KEY"],
        "client_secret": env["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": t["refresh_token"],
    })
    if "access_token" not in nuevo:
        sys.exit(f"No se pudo renovar el token: {nuevo}")
    guardar_token(nuevo)
    return nuevo["access_token"]


def cmd_url(env):
    params = {
        "client_key": env["TIKTOK_CLIENT_KEY"],
        "scope": "user.info.basic,video.upload",
        "response_type": "code",
        "redirect_uri": env["TIKTOK_REDIRECT_URI"],
        "state": secrets.token_urlsafe(8),
    }
    print("https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params))


def cmd_auth(env, codigo):
    codigo = codigo.split()[0]  # la página de retorno copia "código state"
    t = pedir("POST", f"{API}/oauth/token/", forma=True, datos={
        "client_key": env["TIKTOK_CLIENT_KEY"],
        "client_secret": env["TIKTOK_CLIENT_SECRET"],
        "code": codigo,
        "grant_type": "authorization_code",
        "redirect_uri": env["TIKTOK_REDIRECT_URI"],
    })
    if "access_token" not in t:
        sys.exit(f"No se pudo canjear el código: {t}")
    guardar_token(t)
    print(f"Autorizado. Permisos: {t.get('scope')}. Token guardado en token.json")


def partes(tamano):
    # Reglas de TikTok: menos de 5 MB va entero; si no, trozos de 5-64 MB
    # y el último absorbe el resto (hasta 128 MB).
    if tamano <= 64 * MB:
        return tamano, 1
    trozo = 10 * MB
    return trozo, tamano // trozo


def cmd_subir(env, ruta):
    token = token_vigente(env)
    tamano = os.path.getsize(ruta)
    trozo, n = partes(tamano)
    init = pedir("POST", f"{API}/post/publish/inbox/video/init/",
                 headers={"Authorization": f"Bearer {token}"},
                 datos={"source_info": {"source": "FILE_UPLOAD", "video_size": tamano,
                                        "chunk_size": trozo, "total_chunk_count": n}})
    if init.get("error", {}).get("code") not in (None, "ok"):
        sys.exit(f"TikTok rechazó la subida: {init['error']}")
    upload_url = init["data"]["upload_url"]
    publish_id = init["data"]["publish_id"]
    with open(ruta, "rb") as f:
        for i in range(n):
            inicio = i * trozo
            fin = tamano - 1 if i == n - 1 else inicio + trozo - 1
            f.seek(inicio)
            bloque = f.read(fin - inicio + 1)
            req = urllib.request.Request(upload_url, data=bloque, method="PUT", headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(bloque)),
                "Content-Range": f"bytes {inicio}-{fin}/{tamano}",
            })
            try:
                urllib.request.urlopen(req, timeout=600).close()
            except urllib.error.HTTPError as e:
                sys.exit(f"Falló el trozo {i + 1}/{n}: {e.code} {e.read().decode(errors='replace')}")
            print(f"  trozo {i + 1}/{n} subido ({math.ceil((fin + 1) / tamano * 100)}%)")
    print(f"Listo. publish_id = {publish_id}")
    print("Te debería llegar una notificación en TikTok para terminar de publicarlo.")
    cmd_estado(env, publish_id)


def cmd_estado(env, publish_id):
    token = token_vigente(env)
    r = pedir("POST", f"{API}/post/publish/status/fetch/",
              headers={"Authorization": f"Bearer {token}"},
              datos={"publish_id": publish_id})
    print(json.dumps(r.get("data", r), indent=2, ensure_ascii=False))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("url", "auth", "subir", "estado"):
        sys.exit(__doc__)
    env = cargar_env()
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "url":
        cmd_url(env)
    elif cmd == "auth":
        cmd_auth(env, " ".join(args))
    elif cmd == "subir":
        cmd_subir(env, args[0])
    else:
        cmd_estado(env, args[0])


if __name__ == "__main__":
    main()
