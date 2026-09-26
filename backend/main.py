from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.youtube_service import search_viral_videos, get_video_transcript
from backend.ai_service import analisar_e_criar_pacote_viral

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
    period: str = "all"  # "day" | "week" | "month" | "year" | "all"


class AnalysisRequest(BaseModel):
    titulo: str = ""
    descricao: str = ""
    transcricao: str
    duracao_segundos: int = 60  # 15 a 600 (5 min)


@app.get("/")
def read_root():
    return {"status": "Radar de Virais API está a funcionar!"}


@app.post("/api/search")
def search_videos(data: SearchRequest):
    try:
        videos = search_viral_videos(data.query, data.max_results, data.period)
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


@app.post("/api/analyze-transcript")
def analyze_transcript(data: AnalysisRequest):
    # Limita entre 15s e 5min para não gerar roteiros gigantes sem querer
    duracao = max(15, min(data.duracao_segundos, 600))
    try:
        pacote_gerado = analisar_e_criar_pacote_viral(
            data.titulo, data.descricao, data.transcricao, duracao
        )
        return {"script": pacote_gerado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
