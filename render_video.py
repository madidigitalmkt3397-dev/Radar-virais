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
   - Se a narracao for maior que o video, estica em slow-motion
     (ou congela - veja a chave COMO_ESTICAR abaixo)
   - Cenas sem audio ficam em silencio (sem quebrar o render)
   - Normaliza o volume final: -14 LUFS / -1 dB (padrao YouTube)
   - Fase 9: corrige cor, nitidez, zoom Ken Burns e fades
   - Fase 8: efeitos sonoros - whoosh automatico na virada de cada
     cena + o efeito_sonoro_sugerido do roteiro (arquivo de
     banco_efeitos/ ou sintetizado na hora - tudo gratis)

 Para ligar/desligar: chaves SFX_* no topo do script.
 Efeitos com arquivo (risadas, aplausos...): baixe gratis, salve em
 banco_efeitos/ com o nome da sugestao e rode de novo (ver README).
===========================================================
"""

import json
import re
import shutil
import subprocess
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
PASTA_SFX = BASE / "banco_efeitos"

EXTENSOES_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".webp"}
EXTENSOES_AUDIO = {".mp3", ".wav"}
EXTENSOES_SFX = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}

TEMPO_IMAGEM_SEGUNDOS = 3.0  # duracao de cada imagem fixa (sem narracao)
FPS_PADRAO = 30
NOME_SAIDA = "video_final.mp4"

# Quando a narracao e MAIOR que o clipe, o que fazer com o excesso:
#   "lento"    -> video continua em MOVIMENTO, so que mais devagar (recomendado)
#   "congelar" -> ultimo quadro parado ate a fala acabar (efeito "travado")
COMO_ESTICAR = "lento"

# Fase 7 - Normaliza o volume do video final no padrao das redes sociais
# (-14 LUFS com teto de -1 dB = YouTube, TikTok e Instagram nunca cortam o som)
NORMALIZAR = True

# ---------- FASE 8 - Efeitos sonoros ----------
SFX_LIGADO = True            # liga/desliga todos os efeitos sonoros
SFX_TRANSICAO = True         # whoosh automatico na virada de cada cena
SFX_POR_CENA = True          # usa o efeito_sonoro_sugerido do roteiro
SFX_VOLUME = 0.6             # volume dos efeitos (0.0 a 1.0)
SFX_VOLUME_TRANSICAO = 0.5   # volume do whoosh das trocas

# ---------- FASE 9 - Imagem viva (edite para ligar/desligar) ----------
ZOOM_DINAMICO = True      # Ken Burns: zoom sutil em cada cena
ESCALA_ZOOM = 1.12        # ate onde o zoom vai (1.12 = +12%; nunca < 1.0)
CORRECAO_COR = True        # contraste + brilho + saturacao
SATURACAO = 1.25          # 1.0 = sem mudanca | 1.25 = +25% de cor
CONTRASTE = 1.12          # 1.0 = sem mudanca
BRILHO = 1.02             # 1.0 = sem mudanca
NITIDEZ = 0.9             # 0 = desligado | 0.9 = recomendado
FADE_ENTRADA = 0.4        # segundos surgindo do preto (0 = desligado)
FADE_SAIDA = 0.5          # segundos terminando no preto

# Efeitos extras - PADRAO DESLIGADO (podem estragar clips com texto!)
PRETO_E_BRANCO = False    # video inteiro em preto e branco
FLASH_NA_TROCA = False    # flash branco na troca de cena
FLASH_DURACAO = 0.15      # duracao do flash (s)
FLASH_FORCA = 0.75        # 0.0 a 1.0 (1.0 = tela branca total)
ESPELHAR_CLIPES = False   # espelha clipes (cuidado: vira o texto de lado)
INVERTER_CORES = False    # inverte as cores (efeito psicodelico)


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


def achar_ffmpeg():
    """Procura o FFmpeg que ja vem instalado junto com o MoviePy."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def normalizar_volume(caminho: Path) -> bool:
    """
    Fase 7 - Passa final de volume: -14 LUFS com teto em -1 dB.
    E o padrao do YouTube/TikTok (nem baixo demais, nem estourando).
    So o audio e ajustado - o video e copiado como esta (rapido).
    """
    ffmpeg = achar_ffmpeg()
    if not ffmpeg:
        print("[!] FFmpeg nao encontrado - volume fica como estava")
        return False

    temporario = caminho.with_name("_volume_tmp.mp4")
    try:
        saida = subprocess.run(
            [
                ffmpeg, "-y", "-i", str(caminho),
                "-af", "loudnorm=I=-14:TP=-1:LRA=11",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                str(temporario),
            ],
            capture_output=True,
        )
        ok = (
            saida.returncode == 0
            and temporario.exists()
            and temporario.stat().st_size > 0
        )
        if ok:
            temporario.replace(caminho)
            return True
        linhas = (saida.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        print(f"[!] Normalizacao falhou: {linhas[-1][:110] if linhas else 'erro desconhecido'}")
        return False
    finally:
        if temporario.exists():
            try:
                temporario.unlink()
            except OSError:
                pass


def _desfoque_3x3(img):
    """Desfoque gaussiano 3x3 em numpy puro (sem OpenCV/scipy)."""
    import numpy as np
    h, w = img.shape[:2]
    p = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    acc = np.zeros_like(img)
    pesos = ((1, 2, 1), (2, 4, 2), (1, 2, 1))
    for i, linha in enumerate(pesos):
        for j, peso in enumerate(linha):
            acc += peso * p[i:i + h, j:j + w]
    return acc / 16.0


def _zoom_central(img, escala):
    """
    Amplia o quadro em torno do centro (bilinear) mantendo o tamanho original.
    escala >= 1.0 sempre - por isso NUNCA aparece borda preta.
    FEITO EM NUMPY DE PROPOSITO: o resized() do MoviePy 2 trunca quadros
    float para uint8 (bug) e deixaria o video todo preto.
    """
    import numpy as np
    h, w = img.shape[:2]
    yy = (np.arange(h, dtype="float64") + 0.5 - h / 2) / escala + h / 2 - 0.5
    xx = (np.arange(w, dtype="float64") + 0.5 - w / 2) / escala + w / 2 - 0.5
    yy = np.clip(yy, 0, h - 1)
    xx = np.clip(xx, 0, w - 1)

    y0 = yy.astype(np.intp)
    x0 = xx.astype(np.intp)
    y1 = np.minimum(y0 + 1, h - 1)
    x1 = np.minimum(x0 + 1, w - 1)
    wy = (yy - y0).astype("float32")[:, None, None]
    wx = (xx - x0).astype("float32")[None, :, None]

    c00 = img[y0][:, x0]
    c01 = img[y0][:, x1]
    c10 = img[y1][:, x0]
    c11 = img[y1][:, x1]
    topo = c00 + (c01 - c00) * wx
    baixo = c10 + (c11 - c10) * wx
    return topo + (baixo - topo) * wy


def _montar_transform(espelhar: bool, flash: bool, zoom):
    """
    Funcao de quadro da Fase 9 (roda em TODOS os frames):
      - zoom Ken Burns (zoom = (inicio, fim, duracao) ou None)
      - efeitos opcionais: espelhar, preto e branco, inverter cores
      - correcao de cor: contraste + brilho + saturacao (+15%)
      - nitidez (unsharp mask)
      - flash branco no inicio da cena (se FLASH_NA_TROCA ligado)
    """
    import numpy as np

    def processar(gf, t):
        frame = gf(t)
        if frame.ndim != 3 or frame.shape[2] not in (3, 4):
            return frame

        eh_uint8 = frame.dtype == np.uint8
        rgb = frame[..., :3].astype("float32")
        alpha = frame[..., 3:4] if frame.shape[2] == 4 else None
        # Normaliza para 0..1: uint8 vem 0..255; no MoviePy 2 ate float vem
        # 0..255; float com max <= 1 e a convencao antiga (0..1)
        origem_255 = eh_uint8 or (rgb.size > 0 and float(rgb.max()) > 1.0)
        if origem_255:
            rgb /= 255.0

        if ESPELHAR_CLIPES and espelhar:
            rgb = rgb[:, ::-1]
            if alpha is not None:
                alpha = alpha[:, ::-1]

        # Ken Burns: escala sempre >= 1.0 (amplia, nunca reduz)
        if zoom is not None:
            inicio, fim, dur = zoom
            if dur > 0:
                frac = min(max(float(t), 0.0) / dur, 1.0)
                escala = inicio + (fim - inicio) * frac
                if escala > 1.0:
                    rgb = _zoom_central(rgb, escala)
                    if alpha is not None:
                        alpha = _zoom_central(alpha, escala)

        if PRETO_E_BRANCO:
            lum = (rgb * np.array([0.299, 0.587, 0.114], "float32")).sum(axis=2)
            rgb = np.repeat(lum[..., None], 3, axis=2)
        if INVERTER_CORES:
            rgb = 1.0 - rgb

        if CORRECAO_COR:
            # contraste em volta do cinza medio + brilho
            rgb = (rgb - 0.5) * CONTRASTE + 0.5 + (BRILHO - 1.0)
            # saturacao: mantem a luminancia e espalha as cores
            lum = (rgb * np.array([0.299, 0.587, 0.114], "float32")).sum(axis=2)[..., None]
            rgb = np.clip(lum + (rgb - lum) * SATURACAO, 0.0, 1.0)

        if NITIDEZ > 0:
            rgb = np.clip(rgb + NITIDEZ * (rgb - _desfoque_3x3(rgb)), 0.0, 1.0)

        if flash:
            instante = float(t)
            if 0 <= instante < FLASH_DURACAO:
                fator = FLASH_FORCA * (1.0 - instante / FLASH_DURACAO)
                rgb = rgb * (1.0 - fator) + fator  # mistura com o branco

        # Devolve no MESMO formato de entrada (writer do MoviePy quer 0..255)
        if eh_uint8:
            rgb = np.clip(rgb * 255.0, 0, 255).astype("uint8")
        elif origem_255:
            rgb = np.clip(rgb * 255.0, 0, 255)
        else:
            rgb = np.clip(rgb, 0.0, 1.0).astype("float32", copy=False)

        if alpha is None:
            return rgb
        return np.concatenate([rgb, alpha], axis=2)

    return processar


def tratar_imagem(clip, numero, primeira, ultima):
    """
    Fase 9 - da vida aos clipes:
      1. processamento por quadro: zoom Ken Burns (sempre >= 100% - sem
         borda preta), correcao de cor, nitidez e efeitos opcionais
      2. fades: so a 1a cena surge do preto e a ultima termina no preto
        (nas trocas do meio fica corte seco - pisca preto se fosse em tudo)
    """
    from moviepy import vfx

    espelhar = (numero % 2 == 0)  # variacao visual se ESPELHAR_CLIPES ligado
    flash = FLASH_NA_TROCA and not primeira

    # Ken Burns: cenas impares aproximam, pares afastam (variedade visual)
    zoom = None
    if ZOOM_DINAMICO and ESCALA_ZOOM > 1.0 and clip.duration and clip.duration > 0:
        if numero % 2 == 0:
            zoom = (ESCALA_ZOOM, 1.0, clip.duration)
        else:
            zoom = (1.0, ESCALA_ZOOM, clip.duration)

    clip = clip.transform(_montar_transform(espelhar, flash, zoom))

    efeitos = []
    if primeira and FADE_ENTRADA > 0:
        efeitos.append(vfx.FadeIn(FADE_ENTRADA))
    if ultima and FADE_SAIDA > 0:
        efeitos.append(vfx.FadeOut(FADE_SAIDA))
    if efeitos:
        clip = clip.with_effects(efeitos)
    return clip


# ================ FASE 8 - Efeitos sonoros ================
# Quem sintetiza aqui mesmo (custo zero, numpy puro) e quem precisa
# de arquivo em banco_efeitos/:
TIPOS_SINTETIZAVEIS = {
    "whoosh": ("whoosh", "swoosh"),
    "suspense": ("suspense", "suspenso", "tensao"),
    "heartbeat": ("heartbeat", "batimento", "coracao"),
    "ding": ("ding", "sino"),
    "impacto": ("impacto", "impact", "boom", "batida"),
}
FS_SFX = 44100
SFX_TRANSICAO_NOMES = ("swoosh", "transicao", "transition")
SFX_ANTES_DO_CORTE = 0.25  # whoosh comeca antes do corte p/ bater nele


def _normalizar_texto(txt):
    """Minusculas e sem acento (sugestoes vem em ingles ou pt-BR)."""
    import unicodedata
    txt = str(txt or "").lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", txt)
        if unicodedata.category(c) != "Mn"
    )


