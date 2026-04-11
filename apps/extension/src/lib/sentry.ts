import * as Sentry from '@sentry/browser';

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,

    beforeSend(event) {
      // Strip sensitive headers
      if (event.request?.headers) {
        const headers = { ...event.request.headers };
        delete headers['authorization'];
        delete headers['cookie'];
        delete headers['x-api-key'];
        event.request.headers = headers;
      }
      // Strip user PII
      if (event.user) {
        delete event.user.email;
        delete event.user.ip_address;
      }
      return event;
    },
  });
}
