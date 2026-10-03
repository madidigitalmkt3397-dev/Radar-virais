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
   - Fase 8: efeitos sonoros - so toca o que estiver em banco_efeitos/
     (padrao); com SFX_SO_ARQUIVOS = False o render sintetiza
     whoosh/suspense/heartbeat/ding/impacto na hora (tudo gratis)
    - Fase 10: Cut Engine - cortes internos em ritmo ALTERNADO
      (chave PERFIL_CORTES: "normal" 5-7-7-5s | "rapida" 3-5-5-3s |
      "muito_rapida" 0,9-1,8-1,8-0,9s - padrao: muito_rapida)

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
# Normaliza o tamanho das cenas antes de juntar: a tela final segue
# FORMATO_ALVO e as demais cenas sao ajustadas (escala + corte central,
# sem borda preta). Sem isto, o compose do MoviePy usa a maior largura x
# a maior altura entre TODAS as cenas - cenas de resolucoes diferentes
# viram um video com moldura preta (ou quadrado, se alguma cena for 1:1).
AJUSTAR_TAMANHO = True
# Formato da tela final: "9:16" (Shorts/TikTok/Reels) | "16:9" | "1:1"
# | "auto" (a PRIMEIRA cena define a tela - comportamento antigo).
# Com cenas MISTURADAS (1:1 + 16:9 + 9:16), o "auto" seguia a cena 1 e
# o video final saia fora do padrao - por isso o padrao e "9:16".
FORMATO_ALVO = "9:16"
# Tela final nunca menor que a resolucao minima do formato escolhido
# (cenas menores sobem para ela; cenas maiores preservam a nativa).
RESOLUCAO_MINIMA = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (720, 720),
}
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
SFX_SO_ARQUIVOS = True       # True = SO toca arquivo de banco_efeitos/
                             # (nunca sintetiza; sem arquivo = silencio)
SFX_TRANSICAO = True         # whoosh automatico na virada de cada cena
SFX_POR_CENA = True          # usa o efeito_sonoro_sugerido do roteiro
# Volume relativo a VOZ: a narracao fica em ~0,55 de pico e os efeitos em
# cima dela sao densos (chiado/impacto pesa mais que fala no mesmo nivel),
# entao entram bem abaixo - se a narracao parecer baixa, suba a VOZ, nao
# estes valores.
SFX_VOLUME = 0.4             # volume dos efeitos (0.0 a 1.0)
SFX_VOLUME_TRANSICAO = 0.35  # volume do whoosh das trocas

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


# ---------- FASE 10 - Cut Engine (cortes no ritmo da narração) ----------
CUT_ENGINE = True           # liga/desliga o motor de cortes internos
PERFIL_CORTES = "muito_rapida"    # ritmo alternado de duracao de cada plano:
                            # "normal" (5-7-7-5s) | "rapida" (3-5-5-3s) |
                            # "muito_rapida" (0,9-1,8-1,8-0,9s)
CUT_SFX = "auto"            # whoosh nos cortes internos:
                            # "auto" = so no perfil muito_rapida |
                            # True = em todos | False = nunca
CUT_SFX_VOLUME = 0.25       # volume do whoosh dos cortes internos
                             # (muito_rapida = MUITOS cortes: cada whoosh
                             #  fica sutil para a soma nao abafar a voz)
CUT_MARGEM_CENA = 0.45      # nao corta nos X s iniciais/finais da cena

# ritmo de cada perfil: "alvos" = duracao que CADA plano deve ter, alternando
#   (ex.: [3, 5, 5, 3] = 3s, 5s, 5s, 3s, 3s, 5s, 5s, 3s...) | "tol" = folga
#   para o corte encaixar numa pausa/impacto pertinho do alvo
# "min"/"max" = limites duros | "salto" = troca minima de escala no limite
#   de cada corte (o corte visual) | "forca"/"pan" = forca do zoom/enquadramento
PERFIS_CORTES = {
    "normal":       {"alvos": [5, 7, 7, 5], "tol": 1.2,
                     "min": 2.5, "max": 9.0, "forca": 0.05,
                     "pan": 0.04, "impacto": 0.06, "salto": 0.045},
    "rapida":       {"alvos": [3, 5, 5, 3], "tol": 1.2,
                     "min": 2.0, "max": 7.0, "forca": 0.09,
                     "pan": 0.07, "impacto": 0.12, "salto": 0.06},
    "muito_rapida": {"alvos": [0.9, 1.8, 1.8, 0.9], "tol": 0.5,
                     "min": 0.7, "max": 2.5, "forca": 0.13,
                     "pan": 0.10, "impacto": 0.16, "salto": 0.075},
}


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
    # (limiar de 1,0s deixava ate ~0,9s de "buraco mudo" entre cenas;
    #  agora corta ja quando sobra meio segundo - cauda final de 0,3s)
    elif clip.duration > audio.duration + 0.5:
        clip = clip.with_duration(audio.duration + 0.3)

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


