import os
import streamlit as st
from google import genai
from dotenv import load_dotenv

# Tenta carregar o .env local (no Render, as chaves são configuradas no painel do Render)
load_dotenv()

st.set_page_config(page_title="Radar de Virais & Gerador de Roteiros", page_icon="🎬", layout="wide")

st.title("🎬 Radar de Virais & IA Script Generator")
st.markdown("Descubra vídeos virais do YouTube e transforme-os instantaneamente em roteiros originais com Inteligência Artificial.")

# Obter chave de API (local ou das variáveis de ambiente do Render)
api_key = os.getenv("GEMINI_API_KEY")

# --- SECÇÃO 1: YOUTUBE / VÍDEOS VIRAIS (Simulação ou integração dos seus dados) ---
st.subheader("1. Selecione um Vídeo Viral de Referência")
# Aqui futuramente entra a lista dinâmica que puxa do seu sistema do YouTube
video_exemplo = st.selectbox(
    "Escolha um vídeo viral recente:",
    [
        "Exemplo 1: O dia em que decidi mudar de vida aos 50 anos",
        "Exemplo 2: Por que recusei pagar a faculdade ao meu filho",
        "Exemplo 3: Lições que aprendi a trabalhar sozinh@"
    ]
)

# Roteiro base correspondente (pode vir da sua base de dados do YouTube)
roteiro_padrao = """[Gancho Inicial] Há momentos na vida em que temos de escolher entre agradar aos outros ou salvar o nosso próprio futuro.
[Desenvolvimento] Todos achavam que eu estava errado. Diziam que um pai tem a obrigação de dar tudo de mão beijada. Mas eu sabia que o excesso de facilidade destrói a ambição.
[Conclusão] Hoje, ele agradece-me a lição. O valor do dinheiro ganha-se com o suor do rosto.
[Chamada para Ação] Concorda com esta decisão? Deixe a sua opinião nos comentários."""

roteiro_referencia = st.text_area("Roteiro de Referência (Extraído do Vídeo)", value=roteiro_padrao, height=150)

# --- SECÇÃO 2: GERADOR DE ROTEIRO COM GEMINI ---
st.subheader("2. Crie um Novo Roteiro Baseado na Estrutura")
tema_novo = st.text_input("Qual é o novo tema ou perspetiva que quer aplicar?", placeholder="Ex: Uma mãe que ensina o valor do trabalho aos filhos...")

if st.button("Gerar Roteiro com IA 🚀", type="primary"):
    if not tema_novo.strip():
        st.warning("Por favor, insira um tema para o novo roteiro.")
    elif not api_key:
        st.error("Erro: A chave GEMINI_API_KEY não foi encontrada nas variáveis de ambiente.")
    else:
        with st.spinner("A analisar a estrutura e a gerar roteiro viral..."):
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"""
Analisa cuidadosamente o seguinte roteiro de referência e compreende a sua estrutura exata (gancho inicial, ritmo do desenvolvimento, tom emocional e chamada para ação final):

--- ROTEIRO DE REFERÊNCIA ---
{roteiro_referencia}
-----------------------------

Agora, cria um ROTEIRO NOVO e INÉDITO sobre o seguinte tema: "{tema_novo}".
O novo roteiro deve replicar rigorosamente a mesma estrutura e o mesmo dinamismo do exemplo fornecido, mas com conteúdo completamente original.
"""
                chat = client.chats.create(model="gemini-3.5-flash-lite")
                response = chat.send_message(prompt)
                
                st.success("Roteiro gerado com sucesso!")
                st.markdown("### Resultado:")
                st.markdown(response.text)
                
                # Botão para download
                st.download_button(
                    label="Descarregar Roteiro (.md)",
                    data=response.text,
                    file_name="roteiro_viral_gerado.md",
                    mime="text/markdown"
                )
            except Exception as e:
                st.error(f"Erro ao comunicar com a API do Gemini: {e}")