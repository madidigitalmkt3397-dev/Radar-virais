import { useEffect, useState } from 'react';
import api from './services/api';

export default function App() {
  const [status, setStatus] = useState('Conectando ao FastAPI...');

  useEffect(() => {
    api.get('/')
      .then(res => setStatus(JSON.stringify(res.data, null, 2)))
      .catch(err => setStatus('Erro: ' + err.message));
  }, []);

  return (
    <div style={{ padding: '40px', fontFamily: 'Arial' }}>
      <h1 style={{ color: '#2563eb' }}>Radar de Virais</h1>
      <pre style={{ background: '#f3f4f6', padding: '20px', borderRadius: '8px' }}>{status}</pre>
    </div>
  );
}