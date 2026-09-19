import React, { useState } from 'react';
import api from './services/api';

function App() {
  const [nicho, setNicho] = useState('Finanças e Investimentos');
  const [palavraChave, setPalavraChave] = useState('');
  const [periodo, setPeriodo] = useState('Últimos 30 dias');
  const [quantidade, setQuantidade] = useState('5');
  const [videos, setVideos] = useState([]);
  const [transcricoes, setTranscricoes] = useState({});
  const [loadingTranscript, setLoadingTranscript] = useState({});
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState('');

  const nichosDisponiveis = [
    'Finanças e Investimentos',
    'Tecnologia e IA',
    'Marketing Digital e Vendas',
    'Curiosidades e Mistérios',
    'Desenvolvimento Pessoal',
    'Humor e Entretenimento',
    'Fitness e Saúde',
    'Negócios e Empreendedorismo',
    'Games e Geek',
    'Criptomoedas e Web3'
  ];

  // OBS: o backend atual (rota /api/search) só usa "query" e "max_results".
  // Os campos "nicho" e "periodo" continuam na tela pra você escolher,
  // mas hoje eles não são enviados pro backend (ele ainda não usa isso).
  const handlePesquisar = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErro('');
    setTranscricoes({});

    try {
      const response = await api.post('/api/search', {
        query: palavraChave,
        max_results: parseInt(quantidade) || 5
      });
      setVideos(response.data.videos || []);
    } catch (err) {
      console.error(err);
      setErro('Erro ao buscar vídeos. Verifique se o backend está rodando.');
    } finally {
      setLoading(false);
    }
  };

  const handleBuscarTranscricao = async (videoId) => {
    setLoadingTranscript(prev => ({ ...prev, [videoId]: true }));
    try {
      const response = await api.post('/api/transcript', { video_id: videoId });
      setTranscricoes(prev => ({ ...prev, [videoId]: response.data.transcript }));
    } catch (err) {
      console.error(err);
      setTranscricoes(prev => ({ ...prev, [videoId]: 'Erro ao carregar a transcrição.' }));
    } finally {
      setLoadingTranscript(prev => ({ ...prev, [videoId]: false }));
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif', maxWidth: '1100px', margin: '0 auto', background: '#f4f6f9', minHeight: '100vh' }}>
      <header style={{ background: '#fff', padding: '20px', borderRadius: '8px', marginBottom: '20px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
        <h1 style={{ margin: '0 0 5px 0', color: '#1a1a1a' }}>Radar de Virais 🚀</h1>
        <p style={{ margin: 0, color: '#666' }}>Minere padrões de sucesso e transcrições para dominar seu nicho.</p>
      </header>

      <form onSubmit={handlePesquisar} style={{ background: '#fff', padding: '20px', borderRadius: '8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)', marginBottom: '20px' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Nicho:</label>
          <select value={nicho} onChange={(e) => setNicho(e.target.value)} style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}>
            {nichosDisponiveis.map((n, idx) => (
              <option key={idx} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Palavra-chave / Foco:</label>
          <input
            type="text"
            value={palavraChave}
            onChange={(e) => setPalavraChave(e.target.value)}
            placeholder="Ex: inteligência artificial, renda extra..."
            style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
            required
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Período:</label>
          <select value={periodo} onChange={(e) => setPeriodo(e.target.value)} style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc' }}>
            <option value="Últimos 30 dias">Últimos 30 dias</option>
            <option value="Última semana">Última semana</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Quantidade de Vídeos:</label>
          <input
            type="number"
            value={quantidade}
            onChange={(e) => setQuantidade(e.target.value)}
            style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
            min="1"
            max="20"
          />
        </div>

        <div style={{ gridColumn: 'span 2' }}>
          <button type="submit" style={{ background: '#0066ff', color: 'white', padding: '12px 20px', border: 'none', borderRadius: '6px', cursor: 'pointer', width: '100%', fontWeight: 'bold', fontSize: '16px' }}>
            {loading ? 'Minerando dados...' : '🔍 EXECUTAR RADAR DE VIRAIS'}
          </button>
        </div>
      </form>

      {erro && <p style={{ color: 'red', background: '#ffe6e6', padding: '10px', borderRadius: '4px' }}>{erro}</p>}

      <div>
        <h2 style={{ color: '#333' }}>Resultados Analíticos</h2>
        {videos.length === 0 && !loading && (
          <p style={{ color: '#777' }}>Nenhum vídeo minerado ainda. Preencha os campos acima e clique em executar.</p>
        )}

        <div style={{ display: 'grid', gap: '20px' }}>
          {videos.map((video) => (
            <div key={video.id} style={{ border: '1px solid #e1e4e8', padding: '20px', borderRadius: '8px', background: '#fff', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
              <h3 style={{ margin: '0 0 8px 0', color: '#1f2328' }}>{video.title}</h3>
              <p style={{ margin: '0 0 10px 0', color: '#57606a', fontSize: '14px' }}>
                <strong>Canal:</strong> {video.channelTitle} | <strong>Publicado em:</strong> {video.publishedAt ? new Date(video.publishedAt).toLocaleDateString('pt-BR') : '—'}
              </p>

              {video.description && (
                <p style={{ margin: '0 0 12px 0', color: '#57606a', fontSize: '13px', maxHeight: '60px', overflow: 'hidden' }}>
                  {video.description}
                </p>
              )}

              <div style={{ display: 'flex', gap: '15px', alignItems: 'center', marginBottom: '10px' }}>
                <a
                  href={`https://www.youtube.com/watch?v=${video.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#0969da', textDecoration: 'none', fontWeight: 'bold', fontSize: '14px' }}
                >
                  🔗 Assistir no YouTube
                </a>

                <button
                  onClick={() => handleBuscarTranscricao(video.id)}
                  style={{ background: '#2ea44f', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px' }}
                >
                  {loadingTranscript[video.id] ? 'Extraindo...' : '📝 Extrair Transcrição'}
                </button>
              </div>

              {transcricoes[video.id] && (
                <div style={{ marginTop: '10px', background: '#fffcf0', padding: '12px', borderRadius: '6px', border: '1px solid #fbe5a2', maxHeight: '150px', overflowY: 'auto' }}>
                  <strong style={{ display: 'block', marginBottom: '5px', fontSize: '13px' }}>Transcrição Completa:</strong>
                  <p style={{ margin: 0, fontSize: '12px', color: '#333', whiteSpace: 'pre-wrap' }}>{transcricoes[video.id]}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