def _zoom_central(img, escala, dx=0.0, dy=0.0):
    """
    Amplia o quadro em torno de um centro (bilinear) mantendo o tamanho original.
    escala >= 1.0 sempre - por isso NUNCA aparece borda preta.
    dx/dy (fracao da largura/altura) deslocam o enquadramento (pan do
    Cut Engine); as coordenadas sao limitadas aos bordos - pan alem do
    sobrado vira apenas o maximo possivel (nunca preto).
    FEITO EM NUMPY DE PROPOSITO: o resized() do MoviePy 2 trunca quadros
    float para uint8 (bug) e deixaria o video todo preto.
    """
    import numpy as np
    h, w = img.shape[:2]
    cxp = w / 2.0 + float(dx) * w
    cyp = h / 2.0 + float(dy) * h
    yy = (np.arange(h, dtype="float64") + 0.5 - cyp) / escala + cyp - 0.5
    xx = (np.arange(w, dtype="float64") + 0.5 - cxp) / escala + cxp - 0.5
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


def _redimensionar_quadro(img, tw, th):
    """Redimensiona o quadro para exatamente (tw, th) - corte central (cover).

    Escala na menor razao que COBRE o alvo e corta o excedente pelo centro:
    nunca sobra borda preta, nao importa o tamanho de origem. Aceita uint8
    (0-255) e float, preservando o dtype de entrada. Feito em numpy de
    proposito (mesma razao do _zoom_central: o resized() do MoviePy 2
    trunca quadros).
    """
    import numpy as np

    h, w = img.shape[:2]
    if (w, h) == (tw, th):
        return img
    escala = max(tw / w, th / h)
    # janela da fonte que cabe no alvo (cover), centrada
    x0 = (w - tw / escala) / 2.0
    y0 = (h - th / escala) / 2.0
    xx = x0 + (np.arange(tw, dtype="float64") + 0.5) / escala - 0.5
    yy = y0 + (np.arange(th, dtype="float64") + 0.5) / escala - 0.5
    xi = np.clip(np.floor(xx).astype("int64"), 0, w - 1)
    yi = np.clip(np.floor(yy).astype("int64"), 0, h - 1)
    xi1 = np.clip(xi + 1, 0, w - 1)
    yi1 = np.clip(yi + 1, 0, h - 1)
    fx = np.clip(xx - xi, 0.0, 1.0).astype("float32")
    fy = np.clip(yy - yi, 0.0, 1.0).astype("float32")

    p00 = img[np.ix_(yi, xi)]
    p01 = img[np.ix_(yi, xi1)]
    p10 = img[np.ix_(yi1, xi)]
    p11 = img[np.ix_(yi1, xi1)]
    # mascara 2D: (th, tw) | RGB/RGBA: (th, tw, c) - o reshape acomoda os dois
    dim_extra = img.ndim - 2
    fx = fx.reshape((1, tw) + (1,) * dim_extra)
    fy = fy.reshape((th, 1) + (1,) * dim_extra)
    cima = p00 * (1.0 - fx) + p01 * fx
    baixo = p10 * (1.0 - fx) + p11 * fx
    saida = cima * (1.0 - fy) + baixo * fy
    if np.issubdtype(img.dtype, np.integer):
        saida = np.clip(np.rint(saida), 0,
                        np.iinfo(img.dtype).max).astype(img.dtype)
    else:
        saida = saida.astype(img.dtype)
    return saida


def _alvo_por_formato(cenas, VideoFileClip, ImageClip):
    """Escolhe a tela final seguindo FORMATO_ALVO (antes: cena 1 mandava).

    - "auto" -> None (a PRIMEIRA cena define a tela, comportamento antigo);
    - formato fixo -> a MAIOR cena que ja esta nesse formato (preserva a
      melhor resolucao nativa), com piso da RESOLUCAO_MINIMA do formato;
    - nenhuma cena no formato -> cai na resolucao minima (todas sao
      recortadas em cover para o formato escolhido).
    """
    if not AJUSTAR_TAMANHO or FORMATO_ALVO == "auto":
        return None
    chave = str(FORMATO_ALVO).replace(" ", "")
    minimo = RESOLUCAO_MINIMA.get(chave)
    if minimo is None:
        print(f"[!] FORMATO_ALVO desconhecido: {FORMATO_ALVO!r} - usando auto")
        return None
    try:
        num, den = (int(x) for x in chave.split(":"))
        razao = num / den
    except Exception:
        return minimo

    melhor = None
    for _ordem, arq in cenas:
        try:
            if arq.suffix.lower() in EXTENSOES_IMAGEM:
                tmp = ImageClip(str(arq))
                tam = tuple(tmp.size)
                tmp.close()
            else:
                tmp = VideoFileClip(str(arq))
                tam = tuple(tmp.size)
                tmp.close()
        except Exception:
            continue
        if not tam[1]:
            continue
        if abs((tam[0] / tam[1]) / razao - 1.0) <= 0.03:   # =/- 3% do formato
            if melhor is None or tam[0] * tam[1] > melhor[0] * melhor[1]:
                melhor = tam
    if melhor is None:
        print(f"[!] Nenhuma cena em {chave} - tela fixa no minimo "
              f"{minimo[0]}x{minimo[1]} (cover em todas as cenas)")
        return minimo
    if melhor[0] < minimo[0] or melhor[1] < minimo[1]:
        return minimo
    return melhor


