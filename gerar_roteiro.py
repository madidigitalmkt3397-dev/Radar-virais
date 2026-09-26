import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

def criar_roteiro_por_referencia():
    print("--- GERADOR DE ROTEIRO POR REFERÊNCIA ---")
    
    nome_ref = "exemplo_referencia.txt"
    if not os.path.exists(nome_ref):
        print(f"Erro: O ficheiro '{nome_ref}' não foi encontrado.")
        return

    with open(nome_ref, "r", encoding="utf-8") as f:
        roteiro_exemplo = f.read()

    if not roteiro_exemplo.strip():
        print(f"Erro: O ficheiro '{nome_ref}' está vazio.")
        return

    api_key = os.getenv("GEMINI_API_KEY")
    
    tema_novo = input("\nQual é o novo tema para o roteiro? ").strip()
    
    if not tema_novo:
        print("Tema inválido.")
        return

    print(f"\nA analisar a estrutura e a gerar novo roteiro para: '{tema_novo}'...")
    
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    prompt = f"""
Analisa cuidadosamente o seguinte roteiro de referência e compreende a sua estrutura exata (gancho inicial, ritmo do desenvolvimento, tom emocional e chamada para ação final):

--- ROTEIRO DE REFERÊNCIA ---
{roteiro_exemplo}
-----------------------------

Agora, cria um ROTEIRO NOVO e INÉDITO sobre o seguinte tema: "{tema_novo}".
O novo roteiro deve replicar rigorosamente a mesma estrutura e o mesmo dinamismo do exemplo fornecido, mas com conteúdo completamente original.
"""

    # Lista atualizada de modelos suportados para garantir estabilidade
    modelos_para_tentar = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-flash-latest"]
    sucesso = False
    roteiro_gerado = ""

    for modelo in modelos_para_tentar:
        try:
            print(f"A tentar gerar com o modelo: {modelo}...")
            chat = client.chats.create(model=modelo)
            response = chat.send_message(prompt)
            roteiro_gerado = response.text
            if roteiro_gerado:
                sucesso = True
                break
        except Exception as e:
            print(f"Aviso: O modelo {modelo} retornou erro: {e}. A tentar o próximo...")
            time.sleep(1)

    if not sucesso:
        print("\nErro: Todos os modelos estão temporariamente ocupados. Aguarde alguns segundos e tente novamente.")
        return
        
    nome_ficheiro = f"roteiro_inspirado_{tema_novo.lower().replace(' ', '_').replace('?', '').replace('!', '')[:30]}.md"
    
    with open(nome_ficheiro, "w", encoding="utf-8") as f:
        f.write(roteiro_gerado)
        
    print(f"\nSucesso! Novo roteiro guardado em: {nome_ficheiro}")
    print("\n--- PRÉ-VISUALIZAÇÃO DO NOVO ROTEIRO ---\n")
    print(roteiro_gerado)

if __name__ == "__main__":
    criar_roteiro_por_referencia()