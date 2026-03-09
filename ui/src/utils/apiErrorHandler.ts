// Custom event system for API errors that need to display UI notifications.
// This bridges the gap between the Axios interceptor (non-React) and notistack (React).

export interface ApiErrorEvent {
  type: 'rate-limit' | 'conflict';
  message: string;
}

const API_ERROR_EVENT = 'fedprospect:api-error';

export function dispatchApiError(event: ApiErrorEvent): void {
  window.dispatchEvent(
    new CustomEvent<ApiErrorEvent>(API_ERROR_EVENT, { detail: event }),
  );
}

export function onApiError(handler: (event: ApiErrorEvent) => void): () => void {
  const listener = (e: Event) => {
    const customEvent = e as CustomEvent<ApiErrorEvent>;
    handler(customEvent.detail);
  };
  window.addEventListener(API_ERROR_EVENT, listener);
  return () => window.removeEventListener(API_ERROR_EVENT, listener);
}
