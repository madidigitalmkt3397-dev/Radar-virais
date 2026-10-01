# -*- coding: utf-8 -*-
"""
===========================================================
 FASE 4 + 7 - Narracao (Edge-TTS) + tratamento de voz
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

 FASE 7 - Tratamento automatico (constantess logo abaixo):
   - Corta pausas mortas (jump cuts)
   - Aceleracao 1.1x SEM mudar o tom (FFmpeg atempo)
   - EQ anti-robob: corte de grave + ganho nos agudos
   (tudo gratis: usa o FFmpeg que ja vem com o MoviePy)
===========================================================
"""

import asyncio
import json
import shutil
import subprocess
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

# ---------- FASE 7 - Tratamento de voz (edite para ligar/desligar) ----------
CORRIGIR_SILENCIO = True   # True = corta pausas mortas (jump cuts)
SILENCIO_MAX = 0.40        # pausa MAIOR que isso (s) encolhe para SILENCIO_QUIZ
SILENCIO_QUIZ = 0.15       # quanto da pausa morta e mantido (s)
LIMIAR_SILENCIO = 0.01     # volume abaixo disso conta como silencio (0.0 a 1.0)

VELOCIDADE = 1.1           # 1.0 = normal | 1.1 = voz 10% mais rapida (tom igual)

EQ_VOZ = True              # True = EQ anti-robob (voz mais "cristalina")
CORTE_GRAVE = 90           # Hz: corta grave morto abaixo disso
GANHO_PRESENCA = 3         # dB: ganho na presenca da voz (~2500 Hz)
GANHO_BRILHO = 2           # dB: ganho nos agudos (acima de 4000 Hz)


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


# ---------- FASE 7 - Engenharia de som ----------

