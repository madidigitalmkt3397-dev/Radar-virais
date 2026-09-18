import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export const pesquisarRadar = async (dadosFiltro) => {
  const response = await api.post('/api/radar', dadosFiltro);
  return response.data;
};

export default api;