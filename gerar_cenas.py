# -*- coding: utf-8 -*-
"""
===========================================================
 GERA AS CENAS (IMAGEM) a partir dos prompt_visual do roteiro
===========================================================
 COMO USAR:
   1. `roteiro.json` (baixado do site) nesta pasta
   2. Rode:  python gerar_cenas.py
   3. As imagens nascem em `cenas\\cena1.jpg`, `cena2.jpg`...
      (cenas antigas sao movidas para `cenas\\_antigas\\<hora>\\`)
   4. Depois: python gerar_narracao.py  ->  python render_video.py

 FONTE (100% gratis, sem chave e sem cadastro):
   API classica do Pollinations -> https://image.pollinations.ai
   - limite por IP: 1 imagem por vez e ~45s entre elas - o script
     espera sozinho e, se vier 402, obedece o Retry-After deles;
   - saida: JPEG (768x768): o render_video.py recorta no formato
     9:16 e aplica o zoom de movimento (mesmo fluxo das imagens
     que voce ja usava);
   - a mesma URL devolve a mesma imagem; usamos seed nova por
     cena para as cenas nao sairem identicas.

 CONSTANTES (edite para ligar/desligar):
   SUFIXO_ESTILO = ""  -> prompts do roteiro puro, sem estilo extra
   ESPERA_ENTRE_IMAGENS -> ritmo entre downloads
===========================================================
"""

import json
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Nunca derruba o script por caractere estranho no console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# ---------- Configuracoes ----------
BASE = Path(__file__).resolve().parent
ARQUIVO_ROTEIRO = BASE / "roteiro.json"
PASTA_CENAS = BASE / "cenas"
PASTA_BACKUP = PASTA_CENAS / "_antigas"

URL_BASE = "https://image.pollinations.ai/prompt/"
NAVEGADOR_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# estilo extra somado ao prompt_visual (em ingles, como o roteiro pede):
# compoe a cena pensando no recorte9:16 central. "" = prompt puro.
SUFIXO_ESTILO = (", centered composition, subject fully inside frame, "
                 "cinematic lighting, high detail")

ESPERA_ENTRE_IMAGENS = 48   # segundos entre pedidos (limite deles ~45s)
TENTATIVAS_POR_CENA = 4     # inclui retentativas de 402 (limite por IP)
ESPERA_MAX_402 = 300        # teto (s) para o Retry-After do 402
TAMANHO_MINIMO = 8_000      # bytes: um JPEG valido passa de 8 KB


def _esperar_402(erro: urllib.error.HTTPError) -> None:
    """402 do Pollinations = fora do ritmo gratuito; obedece o Retry-After."""
    tentar = erro.headers.get("Retry-After") if erro.headers else None
    try:
        segundos = int(str(tentar).strip())
    except (TypeError, ValueError):
        segundos = ESPERA_ENTRE_IMAGENS + 5
    segundos = max(5, min(segundos, ESPERA_MAX_402))
    print(f"   [!] limite gratuito atingido - esperando {segundos}s (Retry-After)")
    time.sleep(segundos)


def _baixar_imagem(prompt: str, seed: int) -> bytes:
    """Baixa UMA imagem da API keyless. LANCA erro se todas as tentativas falharem."""
    url = (URL_BASE + urllib.parse.quote(prompt, safe="")
           + f"?seed={seed}&nologo=true")
    ultimo_erro = None
    for tentativa in range(TENTATIVAS_POR_CENA):
        req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR_UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                dados = resp.read()
            if not dados.startswith(b"\xff\xd8\xff"):
                raise ValueError(f"resposta nao e JPEG ({len(dados)} bytes)")
            if len(dados) < TAMANHO_MINIMO:
                raise ValueError(f"JPEG pequeno demais ({len(dados)} bytes)")
            return dados
        except urllib.error.HTTPError as e:
            ultimo_erro = e
            if e.code == 402:
                _esperar_402(e)
                continue            # mesma tentativa de novo apos esperar
            time.sleep(8)           # erro pontual (500/503...) -> espera e repete
        except Exception as e:      # timeout, rede, JPEG invalido
            ultimo_erro = e
            time.sleep(8)
    raise RuntimeError(f"{type(ultimo_erro).__name__}: {ultimo_erro}")


def _guardar_cenas_antigas(numero: int) -> list:
    """Move cenaN.* antigos (video ou imagem) para cenas/_antigas/<hora>."""
    padrao = re.compile(rf"^cena{int(numero)}\.")
    alvos = [a for a in PASTA_CENAS.iterdir()
             if a.is_file() and padrao.match(a.name)]
    if not alvos:
        return []
    destino = PASTA_BACKUP / time.strftime("%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    for arquivo in alvos:
        shutil.move(str(arquivo), str(destino / arquivo.name))
    return [a.name for a in alvos]


def gerar_cenas() -> int:
    print("=" * 58)
    print(" GERA CENAS - imagens gratis para os prompts do roteiro")
    print("=" * 58)

    if not ARQUIVO_ROTEIRO.exists():
        print("[ERRO] roteiro.json nao encontrado. Baixe o pacote do site "
              "e salve nesta pasta.")
        return 1

    with open(ARQUIVO_ROTEIRO, "r", encoding="utf-8") as f:
        roteiro = json.load(f)
    cenas = roteiro.get("cenas", [])
    if not cenas:
        print("[ERRO] roteiro.json sem cenas.")
        return 1

    titulo = roteiro.get("titulo_otimizado", "(sem titulo)")
    print(f"[OK] Roteiro lido: \"{titulo}\" | {len(cenas)} cena(s)")
    PASTA_CENAS.mkdir(exist_ok=True)

    geradas = 0
    falhas = []
    t_req_anterior = 0.0

    for cena in cenas:
        numero = int(cena.get("numero", 0))
        prompt = (cena.get("prompt_visual") or "").strip()
        if not prompt:
            prompt = (cena.get("narracao") or "").strip()
            print(f"[!] Cena {numero}: prompt_visual vazio - usando a narracao")
        prompt_final = prompt + SUFIXO_ESTILO if SUFIXO_ESTILO else prompt

        # ritmo: respeita ESPERA_ENTRE_IMAGENS desde o ultimo pedido
        falta = ESPERA_ENTRE_IMAGENS - (time.time() - t_req_anterior)
        if t_req_anterior and falta > 0:
            print(f"   (esperando {int(falta)}s para nao estourar o limite gratuito...)")
            time.sleep(falta)

        print(f"-> Cena {numero}: gerando ...", end="", flush=True)
        t_req_anterior = time.time()
        try:
            dados = _baixar_imagem(prompt_final, seed=random.randint(1, 2_000_000_000))
            destino = PASTA_CENAS / f"cena{numero}.jpg"
            movidos = _guardar_cenas_antigas(numero)
            destino.write_bytes(dados)
            extra = f" | backup: {', '.join(movidos)}" if movidos else ""
            print(f" [OK] cena{numero}.jpg ({len(dados) // 1024} KB){extra}")
            geradas += 1
        except Exception as e:
            print(f" [ERRO] {e}")
            falhas.append(numero)

    print("-" * 58)
    if geradas:
        print(f" PRONTO! {geradas} imagem(s) geradas em: {PASTA_CENAS}")
    if falhas:
        print(f" [!] Cenas que falharam: {falhas} - rode de novo "
              "(as prontas serao substituidas).")
    print(" Proximo passo:  python gerar_narracao.py  ->  python render_video.py")
    print("-" * 58)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(gerar_cenas())
