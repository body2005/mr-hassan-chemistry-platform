import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://host.docker.internal:8080';

export const options = {
  scenarios: {
    dashboard_browse: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 100 },
        { duration: '1m30s', target: 100 },
        { duration: '15s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
    'http_req_duration{scenario:dashboard_browse}': ['p(95)<2000'],
  },
};

export default function () {
  // 1. Login
  const login = http.post(`${BASE}/api/v1/auth/login`, JSON.stringify({
    email: `loaduser${Math.floor(Math.random() * 1000)}@example.com`,
    password: 'wrong-on-purpose-429-or-401',
    institution_slug: 'demo',
  }), { headers: { 'Content-Type': 'application/json' } });

  check(login, { 'login answered': (r) => r.status === 200 || r.status === 401 || r.status === 429 });

  // 2. Health + landing data (unauthenticated dashboard probes)
  const health = http.get(`${BASE}/api/v1/health`);
  check(health, { 'health 200': (r) => r.status === 200 });

  const courses = http.get(`${BASE}/api/v1/courses?page=1&page_size=100`);
  check(courses, { 'courses answered': (r) => r.status === 200 || r.status === 401 });

  sleep(1);
}
