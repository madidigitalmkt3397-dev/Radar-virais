import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
except ImportError:  # ambiente local sem os pacotes do backend
    def load_dotenv():
        return None

try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

# ---------------------------------------------------------------------------
# Busca de transcricao - cadeia de fontes gratuitas (sem chave propria):
#   1) youtube-transcript.ai - a busca acontece NO SERVIDOR deles, entao
#      nao depende do IP do Render (hoje, unico caminho que atravessa o
#      bloqueio do YouTube contra IP de nuvem);
#   2) API interna Innertube (cliente ANDROID) - contorna o captcha do site;
#   3) youtube-transcript-green (vercel) - cache parcial, reserva;
#   4) instancias Piped - rede de seguranca.
# ---------------------------------------------------------------------------
PIPED_INSTANCIAS = [
    "https://api.piped.private.coffee",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.reallyaweso.me",
]
IDIOMAS_PREF = ("pt-BR", "pt", "en")
_NAVEGADOR_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# A API Innertube e chamada SEM chave (?key=): a chave publica do player do
# YouTube e opcional e o GitHub marca ela como segredo - se a Google revogar
# por exposicao, requests com chave quebram; sem chave continuam funcionando.
# hosts em ordem de preferencia: a API do Google costuma bloquear menos
# IP de nuvem do que o youtube.com
INNERTUBE_HOSTS = (
    "https://youtubei.googleapis.com",
    "https://www.googleapis.com",
    "https://www.youtube.com",
)

# Variantes de cliente (versoes atuais conforme o yt-dlp), na ordem em que a
# cadeia tenta. O IP de nuvem recebe LOGIN_REQUIRED em versoes antigas, por
# isso a lista traz android e ios atualizados com o User-Agent proprio de cada
# app. (WEB/MWEB/TVHTML5 -> UNPLAYABLE; ANDROID_VR/VISIONOS -> LOGIN_REQUIRED.)
INNERTUBE_VARIANTES = (
    ("android_21", {
        "clientName": "ANDROID", "clientVersion": "21.26.364",
        "androidSdkVersion": 30, "osName": "Android", "osVersion": "11",
        "hl": "pt", "gl": "BR",
    }, "3",
        "com.google.android.youtube/21.26.364 (Linux; U; Android 11) gzip"),
    ("ios_21", {
        "clientName": "IOS", "clientVersion": "21.26.4",
        "deviceMake": "Apple", "deviceModel": "iPhone16,2",
        "osName": "iPhone", "osVersion": "18.3.2.22D82",
        "hl": "pt", "gl": "BR",
    }, "5",
        "com.google.ios.youtube/21.26.4 (iPhone16,2; U; CPU iOS 18_3_2 "
        "like Mac OS X;)"),
    ("android_20", {
        "clientName": "ANDROID", "clientVersion": "20.10.38",
        "androidSdkVersion": 30, "hl": "pt", "gl": "BR",
    }, "3", _NAVEGADOR_UA),
)
ORCAMENTO_TRANSCRICAO = 15.0   # segundos maximos de toda a cadeia
# O youtubei bloqueia IP de nuvem em escalada (LOGIN_REQUIRED -> 403 ->
# timeout) e CADA chamada alimenta o bloqueio. Parar apos N falhas de
# transporte seguidas evita martelar o endpoint durante uma restricao.
MAX_FALHAS_REDE = 2

DICA_MANUAL = (
    'Use a secao "Insercao Manual" do site: abra o video no YouTube, '
    'clique em "... > Mostrar transcricao", copie o texto e cole la.'
)

# Períodos aceitos pelo front-end: "day", "week", "month", "year", "all"
def _calcular_published_after(period: str):
    if not period or period == "all":
        return None

    agora = datetime.now(timezone.utc)
    janelas = {
        "day": timedelta(days=1),
        "week": timedelta(days=7),
        "month": timedelta(days=30),
        "year": timedelta(days=365),
    }
    delta = janelas.get(period)
    if not delta:
        return None

    data_limite = agora - delta
    # Formato RFC 3339 exigido pela API do YouTube (ex: 2026-08-01T00:00:00Z)
    return data_limite.strftime('%Y-%m-%dT%H:%M:%SZ')