def corrigir_reader_moviepy():
    """Parcheia o FFMPEG_AudioReader.get_frame do MoviePy 2.1.2.

    Bug real: quando a janela pedida cobre mais que buffersize//2 do
    arquivo, o get_frame recursa passando a MASCARA BOOL (in_time[...])
    no lugar dos timestamps - os True viram t=1.0 e arquivos com menos
    de 1,0s derrubam o render com:

        OSError: ... Accessing time t=1.00-1.00 seconds ...

    (e arquivos de ~1,0 a ~2,3s leem um trecho errado, sem avisar).
    Correcao cirurgica: recursar com os TEMPOS validos; buffer, EOF e
    erros continuam sendo os do metodo original. Idempotente.
    """
    try:
        from moviepy.audio.io import readers as _readers
        classe = _readers.FFMPEG_AudioReader
        original = classe.get_frame
        if getattr(original, "_radar_corrigido", False):
            return

        def get_frame_corrigido(self, tt):
            import numpy as np
            if isinstance(tt, np.ndarray):
                dentro = (tt >= 0) & (tt < self.duration)
                if dentro.any():
                    tempos = tt[dentro]
                    quadros = np.round(self.fps * tempos).astype(int)
                    limite = quadros.min() + self.buffersize // 2
                    corte = int(np.searchsorted(quadros, limite,
                                                side="right"))
                    if corte != len(quadros):
                        cabeca = self.get_frame(tempos[:corte])
                        cauda = self.get_frame(tempos[corte:])
                        saida = np.zeros((len(tt), self.nchannels))
                        saida[dentro] = np.concatenate([cabeca, cauda])
                        return saida
            return original(self, tt)

        get_frame_corrigido._radar_corrigido = True
        classe.get_frame = get_frame_corrigido
    except Exception as erro:
        print(f"[!] patch do MoviePy nao aplicado: {erro}")