def _estereo(mono):
    import numpy as np
    return np.repeat(np.asarray(mono, "float32")[:, None], 2, axis=1)


def _com_pico(som, pico):
    import numpy as np
    maximo = float(np.abs(som).max())
    if maximo < 1e-9:
        return som
    return som * (pico / maximo)


def _whoosh_filtrado(ruido, f):
    """
    Uma camada do whoosh: ruido -> banda ressonante que varre (SVF)
    + corpo grave. Sem ruido branco "solto" = nao vira chiado.
    """
    import numpy as np
    n = len(ruido)
    # 2 estagios em cascata: bordas mais fechadas (a banda de verdade
    # varre; sobra pouco ruido solto = sem chiado)
    entrada = ruido
    for _ in range(2):
        low1 = b1 = low2 = b2 = 0.0
        etapa = np.empty(n, "float64")
        for i in range(n):
            fi = f[i]
            # corpo da banda (resonancia moderada)
            high1 = entrada[i] - low1 - 0.62 * b1
            b1 += fi * high1
            low1 += fi * b1
            # foco tonal (resonancia alta = "shh" com tom, nao "tss")
            high2 = entrada[i] - low2 - 0.30 * b2
            b2 += fi * high2
            low2 += fi * b2
            etapa[i] = b1 * 0.85 + b2 * 0.50
        entrada = etapa
    banda = etapa
    # corpo grave acompanha a varredura (o "peso" do whoosh)
    f_corpo = 1.0 - np.exp(-2.0 * np.pi * (f / 6.0) / FS_SFX)
    y = 0.0
    corpo = np.empty(n, "float64")
    for i in range(n):
        y += f_corpo[i] * (ruido[i] - y)
        corpo[i] = y
    return banda * 2.4 + corpo * 1.15