def search_viral_videos(query: str, max_results: int = 5, period: str = "all"):
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY não encontrada nas variáveis de ambiente")
    if build is None:
        raise ValueError("google-api-python-client não instalado neste ambiente")

    try:
        youtube = build("youtube", "v3", developerKey=API_KEY)

        # 1. Busca os vídeos pelo termo / nicho, dentro do período escolhido
        search_kwargs = dict(
            q=query,
            part="snippet",
            maxResults=max_results,
            type="video",
            order="viewCount"  # dentro do período, prioriza os mais vistos = "viralizando"
        )
        published_after = _calcular_published_after(period)
        if published_after:
            search_kwargs["publishedAfter"] = published_after

        search_response = youtube.search().list(**search_kwargs).execute()

        items = search_response.get("items", [])
        video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]

        if not video_ids:
            return []

        # 2. Busca detalhes estatísticos em lote
        stats_response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids)
        ).execute()

        videos = []
        for item in stats_response.get("items", []):
            vid_id = item["id"]
            snippet = item["snippet"]
            stats = item.get("statistics", {})

            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))

            engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0

            videos.append({
                "id": vid_id,
                "title": snippet.get("title", "Sem título"),
                "channelTitle": snippet.get("channelTitle", "Canal desconhecido"),
                "publishedAt": snippet.get("publishedAt", ""),
                "description": snippet.get("description", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": engagement_rate
            })

        return videos

    except Exception as e:
        print(f"Erro na API do YouTube: {str(e)}")
        return []


def _http_get(url: str, timeout: int = 12) -> str:
    """GET simples fingindo ser um navegador (algumas instancias bloqueiam UA padrao)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": _NAVEGADOR_UA,
        "Accept-Language": "pt-BR,pt,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_post_json(url: str, payload: dict, headers: dict = None,
                    timeout: int = 15) -> dict:
    """POST JSON simples (usado na API interna Innertube)."""
    cabecais = {"Content-Type": "application/json", "User-Agent": _NAVEGADOR_UA}
    if headers:
        cabecais.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=cabecais, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _extrair_texto_legenda(corpo: str) -> str:
    """Converte legenda (JSON3 / TTML / WebVTT / SRT) em texto puro."""
    if not corpo or not corpo.strip():
        return ""
    corpo = corpo.strip()
    if corpo.startswith("{"):
        # JSON3 do YouTube
        dados = json.loads(corpo)
        partes = [seg.get("utf8", "")
                  for ev in dados.get("events", [])
                  for seg in ev.get("segs", [])]
        texto = " ".join(partes)
    elif corpo.startswith("WEBVTT"):
        # WebVTT: ignora cabecalhos e marcas de tempo
        linhas = [ln for ln in corpo.splitlines()
                  if not ln.startswith(("WEBVTT", "NOTE", "STYLE", "REGION"))
                  and "-->" not in ln and not ln.strip().isdigit()]
        texto = " ".join(linhas)
    elif "<" in corpo:
        # TTML/XML (formato devolvido pelo proxy do Piped)
        blocos = re.findall(r"<p[^>]*>(.*?)</p>", corpo, re.DOTALL)
        bruto = " ".join(blocos) if blocos else corpo
        bruto = re.sub(r"<br\s*/?>", " ", bruto)
        bruto = re.sub(r"<[^>]+>", " ", bruto)
        texto = html.unescape(bruto)
    else:
        # SRT puro
        linhas = [ln for ln in corpo.splitlines()
                  if "-->" not in ln and not ln.strip().isdigit()
                  and not ln.startswith("NOTE")]
        texto = " ".join(linhas)
    return re.sub(r"\s+", " ", texto).strip()


def _transcript_innertube(video_id: str, timeout: int = 8, relatorio: list = None,
                          orcamento: bool = True, todas: bool = False):
    """Transcricao pela API interna do YouTube (Innertube).

    Tenta as variantes de cliente de INNERTUBE_VARIANTES (android e ios
    atualizados, cada um com o User-Agent do proprio app) nos hosts de
    INNERTUBE_HOSTS. Devolve o texto; None quando o video realmente nao tem
    legenda; levanta Exception quando nenhuma variante funciona.
    Cada tentativa entra em `relatorio` (fonte/status/ms/chars) se informado.

    `orcamento=False` testa tudo mesmo passado o tempo limite e `todas=True`
    continua apos o primeiro sucesso - usado pelo diagnostico, que quer saber
    o que funciona de verdade no servidor.
    """
    ultimo_erro = "nenhuma variante testada"
    visitor = None        # X-Goog-Visitor-Id reaproveitado entre tentativas
    texto_ok = None       # primeira legenda obtida
    sem_legenda = False   # alguma variante viva respondeu sem trilhas
    parar = False         # parada ja decidida (relatorio recebe 1 aviso so)
    falhas_rede = 0       # excecoes de transporte seguidas (403/timeout/dns)
    t_ini = time.monotonic()

    for rot, cli, numero, ua in INNERTUBE_VARIANTES:
        if parar:
            break
        # no modo cadeia, para quando o orcamento acabou
        if orcamento and time.monotonic() - t_ini > ORCAMENTO_TRANSCRICAO:
            ultimo_erro = "orcamento de tempo esgotado (innertube)"
            if relatorio is not None:
                relatorio.append({"fonte": "innertube",
                                  "status": "pulado (orcamento)",
                                  "ms": 0, "chars": 0})
            parar = True
            break
        for host in INNERTUBE_HOSTS:
            if parar:
                break
            # corte tambem no meio da variante (hosts podem pendurar 6s+ cada)
            if orcamento and time.monotonic() - t_ini > ORCAMENTO_TRANSCRICAO:
                ultimo_erro = "orcamento de tempo esgotado (innertube)"
                if relatorio is not None:
                    relatorio.append({"fonte": "innertube",
                                      "status": "pulado (orcamento)",
                                      "ms": 0, "chars": 0})
                parar = True
                break
            origem = f"innertube:{rot}@{host.split('//')[1]}"
            t0 = time.monotonic()
            try:
                cabecais = {
                    "X-Youtube-Client-Name": numero,
                    "X-Youtube-Client-Version": cli["clientVersion"],
                    "User-Agent": ua,
                }
                if visitor:
                    cabecais["X-Goog-Visitor-Id"] = visitor
                pr = _http_post_json(
                    f"{host}/youtubei/v1/player?prettyPrint=false",
                    {
                        "context": {"client": cli},
                        "videoId": video_id,
                        "contentCheckOk": True,
                        "racyCheckOk": True,
                    },
                    cabecais,
                    timeout=timeout,
                )
                ms = int((time.monotonic() - t0) * 1000)
                falhas_rede = 0   # a camada de aplicacao respondeu
                vd = (pr.get("responseContext") or {}).get("visitorData")
                if vd:
                    visitor = vd
                status = pr.get("playabilityStatus", {}).get("status")
                if status not in (None, "OK"):
                    ultimo_erro = f"{origem}: status {status}"
                    if relatorio is not None:
                        relatorio.append({"fonte": origem, "status": status,
                                          "ms": ms, "chars": 0})
                    continue
                trilhas = (pr.get("captions", {})
                             .get("playerCaptionsTracklistRenderer", {})
                             .get("captionTracks", []))
                if not trilhas:
                    # respondeu com status OK e o video nao tem legenda
                    sem_legenda = True
                    if relatorio is not None:
                        relatorio.append({"fonte": origem,
                                          "status": "ok, sem legenda",
                                          "ms": ms, "chars": 0})
                    if not todas:
                        return None
                    continue
                if texto_ok is None:
                    # prefere pt-BR > pt > en > a primeira disponivel
                    alvo = None
                    for cod in IDIOMAS_PREF:
                        alvo = next((t for t in trilhas
                                     if (t.get("languageCode") or "").lower()
                                     .startswith(cod.lower())), None)
                        if alvo:
                            break
                    alvo = alvo or trilhas[0]
                    legenda = _http_get(alvo["baseUrl"] + "&fmt=json3",
                                        timeout=timeout)
                    texto = _extrair_texto_legenda(legenda)
                    ms = int((time.monotonic() - t0) * 1000)
                    if texto:
                        texto_ok = texto
                    if relatorio is not None:
                        relatorio.append({
                            "fonte": origem,
                            "status": "ok" if texto else "legenda vazia",
                            "ms": ms, "chars": len(texto)})
                    ultimo_erro = (f"{origem}: legenda vazia" if not texto
                                   else ultimo_erro)
                else:
                    # ja temos a legenda: so registra que esta variante tb funciona
                    if relatorio is not None:
                        relatorio.append({
                            "fonte": origem,
                            "status": f"ok ({len(trilhas)} trilhas)",
                            "ms": ms, "chars": 0})
                if texto_ok and not todas:
                    return texto_ok
            except Exception as e:
                ms = int((time.monotonic() - t0) * 1000)
                motivo = f"{type(e).__name__}: {str(e)[:70]}"
                if relatorio is not None:
                    relatorio.append({"fonte": origem, "status": motivo,
                                      "ms": ms, "chars": 0})
                falhas_rede += 1
                ultimo_erro = f"{origem}: {motivo}"
                # so no modo cadeia: N falhas de transporte seguidas param a
                # matriz inteira para nao martelar o endpoint (cada chamada
                # durante um bloqueio faz o YouTube endurecer o bloqueio)
                if orcamento and falhas_rede >= MAX_FALHAS_REDE:
                    parar = True
                    if relatorio is not None:
                        relatorio.append({
                            "fonte": "innertube",
                            "status": (f"interrompido apos {falhas_rede} "
                                       "falhas de rede seguidas"),
                            "ms": 0, "chars": 0})
                    break

    if texto_ok:
        return texto_ok
    if sem_legenda:
        return None
    raise RuntimeError(ultimo_erro)


def _transcript_piped(base: str, video_id: str, timeout: int = 6) -> str:
    """Pede a transcricao a uma instancia Piped. Devolve '' se nao houver legenda."""
    dados = json.loads(_http_get(f"{base}/streams/{video_id}", timeout=timeout))
    trilhas = dados.get("subtitles") or []
    if not trilhas:
        return ""
    # prefere pt-BR > pt > en > a primeira disponivel
    alvo = None
    for cod in IDIOMAS_PREF:
        alvo = next((t for t in trilhas
                     if (t.get("code") or "").lower().startswith(cod.lower())), None)
        if alvo:
            break
    alvo = alvo or trilhas[0]
    if not alvo.get("url"):
        raise ValueError("instancia devolveu legenda sem url")
    texto = _extrair_texto_legenda(_http_get(alvo["url"], timeout=timeout))
    if not texto:
        raise ValueError("conteudo de legenda vazio na fonte")
    return texto


def _texto_do_markdown_ia(corpo: str) -> str:
    """Texto puro do markdown do youtube-transcript.ai: cabecalho
    `# Transcript:` + secao `## Transcript` com marcas `[m:ss]` por linha."""
    if "## Transcript" in corpo:
        corpo = corpo.split("## Transcript", 1)[1]
    linhas = []
    for bruto in corpo.splitlines():
        ln = bruto.strip()
        if not ln or ln.startswith("#"):
            continue
        ln = re.sub(r"^\[[\d:]+\]\s*", "", ln)     # marca de tempo
        linhas.append(ln)
    return re.sub(r"\s+", " ", " ".join(linhas)).strip()


def _transcript_ia(video_id: str, timeout: int = 6) -> str:
    """Transcricao via youtube-transcript.ai (gratis, sem chave e sem cadastro).

    GET https://youtube-transcript.ai/transcript/{ID}.txt - a fonte busca a
    legenda no servidor DELA, por isso funciona mesmo com o YouTube
    bloqueando o IP de nuvem do Render. Comportamento medido em teste:
      - User-Agent padrao do urllib leva 403: usa o UA de navegador;
      - 200 + `# Transcript:` = transcript real (~0,5 s, ~4 KB);
      - `# No captions available` = o video nao tem legenda (devolve '');
      - 429 ou corpo ~240 B com "high volume" = rate limit deles (janela de
        ~15-20 min): LANCA erro para a cadeia tentar a proxima fonte.
    """
    corpo = _http_get(
        f"https://youtube-transcript.ai/transcript/{video_id}.txt",
        timeout=timeout,
    )
    c = corpo.lower()
    if "high volume" in c or "rate limited" in c:
        raise ValueError("rate limit do youtube-transcript.ai (~15-20 min)")
    if "# no captions available" in c:
        return ""            # fonte viva respondeu: o video nao tem legenda
    if "# transcript:" in c and "## transcript" in c:
        texto = _texto_do_markdown_ia(corpo)
        if texto:
            return texto
        raise ValueError("youtube-transcript.ai: texto vazio")
    raise ValueError(
        f"youtube-transcript.ai: formato inesperado ({len(corpo)} bytes)")


def _transcript_green(video_id: str, timeout: int = 8) -> str:
    """Reserva: youtube-transcript-green.vercel.app (JSON com timestamps).

    POST /api/transcript {"videoUrl": ..., "format": "json"} - gratis e sem
    chave, mas so responde para videos que ja passaram por la (cache deles).
    A ausencia de resposta ("No transcript available") NAO prova que o
    video nao tem legenda, entao aqui erro vira excecao (fonte falhou) e
    nunca "sem legenda".
    """
    url = "https://youtube-transcript-green.vercel.app/api/transcript"
    try:
        dados = _http_post_json(
            url,
            {"videoUrl": f"https://www.youtube.com/watch?v={video_id}",
             "format": "json"},
            timeout=timeout,
        )
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(
                e.read().decode("utf-8", "replace")).get("error", "")
        except Exception:
            msg = ""
        raise ValueError(f"green: {msg[:70] or e}") from None
    bruto = dados.get("raw") or []
    if not bruto and isinstance(dados.get("data"), str):
        try:
            bruto = json.loads(dados["data"])
        except Exception:
            bruto = []
    partes = [str(s.get("text", "")).strip()
              for s in bruto if isinstance(s, dict)]
    texto = re.sub(r"\s+", " ", " ".join(p for p in partes if p)).strip()
    if texto:
        return texto
    raise ValueError(f"green: {str(dados.get('error') or 'sem texto')[:70]}")


def get_video_transcript(video_id: str, relatorio: list = None) -> str:
    """Busca a transcricao do video (pt-BR > pt > en).

    Cadeia de fontes (todas gratuitas, sem chave propria):
    1) youtube-transcript.ai - busca no servidor deles (independe do IP);
    2) API interna Innertube (variantes android/ios atuais) - nao cai no captcha;
    3) youtube-transcript-green - cache parcial, reserva;
    4) instancias Piped - 1 rodada, rede de seguranca.
    Toda a cadeia tem orcamento de ORCAMENTO_TRANSCRICAO segundos; se tudo
    falhar, levanta ValueError com o motivo (fonte + status + ms) + dica
    do modo manual. `relatorio` (se informado) recebe cada tentativa.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,20}", video_id or ""):
        raise ValueError("ID de video invalido")

    t_ini = time.monotonic()
    if relatorio is None:
        relatorio = []       # fonte/status/ms/chars de cada tentativa
    sem_legenda = False

    # 1) youtube-transcript.ai - server-side (~0,5s), nao depende do IP
    t0 = time.monotonic()
    try:
        texto = _transcript_ia(video_id)
        relatorio.append({"fonte": "transcript.ai",
                          "status": "ok" if texto else "ok, sem legenda",
                          "ms": int((time.monotonic() - t0) * 1000),
                          "chars": len(texto)})
        if texto:
            return texto
        sem_legenda = True   # fonte viva respondeu: o video nao tem legenda
    except Exception as e:
        relatorio.append({"fonte": "transcript.ai",
                          "status": f"{type(e).__name__}: {str(e)[:70]}",
                          "ms": int((time.monotonic() - t0) * 1000),
                          "chars": 0})

    # 2) API interna Innertube (host da API do Google, depois youtube.com)
    if not sem_legenda:
        try:
            texto = _transcript_innertube(video_id, relatorio=relatorio)
            if texto:
                return texto
            sem_legenda = True   # fonte viva respondeu: o video nao tem legenda
        except Exception:
            pass   # cada tentativa ja entrou em `relatorio` com status e ms

    # 3) youtube-transcript-green - so enquanto houver orcamento
    if not sem_legenda:
        if time.monotonic() - t_ini > ORCAMENTO_TRANSCRICAO:
            relatorio.append({"fonte": "transcript-green",
                              "status": "pulado (orcamento)",
                              "ms": 0, "chars": 0})
        else:
            t0 = time.monotonic()
            try:
                texto = _transcript_green(video_id)
                relatorio.append({"fonte": "transcript-green",
                                  "status": "ok",
                                  "ms": int((time.monotonic() - t0) * 1000),
                                  "chars": len(texto)})
                if texto:
                    return texto
            except Exception as e:
                relatorio.append(
                    {"fonte": "transcript-green",
                     "status": f"{type(e).__name__}: {str(e)[:70]}",
                     "ms": int((time.monotonic() - t0) * 1000), "chars": 0})

    # 4) instancias Piped - so enquanto houver orcamento de tempo
    for base in PIPED_INSTANCIAS:
        if sem_legenda:
            break
        if time.monotonic() - t_ini > ORCAMENTO_TRANSCRICAO:
            relatorio.append({"fonte": f"piped:{base}", "status": "pulado (orcamento)",
                              "ms": 0, "chars": 0})
            continue
        t0 = time.monotonic()
        try:
            texto = _transcript_piped(base, video_id)
            relatorio.append({"fonte": f"piped:{base}",
                              "status": "ok" if texto else "ok, sem legenda",
                              "ms": int((time.monotonic() - t0) * 1000),
                              "chars": len(texto)})
            if texto:
                return texto
            sem_legenda = True   # instancia viva sem legenda
        except Exception as e:
            relatorio.append({"fonte": f"piped:{base}",
                              "status": f"{type(e).__name__}: {str(e)[:70]}",
                              "ms": int((time.monotonic() - t0) * 1000), "chars": 0})

    total = int((time.monotonic() - t_ini) * 1000)
    detalhe = "; ".join(
        f"{r['fonte']}={r['status']} em {r['ms']}ms" for r in relatorio
    ) or "nenhuma fonte testada"
    detalhe += f" | total {total}ms"
    if sem_legenda:
        # pelo menos uma fonte viva respondeu: o video nao tem legenda
        raise ValueError(
            "Este video nao tem legenda/transcricao disponivel. " + DICA_MANUAL)
    raise ValueError(
        "Nao consegui puxar a transcricao automatica (motivo: "
        + detalhe + "). " + DICA_MANUAL)