def _montar_transform(espelhar: bool, flash: bool, zoom):
    """
    Funcao de quadro da Fase 9 (roda em TODOS os frames):
      - zoom Ken Burns: classico (zoom = (inicio, fim, duracao)) OU o
        plano chamavel do Cut Engine (devolve escala, dx, dy, espelhar)
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

        # Cut Engine (Fase 10): o plano do segundo `t` devolve
        # (escala, dx, dy, espelhar) - a troca brusca de enquadramento
        # no limite dos planos e o proprio CORTE visual
        escala_cut = None
        dx_cut = dy_cut = 0.0
        espelhar_aqui = espelhar
        if callable(zoom):
            plano = zoom(float(t))
            if plano is not None:
                escala_cut, dx_cut, dy_cut, espelhar_aqui = plano

        if ESPELHAR_CLIPES and espelhar_aqui:
            rgb = rgb[:, ::-1]
            if alpha is not None:
                alpha = alpha[:, ::-1]

        if escala_cut is not None:
            # Ken Burns do Cut Engine: escala/enquadramento do plano atual
            if escala_cut > 1.0 or dx_cut or dy_cut:
                rgb = _zoom_central(rgb, escala_cut, dx_cut, dy_cut)
                if alpha is not None:
                    alpha = _zoom_central(alpha, escala_cut, dx_cut, dy_cut)
        elif zoom is not None:
            # Ken Burns classico da Fase 9 (escala sempre >= 1.0)
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


def tratar_imagem(clip, numero, primeira, ultima, planos=None):
    """
    Fase 9 - da vida aos clipes:
      1. processamento por quadro: zoom Ken Burns (sempre >= 100% - sem
         borda preta), correcao de cor, nitidez e efeitos opcionais
      2. fades: so a 1a cena surge do preto e a ultima termina no preto
        (nas trocas do meio fica corte seco - pisca preto se fosse em tudo)
      planos (Fase 10): pedacos do Cut Engine - a troca brusca de
        enquadramento no limite de cada plano e o corte visual
    """
    from moviepy import vfx

    espelhar = (numero % 2 == 0)  # variacao visual se ESPELHAR_CLIPES ligado
    flash = FLASH_NA_TROCA and not primeira

    # Ken Burns: cenas impares aproximam, pares afastam (variedade visual)
    zoom = None
    if planos:
        # Fase 10 - Cut Engine: um plano por pedaco entre cortes
        zoom = _fn_planos(planos)
    elif ZOOM_DINAMICO and ESCALA_ZOOM > 1.0 and clip.duration and clip.duration > 0:
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
      - SFX_SO_ARQUIVOS = True: so toca arquivo do banco (sem sintetizar)
    `audios` recebe os arquivos abertos (o finally do principal fecha).
    """
    from moviepy import CompositeAudioClip

    dur_total = final.duration
    faixas = []
    sintetizados = 0
    do_banco = 0
    faltando = []
    ignorados = 0
    cortes_sfx = 0

    for i, info in enumerate(cenas_info):
        inicio = float(info["inicio"])
        dur_cena = float(info["duracao"])
        sugerido_norm = _normalizar_texto(info["sugerido"])
        tipo = _tipo_efeito(sugerido_norm) if sugerido_norm else None
        e_whoosh = tipo == "whoosh" or "whoosh" in sugerido_norm \
            or "swoosh" in sugerido_norm

        # --- 1) efeito sugerido no roteiro ---
        clip_efeito = None
        efeito_colocado = False
        if SFX_POR_CENA and sugerido_norm:
            arquivo = _achar_sfx(sugerido_norm, exceto=SFX_TRANSICAO_NOMES)
            if arquivo is not None:
                clip_efeito = _criar_clip_sfx(caminho=arquivo)
                if clip_efeito is not None:
                    audios.append(clip_efeito)
                    do_banco += 1
            elif SFX_SO_ARQUIVOS:
                ignorados += 1       # so-arquivos: sem arquivo = silencio
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
                efeito_colocado = _encaixar(
                    faixas, clip_efeito, onde, dur_total
                )

        # --- 2) whoosh da transicao (se a cena nao ja colocou um whoosh) ---
        if SFX_TRANSICAO and i > 0 and not (e_whoosh and efeito_colocado):
            arquivo_t = _achar_transicao()
            clipe = None
            if arquivo_t is not None:
                clipe = _criar_clip_sfx(
                    caminho=arquivo_t, volume=SFX_VOLUME_TRANSICAO
                )
                if clipe is not None:
                    audios.append(clipe)
                    do_banco += 1
            elif not SFX_SO_ARQUIVOS:
                clipe = _criar_clip_sfx(
                    tipo="whoosh", volume=SFX_VOLUME_TRANSICAO
                )
                sintetizados += 1
            if clipe is not None:
                _encaixar(
                    faixas, clipe,
                    max(0.0, inicio - SFX_ANTES_DO_CORTE), dur_total,
                )

        # --- 3) whoosh dos cortes internos (Fase 10 - Cut Engine) ---
        if info.get("cortes") and _cut_sfx_ativo():
            arquivo_t = _achar_transicao()
            for t_corte in info["cortes"]:
                clipe = None
                if arquivo_t is not None:
                    clipe = _criar_clip_sfx(
                        caminho=arquivo_t, volume=CUT_SFX_VOLUME
                    )
                    if clipe is not None:
                        audios.append(clipe)
                        do_banco += 1
                elif not SFX_SO_ARQUIVOS:
                    clipe = _criar_clip_sfx(
                        tipo="whoosh", volume=CUT_SFX_VOLUME
                    )
                    sintetizados += 1
                if clipe is not None:
                    cortes_sfx += 1
                    _encaixar(
                        faixas, clipe,
                        max(0.0, inicio + t_corte - SFX_ANTES_DO_CORTE),
                        dur_total,
                    )

    if not faixas:
        if ignorados:
            print(f"[sfx] banco_efeitos/ vazio para este roteiro "
                  f"({ignorados} cena(s) sem arquivo; modo so-arquivos)")
        else:
            print("[sfx] nenhum efeito sonoro para adicionar")
        return final

    base = [final.audio] if final.audio is not None else []
    mistura = CompositeAudioClip(base + faixas)
    # MoviePy 2: CompositeAudioClip nasce com duration None - obriga explicito
    mistura = mistura.with_duration(dur_total)
    final = final.with_audio(mistura)
    print(f"[OK] Efeitos sonoros: {sintetizados} sintetizado(s) "
          f"+ {do_banco} do banco_efeitos/")
    if ignorados:
        print(f"     modo so-arquivos: {ignorados} cena(s) sem arquivo "
              "no banco (ficaram em silencio)")
    if cortes_sfx:
        print(f"     whoosh nos cortes internos do Cut Engine: {cortes_sfx}")
    if faltando:
        print("     sem arquivo (baixe gratis e salve em banco_efeitos/): "
              + ", ".join(faltando))
    return final


# ================ FASE 10 - Cut Engine ================
# Decide OS CORTES internos de cada cena no ritmo da narração.
# Sinais usados: silencio, fim de frase/assunto, palavras de impacto,
# picos de voz (enfase), movimento da cena, duracao da cena e o perfil.

PALAVRAS_IMPACTO = (
    "chocou", "chocante", "inacreditavel", "incrivel", "inesperado",
    "surpreendente", "revelou", "verdade", "segredo", "nunca", "ninguem",
    "todo mundo", "gritou", "parou", "chorou", "abracou", "morreu",
    "morte", "dinheiro", "milionario", "assustador", "escapou", "heroi",
)

