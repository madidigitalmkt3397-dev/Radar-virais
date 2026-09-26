import os
import json
from google import genai

def analisar_e_criar_pacote_viral(titulo, descricao, transcricao):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Atua como um especialista em roteiros virais do YouTube e técnicas de retenção profunda.
    Analisa os dados do vídeo fornecido:
    - Título: {titulo}
    - Descrição: {descricao}
    - Transcrição/Contexto: {transcricao}
    
    Gera um pacote viral estruturado em formato JSON puro contendo as seguintes chaves exatas:
    - "topico": Resumo do tema principal.
    - "formato": O formato ideal do vídeo (ex: Controvérsia, História Emocional).
    - "gancho": O gancho inicial (0-5s) de alto impacto.
    - "cenas": Uma lista de objetos de cenas, onde cada cena tem "numero", "titulo_cena", "roteiro" e "dica_visual".
    - "cta": Chamada para ação final.
    """
    
    # Modelos com fallback automático para evitar o erro 503
    modelos_para_tentar = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash"
    ]
    
    resposta_sucesso = None
    for modelo in modelos_para_tentar:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
            )
            if response and response.text:
                resposta_sucesso = response.text
                break
        except Exception:
            continue
            
        if not resposta_sucesso:
            raise Exception("Todos os modelos Gemini estão temporariamente indisponíveis (503). Tente novamente.")
        
    # Limpa formatação markdown caso o modelo adicione ```json ... ```
    texto = resposta_sucesso.strip()
    if texto.startswith("```json"):
        texto = texto[7:]
    if texto.endswith("```"):
        texto = texto[:-3]
        
    try:
        return json.loads(texto.strip())
    except Exception:
        # Fallback estruturado caso o output venha corrompido
        return {
            "topico": titulo,
            "formato": "Viral Genérico",
            "gancho": "Erro ao parsear JSON estruturado.",
            "conteudo_gerado": texto,
            "cenas": [],
            "cta": "Inscreva-se no canal!"
        }