def _sonda_oembed(video_id: str, timeout: int = 8) -> dict:
    """Sonda de contexto: o endpoint publico oEmbed do YouTube.

    Nao busca legenda nenhuma - serve para saber se o DOMINIO youtube.com
    responde do servidor: 200 = transporte OK (logo o bloqueio e especifico
    da Innertube); 403/429/timeout = o dominio inteiro esta bloqueado para
    este IP e nenhuma fonte direta vai funcionar.
    """
    t0 = time.monotonic()
    url = ("https://www.youtube.com/oembed?format=json&url=https%3A%2F%2F"
           "www.youtube.com%2Fwatch%3Fv%3D" + video_id)
    try:
        corpo = _http_get(url, timeout=timeout)
        try:
            titulo = json.loads(corpo).get("title", "")
        except Exception:
            titulo = ""
        return {"status": 200, "ms": int((time.monotonic() - t0) * 1000),
                "titulo": titulo[:80]}
    except Exception as e:
        return {"status": f"{type(e).__name__}: {str(e)[:70]}",
                "ms": int((time.monotonic() - t0) * 1000), "titulo": ""}


def diagnosticar_transcript(video_id: str, completo: bool = False) -> dict:
    """Diagnostico da busca de transcricao a partir do servidor (Render).

    modo leve (padrao): roda a MESMA cadeia da producao, registrando cada
    tentativa, + a sonda oEmbed de contexto - poucas requisicoes.
    modo completo (completo=True): testa TODAS as variantes Innertube x
    hosts e TODOS os Piped mesmo ja tendo achado a legenda - muitas
    requisicoes, use so para investigacao.

    GET /api/diag-transcript?video_id=XXX[&completo=1]
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,20}", video_id or ""):
        return {"erro": "ID de video invalido"}

    t_ini = time.monotonic()
    relatorio = []       # fonte/status/ms/chars de cada tentativa
    texto = None
    erro = None

    oembed = _sonda_oembed(video_id)

    if completo:
        try:
            texto = _transcript_innertube(video_id, relatorio=relatorio,
                                          orcamento=False, todas=True)
        except Exception as e:
            erro = str(e)[:200]
        # todos os Piped tambem, mesmo ja tendo legenda
        for base in PIPED_INSTANCIAS:
            t0 = time.monotonic()
            try:
                t2 = _transcript_piped(base, video_id)
                relatorio.append({"fonte": f"piped:{base}",
                                  "status": "ok" if t2 else "ok, sem legenda",
                                  "ms": int((time.monotonic() - t0) * 1000),
                                  "chars": len(t2)})
                if t2:
                    texto = texto or t2
            except Exception as e:
                relatorio.append({"fonte": f"piped:{base}",
                                  "status": f"{type(e).__name__}: {str(e)[:70]}",
                                  "ms": int((time.monotonic() - t0) * 1000),
                                  "chars": 0})
    else:
        try:
            texto = get_video_transcript(video_id, relatorio=relatorio)
        except ValueError as e:
            erro = str(e)[:400]

    return {
        "video_id": video_id,
        "modo": "completo" if completo else "leve",
        "oembed": oembed,
        "tentativas": relatorio,
        "ok": bool(texto),
        "chars": len(texto or ""),
        "amostra": (texto or "")[:120],
        "erro": erro,
        "total_ms": int((time.monotonic() - t_ini) * 1000),
    }