def _synth_whoosh(dur=0.55):
    """
    Whoosh de transicao profissional (3 camadas, zero chiado):
      1. banda ressonante que SOBE e DESCE (o corpo do whoosh)
      2. corpo grave acompanhando a varredura (peso)
      3. tom doppler sutil + corte agudo acima de 7.5kHz
    Envoltoria assimetrica: pico antes do corte, cai devagar.
    """
    import numpy as np
    n = int(dur * FS_SFX)
    t = np.arange(n) / FS_SFX
    u = t / dur

    # varredura: banda sobe ate o meio do whoosh e desce
    fc = 170.0 + 2000.0 * np.sin(np.pi * u ** 0.75) ** 1.4
    f = 2.0 * np.sin(np.pi * np.clip(fc, 20.0, FS_SFX * 0.45) / FS_SFX)

    # estereo real (sementes diferentes = largura profissional)
    canais = [
        _whoosh_filtrado(np.random.default_rng(s).standard_normal(n), f * d)
        for s, d in ((101, 1.0), (202, 1.07))
    ]
    estereo = np.stack(canais, axis=1)

    # tom doppler sutil (foco tonal - whoosh de verdade nao e so ruido)
    f_tom = 300.0 + 750.0 * np.sin(np.pi * u ** 1.1)
    estereo += (np.sin(2 * np.pi * np.cumsum(f_tom) / FS_SFX) * 0.14)[:, None]

    # corta o agudo que vira "chiado" (ruido branco agudo = amador)
    espectro = np.fft.rfft(estereo, axis=0)
    espectro[np.fft.rfftfreq(n, 1.0 / FS_SFX) > 7500.0] *= 0.15
    estereo = np.fft.irfft(espectro, n, axis=0)

    # envoltoria: sobe rapido (pico em 35% = antes do corte)...
    ta = 0.35 * dur
    env = np.where(
        t < ta,
        0.5 - 0.5 * np.cos(np.pi * np.clip(t / ta, 0, 1) ** 1.3),
        np.exp(-((t - ta) / max(dur - ta, 1e-6)) * 2.6),
    )
    env *= np.clip((dur - t) / 0.08, 0.0, 1.0)   # termina em zero (sem estalo)
    estereo *= env[:, None]

    # saturacao suave (densidade + volume sem estourar o pico)
    topo = float(np.abs(estereo).max())
    if topo > 1e-9:
        estereo = estereo / topo
        estereo = np.tanh(estereo * 2.0) / np.tanh(2.0)

    return _com_pico(estereo.astype("float32"), 0.85)