# peso de cada sinal na escolha do corte (maior = corta ali)
PESOS_CORTES = {
    "normal":       {"pausa": 30, "frase": 26, "virgula": 8,
                     "impacto": 12, "pico": 8},
    "rapida":       {"pausa": 30, "frase": 20, "virgula": 9,
                     "impacto": 34, "pico": 30},
    "muito_rapida": {"pausa": 26, "frase": 18, "virgula": 12,
                     "impacto": 24, "pico": 22},
}

# sequencia de enquadramentos: (aproximacao, direcao do zoom, quer pan)
# 0 = aberto, 1 = medio, 2 = fechado
PADRAO_PLANOS = (
    (0.0, 1, False), (1.0, -1, True), (0.5, 1, True), (2.0, 1, False),
    (1.0, 1, True), (0.0, -1, False), (1.5, -1, True),
)


def _cut_sfx_ativo():
    """Fase 10 - whoosh nos cortes internos? (respeita SFX_* e o perfil)"""
    if not (SFX_LIGADO and CUT_ENGINE and SFX_TRANSICAO):
        return False
    if CUT_SFX is True:
        return True
    if CUT_SFX is False:
        return False
    return PERFIL_CORTES == "muito_rapida"   # "auto"


def _texto_da_cena(roteiro, numero):
    """Texto de narracao da cena (campo `narracao` do roteiro.json)."""
    if not roteiro or not isinstance(roteiro.get("cenas"), list):
        return ""
    for cena in roteiro["cenas"]:
        if isinstance(cena, dict) and cena.get("numero") == numero:
            return cena.get("narracao") or ""
    return ""


def _carregar_sinal_mono(caminho):
    """Decodifica o audio em mono 44100 Hz (numpy puro, via FFmpeg)."""
    import numpy as np
    proc = subprocess.run(
        [achar_ffmpeg(), "-i", str(caminho), "-ac", "1", "-ar", str(FS_SFX),
         "-f", "f32le", "-"],
        capture_output=True,
    )
    return np.frombuffer(proc.stdout, dtype="float32").astype("float64")


def _energia_da_narracao(sinal):
    """
    Curva de volume da fala (RMS de 20 em 20 ms, suavizada, 0 a 1).
    E o 'momento da narração': vales = pausas/termos de frase,
    picos = voz de enfase (impacto).
    """
    import numpy as np
    if sinal is None or len(sinal) < FS_SFX // 4:
        return None
    janela = int(0.02 * FS_SFX)
    m = len(sinal) // janela
    if m < 10:
        return None
    rms = np.sqrt((
        sinal[: m * janela].reshape(m, janela).astype("float64") ** 2
    ).mean(axis=1))
    if m >= 5:  # suaviza em 0,1s para nao tremer no meio de uma consoante
        rms = np.convolve(rms, np.ones(5) / 5.0, mode="same")
    topo = float(np.percentile(rms, 95))
    if topo <= 1e-6:
        return None
    return rms / topo


def _pausas_da_narracao(energia):
    """Intervalos de silencio interno (>= 0,10s): corte ali fica invisivel."""
    import numpy as np
    if energia is None:
        return []
    limiar = max(0.05, float(np.percentile(energia, 90)) * 0.12)
    baixo = energia < limiar
    bordas = np.concatenate(([False], baixo, [False]))
    d = np.diff(bordas.astype("int8"))
    inicios = np.flatnonzero(d == 1)
    fins = np.flatnonzero(d == -1)
    saida = []
    for a, b in zip(inicios, fins):
        if a == 0 or b >= len(energia):   # comeco/fim da cena: nao corta ali
            continue
        if (b - a) * 0.02 >= 0.10:
            saida.append((a * 0.02, b * 0.02))
    return saida


def _frase_tem_impacto(frase):
    """! ou ? , caixa alta ou palavra de impacto = momento de enfase."""
    if "!" in frase or "?" in frase:
        return True
    for bruto in re.findall(r"\b[A-Za-zÀ-ÿ]{3,}\b", frase):
        if len(bruto) >= 3 and bruto.isupper():
            return True
    limpo = _normalizar_texto(frase)
    return any(p in limpo for p in PALAVRAS_IMPACTO)


def _marcos_do_texto(texto):
    """
    Frases e virgulas do texto viram marcadores em fracao da duracao
    da cena (0 a 1): 'frase' = fim de frase/assunto, 'impacto' =
    comeco de frase de impacto (o corte ENTRA no impacto), 'virgula' =
    sub-mudanca dentro da frase.
    """
    if not texto or not texto.strip():
        return []
    partes = [p for p in re.split(r"(?<=[.!?…])\s+", texto.strip()) if p.strip()]
    total = max(len(texto), 1)
    marcos = []
    pos = 0
    for p in partes:
        ini = texto.find(p, pos)
        if ini < 0:
            ini = pos
        fim = min(ini + len(p), total)
        pos = fim
        if 0.0 < fim / total < 1.0:
            marcos.append((fim / total, "frase"))
        if _frase_tem_impacto(p) and ini / total > 0.02:
            marcos.append((ini / total, "impacto"))
        for m in re.finditer(r",\s+", p):
            fr = (ini + m.end()) / total
            if 0.0 < fr < 1.0:
                marcos.append((fr, "virgula"))
    return marcos


