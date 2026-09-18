import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")

def search_viral_videos(query: str, max_results: int = 5):
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY não encontrada no arquivo .env")

    youtube = build("youtube", "v3", developerKey=API_KEY)

    # 1. Busca os vídeos pelo termo / nicho
    search_response = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=max_results,
        type="video",
        order="viewCount"
    ).execute()

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
            "tags": snippet.get("tags", []),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement_rate": engagement_rate
        })

    return videos

def get_video_transcript(video_id: str):
    try:
        # Usa a instância da API compatível com as versões recentes da biblioteca
        yt_api = YouTubeTranscriptApi()
        transcript_list = yt_api.fetch(video_id)
        
        # Extrai e une o texto de cada trecho da legenda
        transcript_text = " ".join([t.text for t in transcript_list])
        return transcript_text
    except Exception as e:
        return f"Transcrição indisponível ou desativada para este vídeo. (Detalhe: {str(e)})"