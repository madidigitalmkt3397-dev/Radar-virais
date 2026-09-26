import React, { useState } from 'react';
import api from './services/api';

// Renderiza o pacote viral (objeto JSON da IA) de forma legível.
// SEM este componente o React quebra ao receber um objeto como filho.
function PacoteViral({ pacote }) {
  if (!pacote) return null;

  // Baixa o pacote como roteiro.json — é ele que o render_video.py lê (Fase 6)
  const baixarRoteiro = () => {
    const blob = new Blob([JSON.stringify(pacote, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'roteiro.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // Formato de emergência: a IA não devolveu JSON válido
  if (pacote.conteudo_bruto) {
    return (
      <div style={{ fontSize: '13px' }}>
        <p style={{ color: '#b00020', fontWeight: 'bold' }}>⚠️ {pacote.erro_formatacao}</p>
        <pre style={{ whiteSpace: 'pre-wrap', background: '#f6f8fa', padding: '10px', borderRadius: '4px' }}>
          {pacote.conteudo_bruto}
        </pre>
      </div>
    );
  }

  const cenas = Array.isArray(pacote.cenas) ? pacote.cenas : [];

  return (
    <div style={{ fontSize: '13px', color: '#24292f', lineHeight: '1.5' }}>
      {pacote.titulo_otimizado && (
        <p style={{ margin: '4px 0' }}><strong>🎬 Título otimizado:</strong> {pacote.titulo_otimizado}</p>
      )}
      {pacote.gancho && (
        <p style={{ margin: '4px 0' }}><strong>🪝 Gancho (0-3s):</strong> {pacote.gancho}</p>
      )}
      {pacote.descricao_otimizada && (
        <p style={{ margin: '4px 0' }}><strong>📝 Descrição otimizada:</strong> {pacote.descricao_otimizada}</p>
      )}

      {cenas.map((cena, idx) => (
        <div key={idx} style={{ background: '#fff', borderLeft: '4px solid #0969da', padding: '10px', margin: '8px 0', borderRadius: '4px' }}>
          <strong>Cena {cena.numero || idx + 1}</strong>
          <p style={{ margin: '6px 0' }}>{cena.narracao || cena.roteiro}</p>
          {cena.prompt_visual && (
            <p style={{ margin: '6px 0', color: '#57606a' }}>
              <strong>🎨 Prompt visual:</strong> {cena.prompt_visual}
            </p>
          )}
          {cena.efeito_sonoro_sugerido && (
            <p style={{ margin: '6px 0' }}>
              <strong>🔊 Efeito sonoro:</strong> {cena.efeito_sonoro_sugerido}
            </p>
          )}
        </div>
      ))}

      {pacote.cta && <p style={{ margin: '4px 0' }}><strong>📣 CTA:</strong> {pacote.cta}</p>}

      <div style={{ marginTop: '10px' }}>
        <button
          onClick={baixarRoteiro}
          style={{ background: '#2ea44f', color: '#fff', border: 'none', padding: '8px 14px', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px' }}
        >
          📥 Baixar roteiro (.json)
        </button>
      </div>

      {/* Último recurso: se não bateu nenhum formato conhecido, mostra o JSON */}
      {cenas.length === 0 && (
        <pre style={{ whiteSpace: 'pre-wrap', background: '#f6f8fa', padding: '10px', borderRadius: '4px' }}>
          {JSON.stringify(pacote, null, 2)}
        </pre>
      )}
    </div>
  );
}

function App() {
  const [nicho, setNicho] = useState('Finanças e Investimentos');
  const [palavraChave, setPalavraChave] = useState('');
  const [periodo, setPeriodo] = useState('month');
  const [quantidade, setQuantidade] = useState('5');
  
  // Novos estados para a entrada manual
  const [manualTitulo, setManualTitulo] = useState('');
  const [manualDescricao, setManualDescricao] = useState('');
  const [manualTranscricao, setManualTranscricao] = useState('');
  const [resultadoManual, setResultadoManual] = useState('');
  const [loadingManual, setLoadingManual] = useState(false);

  const [videos, setVideos] = useState([]);
  const [transcricoes, setTranscricoes] = useState({});
  const [resultadosIa, setResultadosIa] = useState({});
  const [loadingTranscript, setLoadingTranscript] = useState({});
  const [loadingIa, setLoadingIa] = useState({});
  const [copiado, setCopiado] = useState({});
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

  const handlePesquisar = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErro('');
    setVideos([]);

    try {
      const payload = {
        query: palavraChave,
        max_results: parseInt(quantidade) || 5,
        period: periodo
      };
      const response = await api.post('/api/search', payload);
      setVideos(response.data.videos || []);
    } catch (err) {
      console.error(err);
      setErro('Erro ao buscar vídeos. Verifique se o backend está rodando.');
    } finally {
      setLoading(false);
    }
  };

  // Envio manual para a IA gerar o pacote completo
  const handleGerarManual = async (e) => {
    e.preventDefault();
    if (!manualTranscricao.trim()) {
      alert('Por favor, insira a transcrição.');
      return;
    }

    setLoadingManual(true);
    setResultadoManual('');

    try {
      const payload = {
        titulo: manualTitulo || 'Vídeo sem título',
        descricao: manualDescricao || '',
        transcricao: manualTranscricao
      };

      const response = await api.post('/api/analyze-transcript', payload);
      setResultadoManual(response.data.script);
    } catch (err) {
      console.error(err);
      const detalhe = err.response?.data?.detail || err.message;
      alert(`Erro ao gerar análise manual com a IA.\n\n${detalhe}`);
    } finally {
      setLoadingManual(false);
    }
  };

  const buscarTranscricao = async (videoId) => {
    if (transcricoes[videoId]) return transcricoes[videoId];
    setLoadingTranscript(prev => ({ ...prev, [videoId]: true }));
    try {
      const response = await api.post('/api/transcript', { video_id: videoId });
      const texto = response.data.transcript;
      setTranscricoes(prev => ({ ...prev, [videoId]: texto }));
      return texto;
    } catch (err) {
      console.error(err);
      const detalhe = err.response?.data?.detail || err.message;
      const msg = `Erro ao carregar a transcrição automaticamente. (${detalhe})`;
      setTranscricoes(prev => ({ ...prev, [videoId]: msg }));
      return msg;
    } finally {
      setLoadingTranscript(prev => ({ ...prev, [videoId]: false }));
    }
  };

  const handleGerarPacoteIa = async (video) => {
    const transcricaoTexto = await buscarTranscricao(video.id);
    
    if (!transcricaoTexto || transcricaoTexto.includes('Erro')) {
      alert('O YouTube bloqueou a extração automática. Use a seção de "Inserção Manual" acima para colar a transcrição!');
      return;
    }

    setLoadingIa(prev => ({ ...prev, [video.id]: true }));
    try {
      const payload = {
        titulo: video.title,
        descricao: video.description || '',
        transcricao: transcricaoTexto
      };

      const response = await api.post('/api/analyze-transcript', payload);
      setResultadosIa(prev => ({ ...prev, [video.id]: response.data.script }));
    } catch (err) {
      console.error(err);
      const detalhe = err.response?.data?.detail || err.message;
      alert(`Erro ao gerar análise com a IA.\n\n${detalhe}`);
    } finally {
      setLoadingIa(prev => ({ ...prev, [video.id]: false }));
    }
  };

  const formatarNumero = (n) => (typeof n === 'number' ? n.toLocaleString('pt-BR') : '—');

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif', maxWidth: '1100px', margin: '0 auto', background: '#f4f6f9', minHeight: '100vh' }}>
      <header style={{ background: '#fff', padding: '20px', borderRadius: '8px', marginBottom: '20px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
        <h1 style={{ margin: '0 0 5px 0', color: '#1a1a1a' }}>Radar de Virais 🚀</h1>
        <p style={{ margin: 0, color: '#666' }}>Minere padrões de sucesso, analise ganchos e crie roteiros otimizados.</p>
      </header>

      {/* SEÇÃO 1: INSERÇÃO MANUAL (CONTorna bloqueios do YouTube) */}
      <section style={{ background: '#fff', padding: '20px', borderRadius: '8px', marginBottom: '20px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)', borderLeft: '5px solid #2ea44f' }}>
        <h2 style={{ margin: '0 0 10px 0', fontSize: '18px', color: '#2ea44f' }}>✍️ Inserção Manual de Vídeo (Bypass de Bloqueio)</h2>
        <p style={{ margin: '0 0 15px 0', fontSize: '13px', color: '#666' }}>Se o YouTube bloquear a extração automática, cole os dados manualmente aqui para gerar o roteiro e os prompts de vídeo.</p>
        
        <form onSubmit={handleGerarManual} style={{ display: 'grid', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '13px' }}>Título do Vídeo:</label>
            <input
              type="text"
              value={manualTitulo}
              onChange={(e) => setManualTitulo(e.target.value)}
              placeholder="Ex: O erro que todo criador comete..."
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '13px' }}>Descrição:</label>
            <textarea
              value={manualDescricao}
              onChange={(e) => setManualDescricao(e.target.value)}
              placeholder="Cole a descrição do vídeo original aqui..."
              rows="2"
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '13px' }}>Transcrição Completa (Obrigatório):</label>
            <textarea
              value={manualTranscricao}
              onChange={(e) => setManualTranscricao(e.target.value)}
              placeholder="Cole o texto da transcrição copiado do YouTube aqui..."
              rows="5"
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
              required
            />
          </div>

          <button type="submit" style={{ background: '#2ea44f', color: 'white', padding: '10px 15px', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', fontSize: '14px' }}>
            {loadingManual ? 'Analisando e gerando pacote...' : '🚀 Gerar Pacote Viral Manualmente'}
          </button>
        </form>

        {resultadoManual && (
          <div style={{ marginTop: '15px', background: '#f0f6fc', padding: '15px', borderRadius: '6px', border: '1px solid #0969da' }}>
            <strong style={{ display: 'block', marginBottom: '8px', fontSize: '15px', color: '#0969da' }}>✨ Pacote Viral Gerado (Manual):</strong>
            <div style={{ margin: 0 }}>
              <PacoteViral pacote={resultadoManual} />
            </div>
          </div>
        )}
      </section>

      {/* SEÇÃO 2: BUSCA AUTOMÁTICA DE VÍDEOS */}
      <form onSubmit={handlePesquisar} style={{ background: '#fff', padding: '20px', borderRadius: '8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)', marginBottom: '20px' }}>
        <div style={{ gridColumn: 'span 2' }}>
          <h2 style={{ margin: '0 0 5px 0', fontSize: '18px', color: '#0066ff' }}>🔍 Mineração Automática de Vídeos</h2>
        </div>
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
            <option value="day">Últimas 24 horas</option>
            <option value="week">Última semana</option>
            <option value="month">Este mês (últimos 30 dias)</option>
            <option value="year">Este ano (últimos 12 meses)</option>
            <option value="all">Qualquer período</option>
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
            {loading ? 'Minerando dados...' : '🔍 EXECUTAR BUSCA DE VÍDEOS'}
          </button>
        </div>
      </form>

      {erro && <p style={{ color: 'red', background: '#ffe6e6', padding: '10px', borderRadius: '4px' }}>{erro}</p>}

      <div>
        <h2 style={{ color: '#333' }}>Resultados Analíticos</h2>
        {videos.length === 0 && !loading && (
          <p style={{ color: '#777' }}>Nenhum vídeo minerado ainda.</p>
        )}

        <div style={{ display: 'grid', gap: '20px' }}>
          {videos.map((video) => (
            <div key={video.id} style={{ border: '1px solid #e1e4e8', padding: '20px', borderRadius: '8px', background: '#fff', display: 'flex', gap: '20px', alignItems: 'flex-start', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
              {video.thumbnail && (
                <img src={video.thumbnail} alt={video.title} style={{ width: '180px', borderRadius: '6px', objectFit: 'cover' }} />
              )}
              <div style={{ flex: 1 }}>
                <h3 style={{ margin: '0 0 8px 0', color: '#1f2328' }}>{video.title}</h3>
                <p style={{ margin: '0 0 10px 0', color: '#57606a', fontSize: '14px' }}>
                  <strong>Canal:</strong> {video.channelTitle} | <strong>Publicado em:</strong> {video.publishedAt ? new Date(video.publishedAt).toLocaleDateString('pt-BR') : '—'}
                </p>

                <div style={{ display: 'flex', gap: '15px', background: '#f6f8fa', padding: '10px', borderRadius: '6px', marginBottom: '10px', fontSize: '13px', flexWrap: 'wrap' }}>
                  <span>👀 <strong>{formatarNumero(video.views)}</strong> Views</span>
                  <span>👍 <strong>{formatarNumero(video.likes)}</strong> Likes</span>
                  <span>💬 <strong>{formatarNumero(video.comments)}</strong> Comentários</span>
                  <span>🔥 <strong>{video.engagement_rate != null ? video.engagement_rate : '—'}%</strong> Engajamento</span>
                </div>

                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap' }}>
                  <a
                    href={`https://www.youtube.com/watch?v=${video.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#0969da', textDecoration: 'none', fontWeight: 'bold', fontSize: '14px' }}
                  >
                    🔗 Assistir no YouTube
                  </a>

                  <button
                    onClick={() => handleGerarPacoteIa(video)}
                    style={{ background: '#d73a49', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '13px' }}
                  >
                    {loadingIa[video.id] ? 'Gerando Pacote IA...' : '🤖 Gerar Roteiro e Prompts (Automático)'}
                  </button>
                </div>

                {resultadosIa[video.id] && (
                  <div style={{ marginTop: '15px', background: '#f0f6fc', padding: '15px', borderRadius: '6px', border: '1px solid #0969da' }}>
                    <strong style={{ display: 'block', marginBottom: '8px', fontSize: '15px', color: '#0969da' }}>✨ Pacote Viral Gerado pela IA:</strong>
                    <div style={{ margin: 0 }}>
                      <PacoteViral pacote={resultadosIa[video.id]} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
