# -*- coding: utf-8 -*-
"""
===========================================================
 FASE 6 - Render do video final (MoviePy)
===========================================================
 COMO USAR (passo a passo):
   1. No site, clique em "Baixar roteiro (.json)" e salve
      o arquivo como `roteiro.json` nesta pasta do projeto
   2. Coloque os arquivos das cenas na pasta `cenas/`
      (cena1.mp4, cena2.mp4, cena3.mp4...)
   3. Rode:  python render_video.py
   4. Pronto! O video final sai em `output/video_final.mp4`

 Aceita videos (.mp4 .mov .avi .mkv .webm) e imagens
 (.png .jpg .jpeg .webp - cada imagem fica 3 segundos).
===========================================================
"""

import json
import re
import sys
from pathlib import Path

# Nunca derruba o script por causa de caractere estranho no console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# ---------- Configuracoes ----------
BASE = Path(__file__).resolve().parent
PASTA_CENAS = BASE / "cenas"
PASTA_SAIDA = BASE / "output"
ARQUIVO_ROTEIRO = BASE / "roteiro.json"

EXTENSOES_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".webp"}

TEMPO_IMAGEM_SEGUNDOS = 3.0  # duracao de cada imagem fixa
FPS_PADRAO = 30
NOME_SAIDA = "video_final.mp4"


def descobrir_cenas():
    """Lista os arquivos da pasta cenas/ ordenados pelo numero no nome."""
    encontrados = []
    for arq in sorted(PASTA_CENAS.iterdir()):
        if arq.name.startswith(".") or arq.suffix.lower() not in (EXTENSOES_VIDEO | EXTENSOES_IMAGEM):
            continue
        m = re.search(r"(\d+)", arq.stem)
        ordem = int(m.group(1)) if m else 999
        encontrados.append((ordem, arq))
    encontrados.sort(key=lambda t: (t[0], t[1].name.lower()))
    return encontrados


def carregar_roteiro():
    """Le o roteiro.json baixado do site (opcional, mas recomendado)."""
    if not ARQUIVO_ROTEIRO.exists():
        print("[!] roteiro.json nao encontrado - sem ele nao da para conferir")
        print("    se todas as cenas estao ai (baixe no site: Baixar roteiro)")
        return None
    try:
        return json.loads(ARQUIVO_ROTEIRO.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] roteiro.json ilegivel ({e}) - seguindo sem ele")
        return None


def principal():
    print("=" * 58)
    print(" FASE 6 - Render do video final")
    print("=" * 58)

    # 1. MoviePy instalado?
    try:
        from moviepy import ImageClip, VideoFileClip, concatenate_videoclips
    except ImportError:
        sys.exit("ERRO: MoviePy nao instalado. Rode primeiro:\n   python -m pip install moviepy")

    # 2. Pastas e cenas
    if not PASTA_CENAS.exists():
        sys.exit(f"ERRO: Pasta nao encontrada: {PASTA_CENAS}")

    cenas = descobrir_cenas()
    if not cenas:
        sys.exit(
            "ERRO: Nenhuma cena encontrada em `cenas/`.\n"
            "   Coloque os arquivos la (cena1.mp4, cena2.mp4...) e rode de novo."
        )

    # 3. Confere com o roteiro
    roteiro = carregar_roteiro()
    if roteiro and isinstance(roteiro.get("cenas"), list):
        esperadas = len(roteiro["cenas"])
        print(f"[OK] Roteiro: {esperadas} cena(s) esperada(s) | Arquivos: {len(cenas)}")
        if len(cenas) < esperadas:
            faltando = [c.get("numero", i + 1) for i, c in enumerate(roteiro["cenas"])]
            print(f"[!] FALTAM CENAS! Esperadas: {faltando} - veja a pasta `cenas/`")
    else:
        print(f"[OK] Arquivos encontrados: {len(cenas)}")

    # 4. Carrega as cenas
    clips = []
    try:
        for ordem, arq in cenas:
            ext = arq.suffix.lower()
            print(f"  -> Cena {ordem}: {arq.name} ...", end="", flush=True)
            if ext in EXTENSOES_IMAGEM:
                clip = ImageClip(str(arq)).with_duration(TEMPO_IMAGEM_SEGUNDOS)
            else:
                clip = VideoFileClip(str(arq))
            clips.append(clip)
            print(f" ok ({clip.duration:.1f}s)")

        # 5. Audio: mantem so se TODAS as cenas tiverem
        if all(c.audio is not None for c in clips):
            print("[OK] Audio original das cenas: mantido")
        else:
            print("[OK] Nem toda cena tem audio -> audio descartado (a narracao entra na Fase 4)")
            for c in clips:
                c.audio = None

        # 6. Junta tudo
        print("[...] Juntando as cenas...")
        final = concatenate_videoclips(clips, method="compose")

        PASTA_SAIDA.mkdir(exist_ok=True)
        destino = PASTA_SAIDA / NOME_SAIDA
        print(f"[...] Gerando {destino.name} (pode levar alguns minutos)...")
        final.write_videofile(
            str(destino),
            codec="libx264",
            audio_codec="aac",
            fps=FPS_PADRAO,
        )

        bytes_arquivo = destino.stat().st_size
        tamanho = (
            f"{bytes_arquivo / (1024 * 1024):.1f} MB"
            if bytes_arquivo >= 1024 * 1024
            else f"{bytes_arquivo / 1024:.0f} KB"
        )
        print("-" * 58)
        print(f" PRONTO! Video salvo em: {destino}")
        print(f" Duracao: {final.duration:.1f}s | Tamanho: {tamanho}")
        print("-" * 58)
        final.close()
    finally:
        for c in clips:
            try:
                c.close()
            except Exception:
                pass


if __name__ == "__main__":
    principal()
