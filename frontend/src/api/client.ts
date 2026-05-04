import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || '';

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Add request interceptor for debugging
client.interceptors.request.use(
  (config) => {
    console.log('[API Request]', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for debugging
client.interceptors.response.use(
  (response) => {
    console.log('[API Response]', response.config.url, response.status);
    return response;
  },
  (error) => {
    console.error('[API Error]', error.config?.url, error.message, error.response?.status);
    return Promise.reject(error);
  }
);

export default client;