def _colar_no_vale(energia, t, janela=0.30):
    """Aproxima t para o ponto mais calmo da fala em +/- janela (corte disfarcado)."""
    import numpy as np
    if energia is None:
        return t
    i = int(round(t / 0.02))
    a = max(0, i - int(janela / 0.02))
    b = min(len(energia), i + int(janela / 0.02) + 1)
    if b - a < 2:
        return t
    return (a + int(np.argmin(energia[a:b]))) * 0.02


def _momentos_de_impacto(energia):
    """Pontos de voz mais forte: marca o vale logo ANTES do pico."""
    import numpy as np
    if energia is None or len(energia) < 20:
        return []
    med = float(np.median(energia))
    if med <= 1e-6:
        return []
    saida = []
    i = 2
    n = len(energia)
    while i < n - 2:
        if (energia[i] >= med * 1.5 and energia[i] >= energia[i - 1]
                and energia[i] > energia[i + 1]):
            a = max(0, i - 25)          # 0,5s para tras
            j = a + int(np.argmin(energia[a:i + 1]))
            saida.append(j * 0.02)
            i += 15                      # nao conta o mesmo pico de novo
        else:
            i += 1
    return saida


def _movimento_da_cena(clip, t, dur):
    """Quanto a cena se mexe perto de t (0 = parado, 1 = acao forte)."""
    import numpy as np
    if clip is None or not dur or dur <= 0.3:
        return 0.0
    if clip.__class__.__name__ == "ImageClip":
        return 0.0                       # imagem fixa nao tem movimento
    cache = getattr(clip, "_cut_mov_cache", None)
    if cache is None:
        cache = {}
        try:
            clip._cut_mov_cache = cache
        except Exception:
            pass
    chave = round(float(t) / 0.4)
    if chave in cache:
        return cache[chave]
    mov = 0.0
    try:
        ts = [max(0.0, t - 0.12),
              min(max(t, 0.0), max(dur - 0.02, 0.0)),
              min(max(dur - 0.01, 0.0), t + 0.12)]
        quadros = [clip.get_frame(x) for x in ts]
        for a, b in zip(quadros, quadros[1:]):
            if a.shape != b.shape:
                continue
            ga = a[..., :3].astype("float32").mean(axis=2)[::4, ::4]
            gb = b[..., :3].astype("float32").mean(axis=2)[::4, ::4]
            mov = max(mov, float(np.abs(gb - ga).mean()) / 255.0)
        mov = min(1.0, mov * 15.0)
    except Exception:
        mov = 0.0
    cache[chave] = mov
    return mov


def calcular_cortes(dur, energia, texto, perfil, clip=None):
    """
    Cut Engine: devolve os cortes da cena (tempo local, em segundos).
    Cada item = {"t": segundo, "impacto": True/False}.
    Sigue o ritmo alternado (alvos) do perfil, os limites min/max
    do perfil e a margem da cena.
    """
    import numpy as np
    cfg = PERFIS_CORTES.get(perfil) or PERFIS_CORTES["rapida"]
    pesos = PESOS_CORTES.get(perfil) or PESOS_CORTES["rapida"]
    dur = float(dur or 0.0)
    if dur <= 0.0:
        return []
    margem = min(CUT_MARGEM_CENA, dur * 0.2)

    candidatos = []

    # 1) silencio da narracao = melhor lugar para cortar
    for a, b in _pausas_da_narracao(energia):
        candidatos.append({"t": (a + b) / 2.0, "peso": pesos["pausa"],
                           "impacto": False})

    # 2) fim de frase/assunto + comeco de frase de impacto
    for frac, tipo in _marcos_do_texto(texto):
        t = _colar_no_vale(energia, frac * dur, 0.30)
        candidatos.append({"t": t, "peso": pesos[tipo],
                           "impacto": tipo == "impacto"})

    # 3) picos de voz (enfase da narração = momento de impacto)
    for t in _momentos_de_impacto(energia):
        candidatos.append({"t": t, "peso": pesos["pico"], "impacto": True})

    candidatos = [c for c in candidatos if 0.0 <= c["t"] <= dur]

    # 4) movimento da cena: acao forte no instante do corte = penalidade
    if clip is not None:
        for c in candidatos:
            mov = _movimento_da_cena(clip, c["t"], dur)
            if mov > 0.35:
                c["peso"] *= (1.0 - 0.6 * mov)

    # candidatos muito proximos (0,15s): fica so o de maior peso
    candidatos.sort(key=lambda c: (-c["peso"], c["t"]))
    limpos = []
    for c in candidatos:
        if all(abs(c["t"] - o["t"]) >= 0.15 for o in limpos):
            limpos.append(c)
    candidatos = sorted(limpos, key=lambda c: c["t"])

    # 5) ritmo alternado do perfil (ex.: alvos 3, 5, 5, 3 = 3s, 5s, 5s, 3s,
    #    3s, 5s...) - o corte procura ficar perto do alvo da vez, mas entra
    #    na pausa/impacto pertinho dele (folga = tol)
    alvos = cfg.get("alvos") or [(cfg["min"] + cfg["max"]) / 2.0]
    tol = cfg.get("tol", max(0.4, (cfg["max"] - cfg["min"]) / 2.0))
    cortes = []
    t = margem
    k = 0
    while True:
        mira = t + alvos[k % len(alvos)]
        lo = max(t + cfg["min"], mira - tol)
        hi = min(mira + tol, t + cfg["max"], dur - cfg["min"])
        if lo > hi:
            break
        na_janela = [c for c in candidatos if lo - 1e-6 <= c["t"] <= hi + 1e-6]
        if na_janela:
            melhor = max(na_janela,
                         key=lambda c: (c["peso"], -abs(c["t"] - mira)))
            alvo, impacto = melhor["t"], bool(melhor["impacto"])
        elif energia is not None:
            # nenhum sinal: corta no ponto mais calmo da janela
            i0 = min(int(lo / 0.02), len(energia) - 1)
            i1 = min(max(int(hi / 0.02), i0 + 1), len(energia))
            alvo = min(max((i0 + int(np.argmin(energia[i0:i1]))) * 0.02, lo), hi)
            impacto = False
        else:
            alvo = (lo + hi) / 2.0
            impacto = False
        alvo = min(max(alvo, lo), hi)
        cortes.append({"t": round(float(alvo), 3), "impacto": impacto})
        t = alvo
        k += 1
    return cortes


