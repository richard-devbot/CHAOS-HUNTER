import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,  // 1 user
  duration: '5s',  // 5 seconds test
};

export default function () {
  const res = http.get('http://example-service.chaos-eater.svc.cluster.local');
  check(res, {
    'is status 200': (r) => r.status === 200,
  });
}