import axios from 'axios';

const api = axios.create({
  baseURL: 'https://radar-virais-1.onrender.com/',
});

export const pesquisarRadar = async (dadosFiltro) => {
  const response = await api.post('/api/radar', dadosFiltro);
  return response.data;
};

export default api;
