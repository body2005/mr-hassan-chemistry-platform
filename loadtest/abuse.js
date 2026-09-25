import http from 'k6/http';
import { sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://host.docker.internal:8080';

export const options = {
  vus: 5,
  duration: '40s',
  thresholds: {
    // The abuser SHOULD get rejected; we assert the service survives.
    http_req_failed: ['rate<0.99'],
  },
};

export default function () {
  for (let i = 0; i < 50; i++) {
    http.get(`${BASE}/api/v1/knowledge-center/sources?grade_level=SECONDARY_1`);
  }
  sleep(0.2);
}
