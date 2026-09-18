from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_service import search_viral_videos, get_video_transcript

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RadarRequest(BaseModel):
    nicho: str
    palavra_chave: str
    periodo: str
    quantidade: int

class TranscriptRequest(BaseModel):
    video_id: str

@app.post("/api/radar")
def radar_virais(data: RadarRequest):
    try:
        query_completa = f"{data.nicho} {data.palavra_chave}"
        videos_brutos = search_viral_videos(query=query_completa, max_results=data.quantidade)
        
        videos_formatados = []
        for v in videos_brutos:
            videos_formatados.append({
                "id": v["id"],
                "titulo": v["title"],
                "canal": v["channelTitle"],
                "publishedAt": v["publishedAt"],
                "thumbnail": v["thumbnail"],
                "url": f"https://www.youtube.com/watch?v={v['id']}",
                "views": v["views"],
                "likes": v["likes"],
                "comments": v["comments"],
                "engagement_rate": v["engagement_rate"]
            })

        return {"videos": videos_formatados}
    except Exception as e:
        print(f"Erro no servidor: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcript")
def obter_transcricao(data: TranscriptRequest):
    try:
        texto = get_video_transcript(data.video_id)
        return {"video_id": data.video_id, "transcricao": texto}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))