def _synth_ding():
    """Campainha de acerto - 3 tons com caida exponencial."""
    import numpy as np
    n = int(1.3 * FS_SFX)
    t = np.arange(n) / FS_SFX
    som = (np.sin(2 * np.pi * 880.0 * t) * 0.60
           + np.sin(2 * np.pi * 1318.5 * t) * 0.40
           + np.sin(2 * np.pi * 2637.0 * t) * 0.15 * np.exp(-t * 8.0))
    som *= np.exp(-t * 3.0) * np.minimum(t / 0.004, 1.0)
    return _estereo(_com_pico(som, 0.80))


def _synth_impacto():
    """Boom - batida grave que desce de 100Hz para 40Hz + clique."""
    import numpy as np
    n = int(0.7 * FS_SFX)
    t = np.arange(n) / FS_SFX
    f = 40.0 + 60.0 * np.exp(-t * 4.0)
    fase = 2.0 * np.pi * np.cumsum(f) / FS_SFX
    som = np.sin(fase) * np.exp(-t * 5.0)
    clique = np.zeros(n)
    n_cli = int(0.012 * FS_SFX)
    rng = np.random.default_rng(5)
    clique[:n_cli] = rng.standard_normal(n_cli) * np.exp(
        -np.arange(n_cli) / (0.003 * FS_SFX)
    )
    som = som * 0.9 + clique * 0.35
    return _estereo(_com_pico(som, 0.90))