def montar_planos(dur, cortes, perfil, numero):
    """
    Cut Engine: cria o plano visual de cada pedaco entre cortes
    (aproximacao do zoom, direcao e enquadramento/pan). A troca brusca
    de plano no limite do corte e o que se ve como CORTE na tela.
    """
    cfg = PERFIS_CORTES.get(perfil) or PERFIS_CORTES["rapida"]
    limites = [0.0] + [float(c["t"]) for c in cortes] + [float(dur)]
    planos = []
    passo = cfg["forca"] * 0.6
    for i in range(len(limites) - 1):
        ini, fim = limites[i], limites[i + 1]
        if fim - ini <= 0.03:
            continue
        nivel, direcao, quer_pan = PADRAO_PLANOS[
            (i + numero) % len(PADRAO_PLANOS)
        ]
        impacto = bool(cortes[i - 1]["impacto"]) if i >= 1 else False
        base = max(ESCALA_ZOOM, 1.02)
        escala = base + cfg["forca"] * (nivel / 2.0)
        cx_ini = cy_ini = 0.0
        if quer_pan and cfg["pan"] > 0:
            p = cfg["pan"]
            folga = 1.0 / max(1e-6, 1.0 - p / 0.45)  # escala que comporta o pan
            escala = max(escala, folga + passo)
            p = min(p, 0.45 * (1.0 - 1.0 / max(escala - passo, 1.01)))
            dxs, dys = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[
                (i + numero) % 4
            ]
            cx_ini, cy_ini = dxs * p, dys * p
        if impacto:
            # punch de impacto POR CIMA de tudo (nunca engolido pelo pan)
            escala += cfg["impacto"]
        if direcao > 0:
            e_ini = max(1.02, escala - passo)
            e_fim = escala
        else:
            e_ini = escala
            e_fim = max(1.02, escala - passo)
        planos.append({
            "ini": ini, "fim": fim,
            "e_ini": float(e_ini), "e_fim": float(e_fim),
            "cx_ini": float(cx_ini), "cy_ini": float(cy_ini),
            "cx_fim": 0.0, "cy_fim": 0.0,
            "espelhar": bool((i + numero) % 2 == 1),
        })

    # garante CORTE visivel: o plano novo nunca nasce na mesma escala em
    # que o anterior terminou (salto minimo do perfil - so empurra para
    # CIMA: escala maior = mais folga, o pan nunca perde a borda)
    salto_min = cfg["salto"]
    for i in range(1, len(planos)):
        ant, atu = planos[i - 1], planos[i]
        d = atu["e_ini"] - ant["e_fim"]
        if abs(d) >= salto_min:
            continue
        ajuste = (ant["e_fim"] + salto_min) - atu["e_ini"]
        atu["e_ini"] += ajuste
        atu["e_fim"] += ajuste
    return planos


def _fn_planos(planos):
    """Funcao de quadro do Cut Engine: (escala, dx, dy, espelhar) no instante t."""
    import bisect
    inicios = [p["ini"] for p in planos]

    def plano_em(t):
        i = bisect.bisect_right(inicios, t) - 1
        if i < 0:
            i = 0
        elif i >= len(planos):
            i = len(planos) - 1
        p = planos[i]
        dur = p["fim"] - p["ini"]
        frac = (t - p["ini"]) / dur if dur > 0 else 0.0
        frac = min(max(frac, 0.0), 1.0)
        escala = p["e_ini"] + (p["e_fim"] - p["e_ini"]) * frac
        dx = p["cx_ini"] + (p["cx_fim"] - p["cx_ini"]) * frac
        dy = p["cy_ini"] + (p["cy_fim"] - p["cy_ini"]) * frac
        return (escala, dx, dy, p["espelhar"])

    return plano_em


