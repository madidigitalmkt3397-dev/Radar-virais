import React, { useState } from 'react';

export default function App() {
  const [resultadosIa, setResultadosIa] = useState({});
  const [loadingId, setLoadingId] = useState(null);

  const handleGerarPacote = async (video) => {
    setLoadingId(video.id);
    try {
      const response = await fetch('/api/gerar-pacote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          titulo: video.titulo,
          descricao: video.descricao,
          transcricao: video.transcricao
        })
      });
      const data = await response.json();
      setResultadosIa(prev => ({ ...prev, [video.id]: data }));
    } catch (err) {
      alert("Erro ao comunicar com o servidor.");
    } finally {
      setLoadingId(null);
    }
  };

  const baixarJson = (dados, titulo) => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(dados, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${titulo || 'roteiro'}_viral.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif', maxWidth: '800px', margin: '0 auto' }}>
      <h1>🚀 Radar de Virais - Gerador de Roteiros</h1>
      
      <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
        <h3>Exemplo de Vídeo Analisado</h3>
        <p><strong>Título:</strong> Pai recusa pagar faculdade...</p>
        <button 
          onClick={() => handleGerarPacote({ id: 1, titulo: "Pai recusa pagar faculdade", descricao: "História reflexiva", transcricao: "Transcrição simulada..." })}
          disabled={loadingId === 1}
        >
          {loadingId === 1 ? 'A gerar pacote...' : 'Gerar Pacote Viral'}
        </button>

        {/* Renderização segura e estruturada do objeto retornado */}
        {resultadosIa[1] && (
          <div style={{ marginTop: '15px', background: '#f9f9f9', padding: '15px', borderRadius: '5px' }}>
            <h4>🎯 Tópico: {resultadosIa[1].topico}</h4>
            <p><strong>Formato:</strong> {resultadosIa[1].formato}</p>
            <p><strong>Gancho Inicial:</strong> {resultadosIa[1].gancho}</p>
            
            {resultadosIa[1].cenas && resultadosIa[1].cenas.length > 0 ? (
              <div>
                <h5>Cenas do Roteiro:</h5>
                {resultadosIa[1].cenas.map((cena, idx) => (
                  <div key={idx} style={{ background: '#fff', padding: '10px', margin: '8px 0', borderLeft: '4px solid #007bff', borderRadius: '4px' }}>
                    <strong>Cena {cena.numero || idx + 1}: {cena.titulo_cena}</strong>
                    <p>{cena.roteiro}</p>
                    <small style={{ color: '#666' }}>💡 Dica visual: {cena.dica_visual}</small>
                  </div>
                ))}
              </div>
            ) : (
              <pre style={{ whiteSpace: 'pre-wrap' }}>{resultadosIa[1].conteudo_gerado}</pre>
            )}

            <p style={{ marginTop: '10px' }}><strong>CTA:</strong> {resultadosIa[1].cta}</p>

            <button 
              onClick={() => baixarJson(resultadosIa[1], resultadosIa[1].topico)}
              style={{ marginTop: '10px', background: '#28a745', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '4px', cursor: 'pointer' }}
            >
              📥 Baixar Roteiro (.json)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}