def _synth_heartbeat(dur_cena):
    """Lub-dub grave repetindo - tensao de coracao acelerado."""
    import numpy as np
    dur = float(min(max(dur_cena, 2.0), 7.0))
    n = int(dur * FS_SFX)
    saida = np.zeros(n, "float32")

    def batida(pos, forca):
        i0 = int(pos * FS_SFX)
        larg = int(0.18 * FS_SFX)
        if i0 + larg >= n:
            return
        tt = np.arange(larg) / FS_SFX
        pacote = (np.sin(2 * np.pi * 65.0 * tt)
                  + 0.45 * np.sin(2 * np.pi * 130.0 * tt))
        pacote *= np.exp(-((tt - 0.05) / 0.05) ** 2) * forca
        saida[i0:i0 + larg] += pacote

    pos = 0.12
    while pos + 0.45 < dur:
        batida(pos, 1.0)               # lub
        batida(pos + 0.20, 0.62)       # dub
        pos += 0.95                    # ~63 bpm
    return _estereo(_com_pico(saida, 0.70))


def _synth_suspense(dur_cena):
    """Drone grave que respira - cama de tensao (fica ABAIXO da voz)."""
    import numpy as np
    dur = float(min(max(dur_cena, 1.5), 6.0))
    n = int(dur * FS_SFX)
    t = np.arange(n) / FS_SFX
    drone = ((np.sin(2 * np.pi * 55.0 * t) + np.sin(2 * np.pi * 55.5 * t)) * 0.5
             + np.sin(2 * np.pi * 82.5 * t) * 0.35)
    respira = 0.55 + 0.45 * np.sin(2 * np.pi * 0.5 * t - np.pi / 2)
    rng = np.random.default_rng(7)
    kernel = np.ones(96) / 96.0        # ruido suave = textura de vento
    tex = np.convolve(rng.standard_normal(n), kernel, mode="same")
    tex = tex / max(float(np.abs(tex).max()), 1e-9)
    som = drone * respira + tex * 0.30
    fade = int(min(0.35, dur / 3) * FS_SFX)
    som[:fade] *= np.linspace(0.0, 1.0, fade) ** 1.5
    som[-fade:] *= np.linspace(1.0, 0.0, fade) ** 1.5
    return _estereo(_com_pico(som, 0.35))


def _sintetizar(tipo, duracao_cena):
    """Gera o efeito em memoria. None = nao da para sintetizar."""
    if tipo == "whoosh":
        return _synth_whoosh()
    if tipo == "ding":
        return _synth_ding()
    if tipo == "impacto":
        return _synth_impacto()
    if tipo == "heartbeat":
        return _synth_heartbeat(duracao_cena)
    if tipo == "suspense":
        return _synth_suspense(duracao_cena)
    return None


def _tipo_efeito(sugerido_norm):
    """whoosh/suspense/heartbeat/ding/impacto, ou None (ex.: aplausos)."""
    for tipo, chaves in TIPOS_SINTETIZAVEIS.items():
        if any(chave in sugerido_norm for chave in chaves):
            return tipo
    return None


