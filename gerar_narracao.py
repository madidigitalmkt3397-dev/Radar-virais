# -*- coding: utf-8 -*-
"""
===========================================================
 FASE 4 - Narracao com Edge-TTS (gratuito e ilimitado)
===========================================================
 COMO USAR:
   1. Tenha o `roteiro.json` (baixado do site) nesta pasta
   2. Rode:  python gerar_narracao.py
   3. Os audios nascem em `audio\\cena1.mp3`, `cena2.mp3`...
   4. Depois rode o render:  python render_video.py

 VOZ (edite as constantes abaixo):
   - pt-BR-FranciscaNeural (feminina)  <- padrao
   - pt-BR-AntonioNeural   (masculina)
   Taxa de fala: "+10%" mais rapido, "-10%" mais devagar
===========================================================
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Nunca derruba o script por caractere estranho no console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# ---------- Configuracoes ----------
BASE = Path(__file__).resolve().parent
ARQUIVO_ROTEIRO = BASE / "roteiro.json"
PASTA_AUDIO = BASE / "audio"

VOZ = "pt-BR-FranciscaNeural"
TAXA = "+0%"
TENTATIVAS = 3


async def _salvar_fala(texto: str, destino: Path):
    import edge_tts
    fala = edge_tts.Communicate(texto, VOZ, rate=TAXA)
    await fala.save(str(destino))


def gerar_narracao(texto: str, destino: Path) -> bool:
    ultimo_erro = None
    for tentativa in range(TENTATIVAS):
        try:
            asyncio.run(_salvar_fala(texto, destino))
            if destino.exists() and destino.stat().st_size > 0:
                return True
        except Exception as e:
            ultimo_erro = e
            time.sleep(2)
    print(f" [ERRO] {ultimo_erro}")
    return False


def duracao_do_audio(caminho: Path):
    try:
        from moviepy import AudioFileClip
        a = AudioFileClip(str(caminho))
        d = a.duration
        a.close()
        return d
    except Exception:
        return None


def principal():
    print("=" * 58)
    print(" FASE 4 - Narracao (Edge-TTS - gratis e ilimitado)")
    print("=" * 58)

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        sys.exit("ERRO: Edge-TTS nao instalado. Rode primeiro:\n   python -m pip install edge-tts")

    if not ARQUIVO_ROTEIRO.exists():
        sys.exit(
            "ERRO: roteiro.json nao encontrado.\n"
            "   Baixe no site (botao Baixar roteiro) e salve nesta pasta:"
            f"   {ARQUIVO_ROTEIRO}"
        )

    try:
        roteiro = json.loads(ARQUIVO_ROTEIRO.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"ERRO: roteiro.json ilegivel ({e})")

    cenas = roteiro.get("cenas")
    if not isinstance(cenas, list) or not cenas:
        sys.exit("ERRO: o roteiro nao tem a lista 'cenas'.")

    # Mostra QUAL roteiro sera lido (evita usar arquivo antigo sem perceber)
    titulo = roteiro.get("titulo_otimizado") or "(sem titulo)"
    data = time.strftime("%d/%m/%Y %H:%M", time.localtime(ARQUIVO_ROTEIRO.stat().st_mtime))
    print(f'[OK] Roteiro lido: "{titulo}"')
    print(f"     arquivo salvo em {data} | {len(cenas)} cena(s)")

    PASTA_AUDIO.mkdir(exist_ok=True)
    print(f"Voz: {VOZ} | Taxa: {TAXA}\n")

    ok = 0
    puladas = 0
    for i, cena in enumerate(cenas):
        if not isinstance(cena, dict):
            continue
        numero = cena.get("numero", i + 1)
        texto = (cena.get("narracao") or "").strip()
        destino = PASTA_AUDIO / f"cena{numero}.mp3"

        if not texto:
            puladas += 1
            print(f"  -> Cena {numero}: sem narracao, pulando")
            continue

        print(f"  -> Cena {numero}: gerando ...", end="", flush=True)
        if gerar_narracao(texto, destino):
            ok += 1
            d = duracao_do_audio(destino)
            extra = f" ({d:.1f}s)" if d else ""
            print(f" ok{extra}")
        else:
            print(" falhou")

    print("-" * 58)
    print(f" PRONTO! {ok} audio(s) gerados em: {PASTA_AUDIO}")
    if puladas:
        print(f" ({puladas} cena(s) sem texto de narracao foram puladas)")
    print(" Proximo passo:  python render_video.py")
    print("-" * 58)


if __name__ == "__main__":
    principal()
