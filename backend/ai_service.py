import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# A chave é lida de forma segura da variável de ambiente (nunca exposta no código)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def analisar_e_criar_pacote_viral(titulo: str, descricao: str, transcricao: str):
    """
    Analisa um vídeo de referência (título, descrição, transcrição) e devolve
    um pacote ESTRUTURADO em JSON, pronto para alimentar o pipeline local de
    renderização (roteiro por cenas + prompt visual + sugestão de efeito sonoro).
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt_sistema = (
        "Você é um Diretor de Criação sênior e Estrategista de Conteúdo Viral para "
        "TikTok, YouTube Shorts e Instagram Reels. Analise o vídeo de referência fornecido "
        "e crie um pacote completo e original para um novo vídeo, inspirado na estrutura "
        "de sucesso dele, mas com conteúdo próprio (nunca copie literalmente).\n\n"
        "Responda ESTRITAMENTE em JSON válido, seguindo exatamente este formato "
        "(sem markdown, sem texto fora do JSON):\n"
        "{\n"
        '  "titulo_otimizado": "string",\n'
        '  "descricao_otimizada": "string",\n'
        '  "gancho": "string (os 3 primeiros segundos exatos da narração)",\n'
        '  "cenas": [\n'
        "    {\n"
        '      "numero": 1,\n'
        '      "narracao": "texto exato para a narração desta cena",\n'
        '      "prompt_visual": "prompt em inglês, detalhado, para gerar a imagem/vídeo desta cena em uma IA (Midjourney, Runway, Sora, etc.)",\n'
        '      "efeito_sonoro_sugerido": "palavra-chave curta do efeito (ex: whoosh, ding, suspense, aplausos) ou null se nenhum"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Crie entre 4 e 8 cenas, cada uma com narração curta (1-3 frases), pensando em um vídeo "
        "de 30 a 60 segundos no total."
    )

    contents = (
        f"--- VÍDEO DE REFERÊNCIA ---\n"
        f"Título: {titulo}\n"
        f"Descrição: {descricao}\n"
        f"Transcrição: {transcricao}\n"
        f"--- FIM ---"
    )

    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

        texto_resposta = response.text.strip()
        # Segurança extra: remove blocos ```json ... ``` caso o modelo os inclua por engano
        if texto_resposta.startswith("```"):
            texto_resposta = texto_resposta.strip("`")
            if texto_resposta.lower().startswith("json"):
                texto_resposta = texto_resposta[4:].strip()

        try:
            pacote = json.loads(texto_resposta)
        except json.JSONDecodeError:
            # Se por algum motivo o modelo não devolveu JSON válido, não quebra:
            # devolve o texto bruto num formato que o frontend ainda consegue mostrar.
            pacote = {
                "titulo_otimizado": titulo,
                "descricao_otimizada": "",
                "gancho": "",
                "cenas": [],
                "erro_formatacao": "A IA não devolveu um JSON válido desta vez.",
                "conteudo_bruto": texto_resposta,
            }

        return pacote

    except Exception as e:
        raise Exception(f"Erro ao gerar pacote viral com Gemini: {str(e)}")