def _achar_sfx(termo_norm, exceto=()):
    """Procura em banco_efeitos/ um arquivo que case com a sugestao."""
    if not PASTA_SFX.exists() or not termo_norm:
        return None
    arquivos = [
        a for a in sorted(PASTA_SFX.iterdir())
        if a.suffix.lower() in EXTENSOES_SFX
        and _normalizar_texto(a.stem) not in exceto
    ]
    # 1) nome do arquivo aparece na sugestao (ou vice-versa)
    for a in arquivos:
        nome = _normalizar_texto(a.stem)
        if nome in termo_norm or termo_norm in nome:
            return a
    # 2) alguma palavra (>= 4 letras) em comum
    for a in arquivos:
        palavras = [p for p in re.split(r"[\s_\-]+", _normalizar_texto(a.stem))
                    if len(p) >= 4]
        if any(p in termo_norm for p in palavras):
            return a
    return None


def _achar_transicao():
    """swoosh.wav / transicao.wav no banco_efeitos/ (opcional)."""
    if not PASTA_SFX.exists():
        return None
    for a in sorted(PASTA_SFX.iterdir()):
        if (a.suffix.lower() in EXTENSOES_SFX
                and _normalizar_texto(a.stem) in SFX_TRANSICAO_NOMES):
            return a
    return None


def _criar_clip_sfx(caminho=None, tipo=None, duracao_cena=0.0, volume=None):
    """Monta o clipe do efeito (arquivo do banco ou sintetizado)."""
    from moviepy import AudioArrayClip, AudioFileClip, afx
    if caminho is not None:
        clipe = AudioFileClip(str(caminho))
    else:
        som = _sintetizar(tipo, duracao_cena)
        if som is None:
            return None
        clipe = AudioArrayClip(som, FS_SFX)
    return clipe.with_effects([
        afx.MultiplyVolume(volume if volume is not None else SFX_VOLUME),
        afx.AudioFadeIn(0.02),
        afx.AudioFadeOut(0.08),
    ])


def _encaixar(faixas, clipe, onde, dur_total):
    """Posiciona o efeito no tempo; corta se passar do fim do video."""
    restante = dur_total - onde
    if restante <= 0.05:
        return False
    if clipe.duration > restante:
        clipe = clipe.subclipped(0, restante)
    faixas.append(clipe.with_start(onde))
    return True


def _sugestao_do_roteiro(roteiro, numero):
    if not roteiro or not isinstance(roteiro.get("cenas"), list):
        return ""
    for cena in roteiro["cenas"]:
        if isinstance(cena, dict) and cena.get("numero") == numero:
            return cena.get("efeito_sonoro_sugerido") or ""
    return ""


