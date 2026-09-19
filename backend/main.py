from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.youtube_service import search_viral_videos, get_video_transcript

app = FastAPI(title="Radar de Virais API")

# Configuração de CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str
    max_results: int = 10

@app.get("/")
def read_root():
    return {"status": "Radar de Virais API está a funcionar!"}

@app.post("/api/search")
def search_videos(data: SearchRequest):
    try:
        videos = search_viral_videos(data.query, data.max_results)
        return {"videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcript")
def get_transcript(data: dict):
    video_id = data.get("video_id")
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id é obrigatório")
    try:
        transcript = get_video_transcript(video_id)
        return {"transcript": transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))