import streamlit as st
import os
from google import genai

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Gerador de Roteiros Virais | Radar",
    page_icon="🚀",
    layout="centered"
)

st.title("🚀 Gerador de Roteiros Virais por IA")
st.markdown("Transforme estruturas e tendências do YouTube em roteiros de alta retenção.")

# Caixa para inserir a chave de API (caso não esteja nas variáveis de ambiente do Render)
api_key_input = st.text_input("Insira a sua GEMINI_API_KEY (ou deixe em branco se já configurou no Render):", type="password")

# Define a chave de API (prioriza o input, depois tenta ler do ambiente)
api_key = api_key_input if api_key_input else os.environ.get("GEMINI_API_KEY")

# Input do utilizador para o tema ou estrutura do vídeo
tema_video = st.text_area("Sobre o que será o vídeo ou qual a estrutura viral que quer seguir?", placeholder="Ex: Pai que recusa pagar a faculdade para ensinar uma lição de vida...")

if st.button("Gerar Roteiro Viral", type="primary"):
    if not api_key:
        st.error("⚠️ Por favor, insira uma GEMINI_API_KEY válida para continuar.")
    elif not tema_video:
        st.error("⚠️ Por favor, insira o tema ou estrutura do vídeo.")
    else:
        with st.spinner("A gerar roteiro e a aplicar técnicas de retenção com Gemini..."):
            try:
                # Inicializa o cliente da nova biblioteca google-genai
                client = genai.Client(api_key=api_key)
                
                # Prompt estruturado para gerar o roteiro viral
                prompt = f"""
                Atua como um especialista em roteiros virais do YouTube e técnicas de retenção profunda.
                Com base no seguinte tema/estrutura: "{tema_video}", cria um roteiro completo, dividido em:
                1. Gancho Inicial (0-5 segundos de impacto máximo)
                2. Desenvolvimento e Construção de Tensão
                3. Clímax e Reviravolta
                4. Chamada para Ação (CTA) final.
                Usa uma linguagem envolvente, emocional e focada em manter o espectador até ao último segundo.
                """
                
                # Lista de modelos por ordem de preferência (com fallbacks automáticos para alta disponibilidade)
                modelos_para_tentar = [
                    "gemini-3.8-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-2.5-flash"
                ]
                
                resposta_sucesso = None
                erro_ultimo = ""
                
                # Tenta cada modelo em sequência se houver falha por sobrecarga (503)
                for modelo in modelos_para_tentar:
                    try:
                        response = client.models.generate_content(
                            model=modelo,
                            contents=prompt,
                        )
                        if response and response.text:
                            resposta_sucesso = response.text
                            break
                    except Exception as e:
                        erro_ultimo = str(e)
                        continue # Vai para o próximo modelo da lista se este falhar
                
                if resposta_sucesso:
                    st.success("🎉 Roteiro gerado com sucesso!")
                    st.markdown("---")
                    st.markdown(resposta_sucesso)
                    
                    # Botão para download do roteiro gerado
                    st.download_button(
                        label="📥 Descarregar Roteiro (.md)",
                        data=resposta_sucesso,
                        file_name="roteiro_viral.md",
                        mime="text/markdown"
                    )
                else:
                    st.error(f"⚠️ Todos os modelos estão temporariamente ocupados devido a alta procura. Tente novamente em alguns segundos.\n\nDetalhe técnico: {erro_ultimo}")

            except Exception as e:
                st.error(f"Ocorreu um erro inesperado: {str(e)}")