def juntar_efeitos_sonicos(final, cenas_info, audios):
    """
    Fase 8 - mistura os efeitos sonoros no video final:
      - whoosh na virada de cada cena (automatico, comeca antes do corte)
      - efeito_sonoro_sugerido de cada cena (arquivo do banco_efeitos/
        ou sintetizado na hora)
    `audios` recebe os arquivos abertos (o finally do principal fecha).
    """
    from moviepy import CompositeAudioClip

    dur_total = final.duration
    faixas = []
    sintetizados = 0
    do_banco = 0
    faltando = []

    for i, info in enumerate(cenas_info):
        inicio = float(info["inicio"])
        dur_cena = float(info["duracao"])
        sugerido_norm = _normalizar_texto(info["sugerido"])
        tipo = _tipo_efeito(sugerido_norm) if sugerido_norm else None
        e_whoosh = tipo == "whoosh" or "whoosh" in sugerido_norm \
            or "swoosh" in sugerido_norm

        # --- 1) efeito sugerido no roteiro ---
        clip_efeito = None
        if SFX_POR_CENA and sugerido_norm:
            arquivo = _achar_sfx(sugerido_norm, exceto=SFX_TRANSICAO_NOMES)
            if arquivo is not None:
                clip_efeito = _criar_clip_sfx(caminho=arquivo)
                if clip_efeito is not None:
                    audios.append(clip_efeito)
                    do_banco += 1
            elif tipo is not None:
                clip_efeito = _criar_clip_sfx(
                    tipo=tipo, duracao_cena=dur_cena
                )
                sintetizados += 1
            else:
                faltando.append(str(info["sugerido"]).strip())
            if clip_efeito is not None:
                onde = inicio
                if e_whoosh and i > 0:
                    # o proprio whoosh da cena faz o papel de transicao
                    onde = max(0.0, inicio - SFX_ANTES_DO_CORTE)
                _encaixar(faixas, clip_efeito, onde, dur_total)

        # --- 2) whoosh da transicao (se a cena nao ja e whoosh) ---
        if SFX_TRANSICAO and i > 0 and not e_whoosh:
            arquivo_t = _achar_transicao()
            if arquivo_t is not None:
                clipe = _criar_clip_sfx(
                    caminho=arquivo_t, volume=SFX_VOLUME_TRANSICAO
                )
                if clipe is not None:
                    audios.append(clipe)
                    do_banco += 1
            else:
                clipe = _criar_clip_sfx(
                    tipo="whoosh", volume=SFX_VOLUME_TRANSICAO
                )
                sintetizados += 1
            if clipe is not None:
                _encaixar(
                    faixas, clipe,
                    max(0.0, inicio - SFX_ANTES_DO_CORTE), dur_total,
                )

    if not faixas:
        print("[sfx] nenhum efeito sonoro para adicionar")
        return final

    base = [final.audio] if final.audio is not None else []
    mistura = CompositeAudioClip(base + faixas)
    # MoviePy 2: CompositeAudioClip nasce com duration None - obriga explicito
    mistura = mistura.with_duration(dur_total)
    final = final.with_audio(mistura)
    print(f"[OK] Efeitos sonoros: {sintetizados} sintetizado(s) "
          f"+ {do_banco} do banco_efeitos/")
    if faltando:
        print("     sem arquivo (baixe gratis e salve em banco_efeitos/): "
              + ", ".join(faltando))
    return final


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
    cenas_info = []      # Fase 8: inicio/duracao/sugestao de cada cena
    inicio_cena = 0.0
    try:
        for indice, (ordem, arq) in enumerate(cenas):
            ext = arq.suffix.lower()
            is_imagem = ext in EXTENSOES_IMAGEM
            print(f"  -> Cena {ordem}: {arq.name} ...", end="", flush=True)

            if is_imagem:
                clip = ImageClip(str(arq)).with_duration(TEMPO_IMAGEM_SEGUNDOS)
            else:
                clip = VideoFileClip(str(arq))

            narracao = localizar_narracao(ordem)
            audio = None
            if narracao:
                clip, audio = aplicar_narracao(
                    clip, narracao, is_imagem, AudioFileClip, ImageClip, concatenate_videoclips
                )
                audios.append(audio)
                com_narracao += 1
                print(f" ok ({clip.duration:.1f}s) [narrado: {narracao.name}]")
            else:
                print(f" ok ({clip.duration:.1f}s)")

            # Fase 9 - cor, nitidez, zoom Ken Burns e fades
            clip = tratar_imagem(
                clip, ordem,
                primeira=(indice == 0),
                ultima=(indice == len(cenas) - 1),
            )
            if audio is not None and clip.audio is None:
                clip = clip.with_audio(audio)  # salvaguarda: efeitos nunca perdem a voz

            clips.append(clip)
            cenas_info.append({
                "numero": ordem,
                "inicio": inicio_cena,
                "duracao": clip.duration or 0.0,
                "sugerido": _sugestao_do_roteiro(roteiro, ordem),
            })
            inicio_cena += clip.duration or 0.0

        print(f"[OK] Narração em {com_narracao}/{len(cenas)} cena(s)")
        if com_narracao < len(cenas):
            print("     (cenas sem audio ficam em silencio - rode gerar_narracao.py para todas)")

        # 5. Junta tudo (cenas com audio + cenas sem = CompositeAudioClip, sem erro)
        print("[...] Juntando as cenas...")
        final = concatenate_videoclips(clips, method="compose")

        # Fase 8 - whoosh nas trocas + efeito sugerido no roteiro
        if SFX_LIGADO:
            final = juntar_efeitos_sonicos(final, cenas_info, audios)
        else:
            print("[sfx] efeitos sonoros desligados (SFX_LIGADO = False)")

        PASTA_SAIDA.mkdir(exist_ok=True)
        destino = PASTA_SAIDA / NOME_SAIDA
        print(f"[...] Gerando {destino.name} (pode levar alguns minutos)...")
        final.write_videofile(
            str(destino),
            codec="libx264",
            audio_codec="aac",
            fps=FPS_PADRAO,
        )

        if NORMALIZAR:
            print("[...] Normalizando o volume (-14 LUFS / -1 dB)...")
            if normalizar_volume(destino):
                print("[OK] Volume no padrao das redes sociais (-14 LUFS)")
            else:
                print("[!] Video mantido com o volume original")

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
