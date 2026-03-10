import axios from 'axios';
import { dispatchApiError } from '@/utils/apiErrorHandler';

const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// CSRF interceptor: read XSRF token from cookie, attach as header
apiClient.interceptors.request.use((config) => {
  const token = document.cookie
    .split('; ')
    .find((row) => row.startsWith('XSRF-TOKEN='))
    ?.split('=')[1];
  if (token) {
    config.headers['X-XSRF-TOKEN'] = decodeURIComponent(token);
  } else if (config.method !== 'get' && !config.url?.startsWith('/auth/')) {
    console.warn('[CSRF] XSRF-TOKEN cookie not found for mutating request to', config.url);
  }
  return config;
});

// 401 interceptor with refresh lock pattern
// Note: isRefreshing and failedQueue are module-level but per-tab (each browser tab
// has its own JS context), so this pattern handles concurrent 401s within a single
// tab correctly. Cross-tab coordination (e.g., BroadcastChannel) is unnecessary
// for a small-team tool.
let isRefreshing = false;
let refreshFailCount = 0;
const MAX_REFRESH_FAILURES = 3;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

const processQueue = (error: unknown) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(undefined);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;

    // 429 Rate Limit
    if (status === 429) {
      const retryAfter = error.response?.headers?.['retry-after'];
      const message = retryAfter
        ? `Rate limit reached. Please wait ${retryAfter} seconds before trying again.`
        : 'Too many requests. Please slow down.';
      dispatchApiError({ type: 'rate-limit', message });
      return Promise.reject(error);
    }

    // 409 Conflict
    if (status === 409) {
      const serverMessage = error.response?.data?.message || error.response?.data?.error;
      dispatchApiError({
        type: 'conflict',
        message: serverMessage || 'This record was modified by another user. Please reload and try again.',
      });
      return Promise.reject(error);
    }

    if (status === 401 && !originalRequest._retry && !originalRequest.url?.startsWith('/auth/')) {
      // If refresh has failed too many times consecutively, skip straight to login
      if (refreshFailCount >= MAX_REFRESH_FAILURES) {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login?expired=true';
        }
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => apiClient(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        await axios.post('/api/v1/auth/refresh', {}, { withCredentials: true });
        refreshFailCount = 0;
        processQueue(null);
        return apiClient(originalRequest);
      } catch (refreshError) {
        refreshFailCount++;
        processQueue(refreshError);
        if (window.location.pathname !== '/login') {
          window.location.href = '/login?expired=true';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