def principal():
    print("=" * 58)
    print(" FASE 6 - Render do video final")
    print("=" * 58)

    # 1. MoviePy instalado?
    try:
        from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
    except ImportError:
        sys.exit("ERRO: MoviePy nao instalado. Rode primeiro:\n   python -m pip install moviepy")
    corrigir_reader_moviepy()   # SFX/arquivos curtos nao derrubam o render

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
    alvo = None   # tela final (AJUSTAR_TAMANHO + FORMATO_ALVO)
    if AJUSTAR_TAMANHO:
        alvo = _alvo_por_formato(cenas, VideoFileClip, ImageClip)
        if alvo is not None:
            print(f"[OK] Tela final ({FORMATO_ALVO}): {alvo[0]}x{alvo[1]}")
    audios = []
    com_narracao = 0
    resumo_cortes = []   # Fase 10: (numero, n_cortes) de cada cena
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

            # Ajusta resolucoes/formatos diferentes da tela final (cover +
            # corte central) - sem isto o compose do MoviePy centraliza a
            # cena menor com moldura preta (ou a tela vira quadrada).
            # alvo vem de FORMATO_ALVO; se None ("auto"), a cena 1 define.
            if AJUSTAR_TAMANHO:
                if alvo is None:
                    alvo = tuple(clip.size)
                elif tuple(clip.size) != alvo:
                    antes = tuple(clip.size)
                    clip = clip.image_transform(
                        lambda f: _redimensionar_quadro(f, *alvo),
                        apply_to="mask")
                    print(f" [{antes[0]}x{antes[1]} -> {alvo[0]}x{alvo[1]}]",
                          end="", flush=True)

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

            # Fase 10 - Cut Engine: decide os cortes no ritmo da narração
            planos = None
            cortes_cena = []
            if CUT_ENGINE and ZOOM_DINAMICO and PERFIL_CORTES in PERFIS_CORTES:
                energia = None
                if narracao:
                    energia = _energia_da_narracao(
                        _carregar_sinal_mono(narracao)
                    )
                texto_cena = _texto_da_cena(roteiro, ordem)
                cortes_cena = calcular_cortes(
                    clip.duration or 0.0, energia, texto_cena,
                    PERFIL_CORTES, clip=clip,
                )
                if cortes_cena:
                    planos = montar_planos(
                        clip.duration, cortes_cena, PERFIL_CORTES, ordem
                    )

            # Fase 9 - cor, nitidez, zoom Ken Burns e fades
            clip = tratar_imagem(
                clip, ordem,
                primeira=(indice == 0),
                ultima=(indice == len(cenas) - 1),
                planos=planos,
            )
            if audio is not None and clip.audio is None:
                clip = clip.with_audio(audio)  # salvaguarda: efeitos nunca perdem a voz

            clips.append(clip)
            resumo_cortes.append((ordem, len(cortes_cena)))
            cenas_info.append({
                "numero": ordem,
                "inicio": inicio_cena,
                "duracao": clip.duration or 0.0,
                "sugerido": _sugestao_do_roteiro(roteiro, ordem),
                "cortes": [c["t"] for c in cortes_cena],
            })
            inicio_cena += clip.duration or 0.0

        print(f"[OK] Narração em {com_narracao}/{len(cenas)} cena(s)")
        if com_narracao < len(cenas):
            print("     (cenas sem audio ficam em silencio - rode gerar_narracao.py para todas)")

        # Fase 10 - resumo do Cut Engine
        if CUT_ENGINE:
            if PERFIL_CORTES not in PERFIS_CORTES:
                print(f"[!] PERFIL_CORTES invalido: {PERFIL_CORTES!r} "
                      f"(use: {', '.join(PERFIS_CORTES)}) - sem cortes")
            elif not ZOOM_DINAMICO:
                print("[cut] Cut Engine parado: ZOOM_DINAMICO = False")
            else:
                cfg_p = PERFIS_CORTES[PERFIL_CORTES]
                ritmo = "-".join(f"{a:g}" for a in cfg_p.get("alvos", []))
                total_cortes = sum(n for _, n in resumo_cortes)
                detalhe = " | ".join(
                    f"cena {n}: {k}" for n, k in resumo_cortes
                )
                print(f"[cut] Perfil {PERFIL_CORTES} "
                      f"(ritmo {ritmo}s por plano): "
                      f"{detalhe} -> {total_cortes} corte(s) interno(s)")
                instantes = sorted(
                    info["inicio"] + t
                    for info in cenas_info
                    for t in info.get("cortes", [])
                )
                if instantes:
                    print("[cut] instantes globais (s): "
                          + ", ".join(f"{x:.2f}" for x in instantes))
        else:
            print("[cut] Cut Engine desligado (CUT_ENGINE = False)")

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
