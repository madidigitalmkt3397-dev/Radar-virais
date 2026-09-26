import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# A chave é lida de forma segura da variável de ambiente (nunca exposta no código)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def analisar_e_criar_pacote_viral(topico: str, formato: str, duracao: int):
    """
    Gera o roteiro, texto para narração e instruções de mídia visual (para a pasta banco_midia/)
    adaptados ao formato e à duração escolhidos.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt_sistema = (
        "Você é um especialista em criação de vídeos virais para redes sociais. "
        f"O vídeo deve ter o formato {formato} e uma duração aproximada de {duracao} segundos. "
        "Com base no tópico fornecido, devolva uma resposta organizada contendo: "
        "1. Roteiro dividido por cenas (com indicação do tempo de cada cena). "
        "2. Texto exato para a narração (sem excessos, ideal para o tempo estipulado). "
        "3. Sugestões de prompts visuais detalhados para cada cena (para o utilizador gerar a imagem/vídeo manualmente e colocar na pasta 'banco_midia/'). "
        "4. Indicações de onde colocar efeitos sonoros (ex: [Efeito: transição rápida], [Efeito: suspense])."
    )

    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=f"Tópico do vídeo: {topico}",
            config=types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                temperature=0.7,
            ),
        )
        
        return {
            "topico": topico,
            "formato": formato,
            "duracao_estimada": duracao,
            "conteudo_gerado": response.text,
            "instrucoes_fluxo": {
                "proximo_passo_midia": "Coloque os ficheiros gerados manualmente na pasta 'banco_midia/' nomeando-os por cena (ex: cena_1.mp4, cena_2.mp4).",
                "proximo_passo_audio": "Integrar biblioteca edge-tts para transformar o texto de narração em MP3."
            }
        }

    except Exception as e:
        raise Exception(f"Erro ao gerar pacote viral com Gemini: {str(e)}")
