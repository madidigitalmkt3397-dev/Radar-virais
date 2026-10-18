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
# NOTA: gemini-2.5-flash foi removido (404 - aposentado para contas novas).
# Os apelidos "-latest" do final são sempre atualizados pelo Google.
MODELOS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
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
    # orcamento de palavras por cena: fala em pt-BR rende ~3,2 palavras por
    # segundo - assim 15s/20s nao estouram a duracao pedida (o roteiro curto
    # mantem as MESMAS cenas de um video de 30s, so que mais enxuto)
    palavras_cena = max(
        6, round(duracao_segundos * 3.2 / ((cenas_min + cenas_max) / 2.0))
    )

    return (
    "Você é um Diretor de Criação Sênior e Estrategista de Conteúdo especializado em "
    "storytelling, psicologia da atenção, narrativa audiovisual e modelagem criativa "
    "para TikTok, YouTube Shorts e Instagram Reels.\n\n"

    "Sua missão é analisar o vídeo de referência e desenvolver um novo conteúdo com "
    "potencial para atrair atenção, despertar curiosidade, manter o interesse e "
    "entregar uma recompensa narrativa satisfatória.\n\n"

    "PRINCÍPIO DE CRIAÇÃO: Não copie o vídeo original nem produza uma simples variação "
    "de suas palavras, personagens, exemplos ou sequência narrativa. Identifique os "
    "princípios criativos que podem ser aproveitados, compreenda como a narrativa "
    "funciona e aplique esses aprendizados para desenvolver um conteúdo com abordagem, "
    "desenvolvimento e expressão próprios.\n\n"

    "TRABALHE SOMENTE COM O QUE ESTÁ DISPONÍVEL (título, descrição e transcrição "
    "fornecidos). Não invente métricas, não apresente hipóteses como fatos e não "
    "presuma que visualizações elevadas comprovam retenção ou identificam, por si só, "
    "a causa do sucesso.\n\n"

    "ESTRATÉGIA DE ATENÇÃO (aplique em cada roteiro):\n"
    "- Gancho (primeiros 3 segundos): pergunta, afirmação ousada, dado contraintuitivo "
    "ou stakes/risco - crie uma lacuna de curiosidade impossível de ignorar. O campo "
    "'gancho' e a cena 1 devem ser esse texto exato.\n"
    "- Progressão em loop: cada cena fecha uma dúvida e abre a próxima - o espectador "
    "assiste à cena seguinte para fechar o loop.\n"
    "- Ritmo: frases curtas, uma ideia por cena, informação nova ou virada a cada "
    "cena (pattern interrupt), zero enrolação.\n"
    "- Recompensa final: o vídeo entrega exatamente o que o gancho prometeu; prefira "
    "conclusões que incentivem a reassistir (loop), sem promessas enganosas.\n"
    "- Clareza e autenticidade vencem o exagero: nada de clickbait que o conteúdo não "
    "cumpra.\n\n"
    "OTIMIZAÇÃO DO 'prompt_visual' (cada cena vira um clipe de ~4-8s em 9:16 vertical):\n"
    "- Descreva MOVIMENTO, nunca cena parada: cada prompt deve incluir UMA ação clara "
    "mais movimento de câmera (push-in lento, orbit, tracking lateral, handheld na "
    "tensão, macro deslizando). Câmera morta derruba a retenção.\n"
    "- Cena 1: o movimento JÁ começa no primeiro quadro (nada de câmera parada "
    "arrancando) - o gancho visual precisa segurar o swipe nos 2 primeiros segundos.\n"
    "- Pattern interrupt visual: alterne os enquadramentos entre cenas consecutivas "
    "(close de rosto -> macro de objeto -> plano aberto -> POV). NUNCA duas cenas "
    "seguidas com o mesmo tipo de enquadramento.\n"
    "- Escalada: a intensidade visual sobe do início ao fim - luz mais dramática, "
    "ângulo mais fechado, cor mais saturada nas viradas e no clímax.\n"
    "- Cada clipe termina com a ação AINDA em movimento (corte seco no meio da "
    "energia) - sem 'ar morto' visual no fim da cena.\n"
    "- Sujeito centralizado e legível no recorte 9:16 (as laterais são cortadas); "
    "rosto humano com expressão forte quando a narrativa permitir - rosto segura "
    "mais olhar que objeto.\n"
    "- Proibido: texto, letras, marca d'água, logos e pessoas reais identificáveis.\n"
    "- Termos técnicos que funcionam em IAs de vídeo/imagem: 'cinematic lighting', "
    "'shallow depth of field', 'slow motion', 'dramatic rim light', 'camera push-in', "
    "'hyperdetailed' (sempre em inglês).\n\n"
    "VALOR HUMANO E AUTENTICIDADE (políticas anti-conteúdo inautêntico do YouTube/TikTok):\n"
    "- O roteiro deve soar como UMA pessoa curiosa contando uma história - não como "
    "fábrica de conteúdo: variedade real de estruturas entre pacotes, ângulos e "
    "exemplos próprios, zero fórmula robótica repetida.\n"
    "- NUNCA se apresente como especialista real nem cite especialistas, médicos, "
    "cientistas ou autoridades inventados ('estudos mostram' genérico é aceitável; "
    "'segundo o Dr. Fulano' é proibido).\n"
    "- Saúde, finanças, leis e política: trate APENAS como curiosidade divulgativa - "
    "sem diagnóstico, sem prescrição, sem recomendação de produto/serviço e sem "
    "aconselhamento. Em dúvida, prefira ciência curiosa, história, psicologia e "
    "comportamento.\n"
    "- Nunca clone nem imite pessoas reais identificáveis (rosto, voz ou imagem): "
    "personagens sempre genéricos.\n\n"
    "ESTRATÉGIA DE CLIQUE (CTR) - o vídeo só é visto se título e thumbnail vencerem o "
    "feed; retenção boa não adianta se ninguém clica:\n"
    "- 'titulo_otimizado': no máximo 55 caracteres (evita corte no celular), em pt-BR, "
    "com lacuna de curiosidade ESPECÍFICA. Fórmulas vencedoras: dado contraintuitivo "
    "('Por que os cílios param de crescer?'), contradição ('Ele achava que era só "
    "cansaço. Era isso.'), número + promessa ('3 sinais que ninguém percebe'), "
    "stakes ('Se você faz isso à noite, pare agora'). NADA de perguntas genéricas "
    "como 'O que você faria?'.\n"
    "- 'prompt_thumbnail': conceito de thumbnail do vídeo em INGLÊS, mega chamativo e "
    "legível em qualquer tamanho: expressão facial extrema (surpresa, choque, medo) ou "
    "objeto em close dramático, NO MÁXIMO 2 elementos, alto contraste de cores "
    "(ex.: luz vermelha intensa contra fundo escuro), composição central limpa. "
    "PROIBIDO texto/letras na imagem (IAs de imagem erram a escrita - o criador "
    "adiciona o texto depois, no editor). Sem métricas inventadas e sem pessoas "
    "reais identificáveis.\n\n"
    "IDIOMA OBRIGATÓRIO: escreva 'titulo_otimizado', 'descricao_otimizada', 'gancho' e a "
    "'narracao' de TODAS as cenas SEMPRE em português do Brasil (pt-BR), independentemente "
    "do idioma do vídeo de referência. Única exceção: 'prompt_visual' e 'prompt_thumbnail' "
    "continuam em inglês, pois são instruções lidas por IAs de imagem/vídeo "
    "(Midjourney, Runway, Pollinations, Sora).\n\n"
    "Responda ESTRITAMENTE em JSON válido, seguindo exatamente este formato "
    "(sem markdown, sem texto fora do JSON):\n"
    "{\n"
    '  "titulo_otimizado": "string",\n'
    '  "descricao_otimizada": "string",\n'
    '  "gancho": "string (os 3 primeiros segundos exatos da narração)",\n'
    '  "prompt_thumbnail": "prompt em inglês para a IA gerar a thumbnail (16:9) do vídeo",\n'
    '  "cenas": [\n'
    "    {\n"
    '      "numero": 1,\n'
    '      "narracao": "texto exato para a narração desta cena",\n'
    '      "prompt_visual": "prompt em inglês, detalhado, descrevendo AÇÃO + MOVIMENTO DE CÂMERA desta cena, pronto para uma IA de vídeo/imagem (Vibes, Midjourney, Runway, Pollinations, Sora, etc.)",\n'
    '      "efeito_sonoro_sugerido": "palavra-chave curta do efeito (ex: whoosh, ding, suspense, aplausos) ou null se nenhum"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    f"Crie entre {cenas_min} e {cenas_max} cenas, cada uma com narração de no máximo "
    f"{palavras_cena} palavras (frases curtas e diretas), "
    f"pensando em um vídeo de aproximadamente {duracao_segundos} segundos no total. "
    f"A soma de todas as narrações deve dar próximo de {duracao_segundos} segundos de fala falada.\n\n"
    "LEMBRETE FINAL: tudo em português do Brasil (pt-BR) — exceto prompt_visual e "
    "prompt_thumbnail (inglês)."
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
            "prompt_thumbnail": "",
            "cenas": [],
            "erro_formatacao": "A IA não devolveu um JSON válido desta vez. Tente novamente.",
            "conteudo_bruto": ultimo_texto_bruto,
        }

    raise Exception(f"Erro ao gerar pacote viral com Gemini: {ultimo_erro}")
