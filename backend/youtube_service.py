import html
import json
import os
import re
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

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

# ---------------------------------------------------------------------------
# Fallback de transcricao: instancias Piped (gratuitas, sem chave de API).
# O YouTube bloqueia IPs de nuvem (429/captcha) - as instancias Piped pedem
# a legenda do lado delas e nos devolvem o conteudo pronto.
# ---------------------------------------------------------------------------
PIPED_INSTANCIAS = [
    "https://api.piped.private.coffee",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.reallyaweso.me",
    "https://api-piped.mha.fi",
]
IDIOMAS_PREF = ("pt-BR", "pt", "en")
_NAVEGADOR_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

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


def _transcript_piped(base: str, video_id: str, timeout: int = 12) -> str:
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


def get_video_transcript(video_id: str) -> str:
    """Busca a transcricao do video (pt-BR > pt > en).

    1) direto via youtube_transcript_api (funciona quando o IP nao esta bloqueado);
    2) se o YouTube bloquear o IP (429/captcha), tenta instancias Piped;
    3) se tudo falhar, levanta ValueError com o motivo + dica do modo manual.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,20}", video_id or ""):
        raise ValueError("ID de video invalido")

    erros = []

    # 1) busca direta
    if YouTubeTranscriptApi is not None:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=['pt', 'pt-BR', 'en']
            )
            texto = " ".join(t['text'] for t in transcript_list)
            if texto.strip():
                return texto
            erros.append("busca direta devolveu vazio")
        except Exception as e:
            primeira = str(e).strip().splitlines()
            erros.append(primeira[0] if primeira else type(e).__name__)
    else:
        erros.append("busca direta indisponivel (youtube_transcript_api nao instalado)")

    # 2) instancias Piped
    fonte_viva_sem_legenda = False
    for base in PIPED_INSTANCIAS:
        try:
            texto = _transcript_piped(base, video_id)
            if texto:
                return texto
            fonte_viva_sem_legenda = True   # instancia respondeu, mas sem legenda
        except Exception as e:
            erros.append(f"{base}: {str(e)[:90]}")

    detalhe = "; ".join(erros) if erros else "todas as fontes retornaram vazio"
    if fonte_viva_sem_legenda:
        # pelo menos uma instancia viva respondeu: o video nao tem legenda
        raise ValueError(
            "Este video nao tem legenda/transcricao disponivel. " + DICA_MANUAL)
    raise ValueError(
        "Nao consegui puxar a transcricao automatica (motivo: "
        + detalhe + "). " + DICA_MANUAL)
