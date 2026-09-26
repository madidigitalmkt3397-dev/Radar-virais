import sys
import os

# Adiciona a pasta backend ao path para importar o serviço de IA existente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from ai_service import gerar_roteiro_ia

def criar_roteiro_externo(tema: str):
    print(f"A gerar roteiro para o tema: '{tema}'...")
    try:
        roteiro = gerar_roteiro_ia(tema)
        nome_ficheiro = f"roteiro_{tema.lower().replace(' ', '_')}.md"
        with open(nome_ficheiro, "w", encoding="utf-8") as f:
            f.write(roteiro)
        print(f"Sucesso! Roteiro guardado em: {nome_ficheiro}")
    except Exception as e:
        print(f"Erro ao gerar roteiro: {e}")

if __name__ == "__main__":
    tema_escolhido = input("Introduza o tema para o vídeo viral: ")
    criar_roteiro_externo(tema_escolhido)
