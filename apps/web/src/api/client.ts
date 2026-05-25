/// <reference types="vite/client" />
import axios, { type AxiosError } from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_AGENTNET_API_BASE || '',
  withCredentials: true,
  timeout: 30000,
});

// CSRF Interceptor: read cookie, set header for mutations
api.interceptors.request.use((config) => {
  const method = (config.method || '').toLowerCase();
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('agentnet_csrf='))
      ?.split('=')[1];
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

// Auth Interceptor: redirect on 401, but skip if already on /login,
// if the failing request is the login endpoint itself,
// or if it's the auth/me probe (public pages handle the error via useAuth).
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname;
      const isLoginPage = currentPath === '/login';
      const requestUrl = error.config?.url ?? '';
      const isLoginRequest = requestUrl.includes('/auth/login');
      const isAuthMeProbe = requestUrl.includes('/auth/me');
      if (!isLoginPage && !isLoginRequest && !isAuthMeProbe) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default api;