def achar_ffmpeg():
    """Procura o FFmpeg que ja vem instalado junto com o MoviePy."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _carregar_audio(caminho: Path):
    """Le um arquivo de audio e devolve (matriz numpy, fps)."""
    from moviepy import AudioFileClip
    clip = AudioFileClip(str(caminho))
    try:
        fps = int(clip.fps or 44100)
        arr = clip.to_soundarray(fps=fps)
    finally:
        clip.close()
    return arr, fps


def _cortar_pausas(arr, fps):
    """
    Jump cuts de audio (numpy):
      - silencio do comeco/fim: quase todo cortado
      - pausa morta interna maior que SILENCIO_MAX: encolhe para SILENCIO_QUIZ
    Devolve a matriz cortada (None se nao ha nada a cortar).
    """
    import numpy as np

    mono = arr.mean(axis=1) if arr.ndim > 1 else arr
    n = len(mono)
    janela = max(1, int(fps * 0.02))  # mede o volume de 20 em 20 ms
    n_jan = n // janela
    if n_jan < 10:
        return None

    rms = np.sqrt(np.mean(
        mono[: n_jan * janela].astype("float64").reshape(n_jan, janela) ** 2,
        axis=1,
    ))
    silencio = rms < LIMIAR_SILENCIO
    if silencio.all() or not silencio.any():
        return None

    mascara = np.repeat(silencio, janela)
    if len(mascara) < n:
        mascara = np.concatenate([mascara, np.zeros(n - len(mascara), dtype=bool)])

    # Regioes de silencio (inicio/fim exclusivos de cada bloco)
    bordas = np.concatenate(([False], mascara, [False]))
    diffs = np.diff(bordas.astype("int8"))
    inicios = np.flatnonzero(diffs == 1)
    fins = np.flatnonzero(diffs == -1)

    manter = np.ones(n, dtype=bool)
    for k in range(len(inicios)):
        s, e = int(inicios[k]), int(fins[k])
        if s == 0:  # silencio do comeco: deixa so 0,05s de respiro
            corte = e - int(0.05 * fps)
            if corte > s:
                manter[s:corte] = False
        elif e >= n:  # silencio do fim: deixa so 0,10s de respiro
            ini = s + int(0.10 * fps)
            if ini < e:
                manter[ini:e] = False
        elif (e - s) / fps > SILENCIO_MAX:  # pausa morta interna
            ini = s + int(SILENCIO_QUIZ * fps)
            if ini < e:
                manter[ini:e] = False

    novo = arr[manter]
    if len(novo) < int(0.5 * fps):  # salvaguarda: nunca encurta demais
        return None
    return novo


def _salvar_wav(arr, caminho: Path, fps: int):
    """Grava .wav 16 bits (entrada temporaria do FFmpeg)."""
    import wave
    import numpy as np
    dados = arr if arr.ndim > 1 else arr.reshape(-1, 1)
    pcm = (np.clip(dados, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(int(pcm.shape[1]))
        w.setsampwidth(2)
        w.setframerate(int(fps))
        w.writeframes(pcm.tobytes())


def _montar_filtros():
    """Lista de filtros FFmpeg: velocidade (tom preservado) + EQ da voz."""
    filtros = []
    if abs(VELOCIDADE - 1.0) > 1e-6:
        filtros.append(f"atempo={VELOCIDADE:g}")  # muda a velocidade, NAO o tom
    if EQ_VOZ:
        filtros.append(f"highpass=f={CORTE_GRAVE}")
        filtros.append(f"equalizer=f=2500:t=q:w=1.2:g={GANHO_PRESENCA}")
        filtros.append(f"treble=g={GANHO_BRILHO}:f=4000")
    return filtros


def processar_audio(bruto: Path, final: Path):
    """
    Fase 7: corta pausas -> acelera sem mudar o tom -> EQ.
    Sempre deixa `final` existindo (se algo falhar, usa o audio bruto).
    Devolve (resumo_para_console, lista_de_avisos).
    Ex. de resumo: " [corte + 1.1x + EQ: 8.4s -> 7.1s]"
    """
    avisos = []
    ativos = []
    temporarios = []
    entrada = bruto
    sucesso = False

    # Sem moviepy/numpy nao da para tratar - salva o bruto e segue
    try:
        import numpy  # noqa: F401
        from moviepy import AudioFileClip  # noqa: F401
    except ImportError:
        shutil.copyfile(bruto, final)
        bruto.unlink(missing_ok=True)
        return "", avisos

    d0 = duracao_do_audio(bruto)

    # 1) Cortar pausas mortas (numpy) -> vira .wav temporario
    if CORRIGIR_SILENCIO:
        try:
            arr, fps = _carregar_audio(bruto)
            cortado = _cortar_pausas(arr, fps)
            if cortado is not None and len(cortado) != len(arr):
                tmp = bruto.with_name(bruto.stem + "_corte.wav")
                _salvar_wav(cortado, tmp, fps)
                temporarios.append(tmp)
                entrada = tmp
                ativos.append("corte")
        except Exception as e:
            avisos.append(f"corte de pausas pulado nesta cena ({type(e).__name__})")

    # 2) FFmpeg: aceleracao + EQ -> audio final
    filtros = _montar_filtros()
    ffmpeg = achar_ffmpeg()
    if (not filtros) and entrada is bruto:
        # Nada para tratar - so reaproveita o bruto
        shutil.copyfile(bruto, final)
        sucesso = True
    elif ffmpeg:
        cmd = [ffmpeg, "-y", "-i", str(entrada)]
        if filtros:
            cmd += ["-af", ",".join(filtros)]
        cmd += ["-b:a", "192k", str(final)]
        r = subprocess.run(cmd, capture_output=True)
        sucesso = r.returncode == 0 and final.exists() and final.stat().st_size > 0
        if not sucesso:
            linhas = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            avisos.append(f"ffmpeg: {linhas[-1][:110] if linhas else 'erro desconhecido'}")
    else:
        avisos.append("FFmpeg nao encontrado")

    # 3) Nunca deixa a cena sem audio: se falhou, usa o bruto
    if not sucesso:
        shutil.copyfile(bruto, final)
        ativos = []

    if abs(VELOCIDADE - 1.0) > 1e-6:
        ativos.append(f"{VELOCIDADE:g}x")
    if EQ_VOZ:
        ativos.append("EQ")

    for t in temporarios:
        t.unlink(missing_ok=True)
    bruto.unlink(missing_ok=True)

    # Resumo para o console
    d1 = duracao_do_audio(final) if final.exists() else None
    if sucesso and ativos and d0 and d1:
        return f" [{' + '.join(ativos)}: {d0:.1f}s -> {d1:.1f}s]", avisos
    if d1:
        return f" ({d1:.1f}s)", avisos
    return "", avisos


def principal():
    print("=" * 58)
    print(" FASE 4 + 7 - Narracao + tratamento de voz (gratuito)")
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
        bruto = PASTA_AUDIO / f"cena{numero}_raw.mp3"
        if gerar_narracao(texto, bruto):
            ok += 1
            detalhe, avisos = processar_audio(bruto, destino)
            print(f" ok{detalhe}")
            for aviso in avisos:
                print(f"        [!] {aviso}")
        else:
            print(" falhou")

    print("-" * 58)
    print(f" PRONTO! {ok} audio(s) gerados em: {PASTA_AUDIO}")
    if puladas:
        print(f" ({puladas} cena(s) sem texto de narracao foram puladas)")
    if CORRIGIR_SILENCIO or abs(VELOCIDADE - 1.0) > 1e-6 or EQ_VOZ:
        print(" Fase 7 aplicada: pausas cortadas + voz acelerada + EQ")
        print(" (edite as constantes FASE 7 no comeco deste script)")
    print(" Proximo passo:  python render_video.py")
    print("-" * 58)


if __name__ == "__main__":
    principal()
