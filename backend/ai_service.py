import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# A chave é lida de forma segura da variável de ambiente (nunca exposta no código)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Modelos por ordem de preferência. Se um estiver lotado (erro 503 do Google),
# o sistema tenta o próximo automaticamente — evita a falha que derrubava a API.
MODELOS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]

# Repetições por modelo em caso de 503/429 (sobra de demanda temporária)
TENTATIVAS_POR_MODELO = 2
ESPERA_ENTRE_TENTATIVAS = 2  # segundos

def montar_prompt_sistema(duracao_segundos: int) -> str:
    """
    Monta o prompt de acordo com a duração pedida.
    Regra de ouro: ~1 cena a cada 8 segundos de vídeo.
    """
    cenas_min = max(4, round(duracao_segundos / 12))
    cenas_max = max(cenas_min + 2, round(duracao_segundos / 7))

    return (
    "Você é um Diretor de Criação sênior e Estrategista de Conteúdo Viral para "
    "TikTok, YouTube Shorts e Instagram Reels. Analise o vídeo de referência fornecido "
    "e crie um pacote completo e original para um novo vídeo, inspirado na estrutura "
    "de sucesso dele, mas com conteúdo próprio (nunca copie literalmente).\n\n"
    "IDIOMA OBRIGATÓRIO: escreva 'titulo_otimizado', 'descricao_otimizada', 'gancho' e a "
    "'narracao' de TODAS as cenas SEMPRE em português do Brasil (pt-BR), independentemente "
    "do idioma do vídeo de referência. Única exceção: 'prompt_visual' continua em inglês, "
    "pois é uma instrução lida por IAs de imagem/vídeo (Midjourney, Runway, Sora).\n\n"
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
    f"Crie entre {cenas_min} e {cenas_max} cenas, cada uma com narração curta (1-3 frases), "
    f"pensando em um vídeo de aproximadamente {duracao_segundos} segundos no total.\n\n"
    "LEMBRETE FINAL: tudo em português do Brasil (pt-BR) — exceto prompt_visual (inglês)."
)


def _limpar_json(texto: str) -> str:
    """Remove blocos ```json ... ``` caso o modelo os inclua por engano."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.lower().startswith("json"):
            texto = texto[4:].strip()
    return texto


def analisar_e_criar_pacote_viral(
    titulo: str, descricao: str, transcricao: str, duracao_segundos: int = 60
):
    """
    Analisa um vídeo de referência (título, descrição, transcrição) e devolve
    um pacote ESTRUTURADO em JSON, pronto para alimentar o pipeline local de
    renderização (roteiro por cenas + prompt visual + sugestão de efeito sonoro).

    Tenta os modelos em sequência e repete em caso de 503 (demand alta),
    para não falhar quando um único modelo estiver lotado.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    contents = (
        f"--- VÍDEO DE REFERÊNCIA ---\n"
        f"Título: {titulo}\n"
        f"Descrição: {descricao}\n"
        f"Transcrição: {transcricao}\n"
        f"--- FIM ---"
    )

    ultimo_erro = ""
    ultimo_texto_bruto = ""

    for modelo in MODELOS:
        for tentativa in range(TENTATIVAS_POR_MODELO):
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=montar_prompt_sistema(duracao_segundos),
                        temperature=0.7,
                        response_mime_type="application/json",
                    ),
                )

                texto_resposta = (response.text or "").strip()
                if not texto_resposta:
                    ultimo_erro = f"{modelo}: resposta vazia da IA"
                    break  # tenta o próximo modelo

                ultimo_texto_bruto = texto_resposta
                pacote = json.loads(_limpar_json(texto_resposta))

                # Validação mínima da estrutura esperada pelo frontend
                if not isinstance(pacote, dict) or "cenas" not in pacote:
                    ultimo_erro = f"{modelo}: JSON sem a lista 'cenas'"
                    break  # tenta o próximo modelo

                print(f"[Gemini] Pacote gerado com {modelo} (tentativa {tentativa + 1})")
                return pacote

            except json.JSONDecodeError:
                # IA devolveu texto fora do formato: não adianta repetir o mesmo modelo
                ultimo_erro = f"{modelo}: a IA não devolveu JSON válido"
                break

            except Exception as e:
                erro = str(e)
                ultimo_erro = f"{modelo}: {erro}"

                # 503/429 = demanda alta do Google → espera e repete o mesmo modelo
                if "503" in erro or "429" in erro or "UNAVAILABLE" in erro.upper():
                    if tentativa < TENTATIVAS_POR_MODELO - 1:
                        print(f"[Gemini] {modelo} ocupado (503), nova tentativa em {ESPERA_ENTRE_TENTATIVAS}s...")
                        time.sleep(ESPERA_ENTRE_TENTATIVAS)
                        continue
                print(f"[Gemini] {modelo} falhou: {erro[:200]}")
                break  # erro diferente (ex.: chave inválida) → próximo modelo

    # Todos os modelos falharam: se ao menos temos texto bruto, devolve um pacote
    # de emergência que o frontend ainda consegue exibir, em vez de um 500 seco.
    if ultimo_texto_bruto:
        return {
            "titulo_otimizado": titulo,
            "descricao_otimizada": "",
            "gancho": "",
            "cenas": [],
            "erro_formatacao": "A IA não devolveu um JSON válido desta vez. Tente novamente.",
            "conteudo_bruto": ultimo_texto_bruto,
        }

    raise Exception(f"Erro ao gerar pacote viral com Gemini: {ultimo_erro}")
