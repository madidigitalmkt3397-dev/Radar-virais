# -*- coding: utf-8 -*-
"""Busca a transcricao de um video do YouTube no SEU computador.

Por que existe: o YouTube bloqueia o IP de nuvem do Render na hora de entregar
legenda (LOGIN_REQUIRED -> 403 -> timeout), mas o IP da sua casa funciona
normalmente (0.8s). Este script busca a transcricao aqui e:

  * por padrao: copia para a area de transferencia (Ctrl+V) e salva em
    transcricao.txt - e so colar na secao "Insercao Manual" do site;
  * com --duracao: chama a IA do site (a IA roda no servidor, so a
    transcricao vem de aqui) e salva roteiro.json na pasta do projeto.

Uso:
    python buscar_transcricao.py <url_ou_id_do_video>
    python buscar_transcricao.py <url> --duracao 15

100% gratuito - usa o mesmo codigo da cadeia oficial (Innertube), so de
biblioteca padrao do Python.
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.youtube_service import get_video_transcript  # noqa: E402

SITE = "https://radar-virais.onrender.com"
PASTA = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def extrair_id(texto):
    """Aceita URL completa (watch/youtu.be/shorts) ou o ID solto."""
    texto = (texto or "").strip()
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{5,20})", texto)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{5,20}", texto):
        return texto
    return None


def pegar_titulo(video_id):
    """Titulo/canal via oEmbed (endpoint publico do YouTube, responde sempre)."""
    url = ("https://www.youtube.com/oembed?format=json&url=https%3A%2F%2F"
           "www.youtube.com%2Fwatch%3Fv%3D" + video_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
        return dados.get("title", ""), dados.get("author_name", "")
    except Exception:
        return "", ""


def copiar_para_area_de_transferencia(texto):
    """Ctrl+V via API nativa do Windows (CF_UNICODETEXT, sem BOM).

    O clip.exe aceita UTF-16 com BOM, mas esse BOM vaza como um caractere
    invisivel no inicio do texto colado - a API direta nao tem esse defeito.
    """
    try:
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.CloseClipboard.restype = wintypes.BOOL

        pacote = (texto + "\0").encode("utf-16-le")  # sem BOM, com terminador
        hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(pacote))
        if not hglobal:
            return False
        ponteiro = kernel32.GlobalLock(hglobal)
        if not ponteiro:
            kernel32.GlobalFree(hglobal)
            return False
        ctypes.memmove(ponteiro, pacote, len(pacote))
        kernel32.GlobalUnlock(hglobal)

        # outro app pode estar com a clipboard aberta: 5 tentativas rapidas
        aberta = False
        for _ in range(5):
            if user32.OpenClipboard(None):
                aberta = True
                break
            time.sleep(0.05)
        if not aberta:
            kernel32.GlobalFree(hglobal)
            return False
        user32.EmptyClipboard()
        definido = user32.SetClipboardData(CF_UNICODETEXT, hglobal) is not None
        user32.CloseClipboard()
        if not definido:   # em caso de sucesso o sistema fica dono da memoria
            kernel32.GlobalFree(hglobal)
        return bool(definido)
    except Exception:
        # ultimo recurso: clip.exe (funciona, mas deixa um BOM invisivel)
        try:
            r = subprocess.run(["clip"], input=texto.encode("utf-16"),
                               capture_output=True, timeout=15)
            return r.returncode == 0
        except Exception:
            return False


def gerar_roteiro(video_id, titulo, canal, transcricao, duracao):
    """Manda a transcricao para a IA do site e salva roteiro.json."""
    corpo = json.dumps({
        "titulo": titulo or f"Video {video_id}",
        "descricao": canal,
        "transcricao": transcricao,
        "duracao_segundos": duracao,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{SITE}/api/analyze-transcript", data=corpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        dados = json.loads(r.read().decode("utf-8", "replace"))
    pacote = dados.get("script") or dados
    destino = os.path.join(PASTA, "roteiro.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(pacote, f, ensure_ascii=False, indent=2)
    return destino


def main():
    args = [a for a in sys.argv[1:]]
    duracao = None
    if "--duracao" in args:
        i = args.index("--duracao")
        try:
            duracao = int(args[i + 1])
            del args[i:i + 2]
        except (IndexError, ValueError):
            print("[!] --duracao precisa de um numero (ex.: --duracao 15)")
            return 1

    if not args:
        print("Uso: python buscar_transcricao.py <url_ou_id> "
              "[--duracao 15|20|30|60]")
        print("Ex.: python buscar_transcricao.py "
              "https://www.youtube.com/watch?v=VIDEO --duracao 15")
        return 1

    video_id = extrair_id(args[0])
    if not video_id:
        print(f"[!] Nao consegui entender o video: {args[0]!r}")
        print(" -> Cole a URL completa ou o ID do video.")
        return 1

    titulo, canal = pegar_titulo(video_id)
    print(f"[1/3] Video: {titulo or '(titulo indisponivel)'}"
          + (f" | {canal}" if canal else ""))
    print(f"      ID: {video_id}")

    print("[2/3] Buscando a transcricao no seu computador...")
    try:
        transcricao = get_video_transcript(video_id)
    except ValueError as e:
        print(f"[!] {e}")
        return 1
    print(f"[OK] {len(transcricao)} caracteres")

    arquivo = os.path.join(PASTA, "transcricao.txt")
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(transcricao)
    copiado = copiar_para_area_de_transferencia(transcricao)

    if duracao is None:
        print(f"[3/3] Transcricao salva em: {arquivo}")
        if copiado:
            print("[OK] Tambem copiada para a area de transferencia "
                  "(pronta para o Ctrl+V)")
        print("")
        print("Como usar no site:")
        print("  1. Abra o site e va na secao \"Insercao Manual\"")
        print("  2. Cole (Ctrl+V) - ou copie o conteudo de transcricao.txt")
        print("  3. Escolha a duracao e clique em gerar a analise")
        return 0

    duracao = max(15, min(duracao, 600))
    print(f"[3/3] Gerando o roteiro de {duracao}s com a IA do site...")
    try:
        destino = gerar_roteiro(video_id, titulo, canal, transcricao, duracao)
    except Exception as e:
        print(f"[!] A IA do site falhou: {str(e)[:200]}")
        print(f" -> A transcricao esta salva em {arquivo} e copiada; "
              "use o modo manual no site.")
        return 1
    print(f"[OK] Roteiro salvo em: {destino}")
    print("")
    print("Proximos passos (igual sempre):")
    print("  1. Abra as cenas em: cenas\\")
    print("  2. python gerar_narracao.py")
    print("  3. python render_video.py")
    print("  4. O video fica em: output\\video_final.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
