# -*- coding: utf-8 -*-
"""
===========================================================
 FASE 6 - Render do video final (MoviePy)
===========================================================
 COMO USAR (passo a passo):
   1. `roteiro.json` baixado do site, nesta pasta
   2. Cenas na pasta `cenas/` (cena1.mp4, cena2.mp4...)
   3. Narracao:  python gerar_narracao.py   (gera audio/cenaN.mp3)
   4. Render:    python render_video.py
      -> saida: `output/video_final.mp4`

 O que este script faz:
   - Junta as cenas na ordem dos numeros
   - Coloca a narracao de cada cena (pasta `audio/`)
   - Se a narracao for maior que o video, congela o ultimo quadro
   - Cenas sem audio ficam em silencio (sem quebrar o render)

 Futuro: efeitos sonoros de `banco_efeitos/` (ver roteiro:
 campo efeito_sonoro_sugerido de cada cena).
===========================================================
"""

import json
import re
import sys
import time
from pathlib import Path

# Nunca derruba o script por causa de caractere estranho no console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# ---------- Configuracoes ----------
BASE = Path(__file__).resolve().parent
PASTA_CENAS = BASE / "cenas"
PASTA_AUDIO = BASE / "audio"
PASTA_SAIDA = BASE / "output"
ARQUIVO_ROTEIRO = BASE / "roteiro.json"

EXTENSOES_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".webp"}
EXTENSOES_AUDIO = {".mp3", ".wav"}

TEMPO_IMAGEM_SEGUNDOS = 3.0  # duracao de cada imagem fixa (sem narracao)
FPS_PADRAO = 30
NOME_SAIDA = "video_final.mp4"

# Quando a narracao e MAIOR que o clipe, o que fazer com o excesso:
#   "lento"    -> video continua em MOVIMENTO, so que mais devagar (recomendado)
#   "congelar" -> ultimo quadro parado ate a fala acabar (efeito "travado")
COMO_ESTICAR = "lento"


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


def localizar_narracao(numero: int):
    """Procura audio/cenaN.mp3 (ou .wav) para a cena N."""
    if not PASTA_AUDIO.exists():
        return None
    for ext in EXTENSOES_AUDIO:
        for nome in (f"cena{numero}{ext}", f"{numero}{ext}"):
            caminho = PASTA_AUDIO / nome
            if caminho.exists():
                return caminho
    return None


def carregar_roteiro():
    """Le o roteiro.json baixado do site (opcional, mas recomendado)."""
    if not ARQUIVO_ROTEIRO.exists():
        print("[!] roteiro.json nao encontrado - sem ele nao da para conferir")
        print("    se todas as cenas estao ai (baixe no site: Baixar roteiro)")
        return None
    try:
        dados = json.loads(ARQUIVO_ROTEIRO.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] roteiro.json ilegivel ({e}) - seguindo sem ele")
        return None

    # Mostra QUAL roteiro foi lido - evita usar um arquivo antigo sem perceber
    titulo = dados.get("titulo_otimizado") or "(sem titulo)"
    data = time.strftime("%d/%m/%Y %H:%M", time.localtime(ARQUIVO_ROTEIRO.stat().st_mtime))
    n_cenas = len(dados.get("cenas")) if isinstance(dados.get("cenas"), list) else 0
    print(f'[OK] Roteiro lido: "{titulo}"')
    print(f"     arquivo salvo em {data} | {n_cenas} cena(s)")
    return dados


def aplicar_narracao(clip, caminho_audio, is_imagem, AudioFileClip, ImageClip, concatenate_videoclips):
    """
    Encaixa a narracao na cena:
    - se o video for menor que a fala, estende:
        COMO_ESTICAR="lento"    -> video continua em movimento (so que devagar)
        COMO_ESTICAR="congelar" -> ultimo quadro parado ate a fala acabar
    - se o video for MUITO maior que a fala, corta no fim da fala (evita buraco mudo)
    - o audio da narracao SUBSTITUI o som original da cena
    Devolve (clip_final, objeto_audio_para_fechar).
    """
    audio = AudioFileClip(str(caminho_audio))

    # Video menor que a narracao -> estica ate a fala terminar
    if audio.duration > clip.duration + 0.05:
        alvo = audio.duration
        if is_imagem:
            clip = clip.with_duration(alvo)
        elif COMO_ESTICAR == "lento":
            margem = min(0.05, clip.duration * 0.1)
            fator = (clip.duration - margem) / alvo  # < 1 = joga mais devagar
            clip = clip.time_transform(lambda t: t * fator).with_duration(alvo)
        else:  # "congelar"
            quadro = clip.get_frame(max(clip.duration - 0.06, 0))
            congelado = ImageClip(quadro).with_duration(alvo - clip.duration)
            clip = concatenate_videoclips([clip, congelado], method="chain")

    # Video bem maior que a narracao -> corta um pouco apos o fim da fala
    elif clip.duration > audio.duration + 1.0:
        clip = clip.with_duration(audio.duration + 0.4)

    return clip.with_audio(audio), audio


def principal():
    print("=" * 58)
    print(" FASE 6 - Render do video final")
    print("=" * 58)

    # 1. MoviePy instalado?
    try:
        from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
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
        print(f"[OK] Pastas: {esperadas} cena(s) no roteiro | {len(cenas)} arquivo(s) em cenas/")
        if len(cenas) != esperadas:
            print(f"[!] ATENCAO: os numeros NAO batem! Verifique se o roteiro.json e o certo.")
            if len(cenas) < esperadas:
                faltando = [c.get("numero", i + 1) for i, c in enumerate(roteiro["cenas"])]
                print(f"    FALTAM cenas - esperadas: {faltando}")

        # Roteiro mais novo que os audios = narracao desatualizada
        if PASTA_AUDIO.exists():
            audios = list(PASTA_AUDIO.glob("cena*"))
            if audios:
                mais_novo = max(a.stat().st_mtime for a in audios)
                if ARQUIVO_ROTEIRO.stat().st_mtime > mais_novo + 1:
                    print("[!] ATENCAO: roteiro.json e MAIS NOVO que os audios de audio/!")
                    print("    Rode: python gerar_narracao.py  (para atualizar a narracao)")
    else:
        print(f"[OK] Arquivos encontrados: {len(cenas)}")

    # 4. Carrega as cenas + narracao
    clips = []
    audios = []
    com_narracao = 0
    try:
        for ordem, arq in cenas:
            ext = arq.suffix.lower()
            is_imagem = ext in EXTENSOES_IMAGEM
            print(f"  -> Cena {ordem}: {arq.name} ...", end="", flush=True)

            if is_imagem:
                clip = ImageClip(str(arq)).with_duration(TEMPO_IMAGEM_SEGUNDOS)
            else:
                clip = VideoFileClip(str(arq))

            narracao = localizar_narracao(ordem)
            if narracao:
                clip, audio = aplicar_narracao(
                    clip, narracao, is_imagem, AudioFileClip, ImageClip, concatenate_videoclips
                )
                audios.append(audio)
                com_narracao += 1
                print(f" ok ({clip.duration:.1f}s) [narrado: {narracao.name}]")
            else:
                print(f" ok ({clip.duration:.1f}s)")

            clips.append(clip)

        print(f"[OK] Narração em {com_narracao}/{len(cenas)} cena(s)")
        if com_narracao < len(cenas):
            print("     (cenas sem audio ficam em silencio - rode gerar_narracao.py para todas)")

        # 5. Junta tudo (cenas com audio + cenas sem = CompositeAudioClip, sem erro)
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
        for a in audios:
            try:
                a.close()
            except Exception:
                pass


if __name__ == "__main__":
    principal()
