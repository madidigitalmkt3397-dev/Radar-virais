import axios from 'axios';

const api = axios.create({
  baseURL: 'https://radar-virais.onrender.com',
  headers: {
    'Content-Type': 'application/json'
  }
});

export default api;
