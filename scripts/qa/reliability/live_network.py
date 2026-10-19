"""Small production smoke using an ordinary session; no server-key read.

Run only after the independent proxy key and explicit Render mode are deployed.
The optional five-attempt guard uses a nonexistent reserved test identity and
creates no student or content. Never print cookies, login bodies or raw IPs.
"""
import argparse
import getpass
import ipaddress
import json
import os
from pathlib import Path
import time
import uuid

import httpx

HOSTS = (
    ('render', 'https://mr-hassan-chemistry-platform.onrender.com/api/v1'),
    ('vercel', 'https://mr-hassan-chemistry-platform.vercel.app/api/v1'),
)
FIELDS = ('expected_match', 'signed_proxy_assertion', 'render_edge_contract')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--institution', default='demo')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--login-guard', action='store_true')
    args = parser.parse_args()
    password = os.getenv('LIVE_STUDENT_PASSWORD') or getpass.getpass('Student password: ')
    report = {'hosts': [], 'passed': False}
    with httpx.Client(timeout=30, trust_env=False) as public:
        r = public.get('https://api.ipify.org')
        r.raise_for_status()
        expected = str(ipaddress.ip_address(r.text.strip()))
    for label, base in HOSTS:
        row = {'host': label, 'checks': [], 'passed': False}
        report['hosts'].append(row)
        with httpx.Client(timeout=30, trust_env=False) as session:
            login = session.post(base + '/auth/login', json={
                'email': args.email, 'password': password,
                'institution_slug': args.institution,
            })
            row['login_status'] = login.status_code
            if login.status_code != 200:
                continue
            try:
                for kind, extras in (
                    ('baseline', {}),
                    ('forged_forwarding', {
                        'X-Forwarded-For': '198.51.100.42',
                        'X-Vercel-Forwarded-For': '203.0.113.8',
                        'X-Chemistry-Client-IP': '192.0.2.1',
                        'X-Chemistry-Client-Time': str(int(time.time())),
                        'X-Chemistry-Client-Signature': '0' * 64,
                    }),
                ):
                    r = session.get(base + '/operations/client-network',
                        headers={'X-Expected-Client-IP': expected, **extras})
                    comparison = {k: r.json().get(k) for k in FIELDS} if r.status_code == 200 else {}
                    row['checks'].append({'kind': kind, 'status': r.status_code, 'comparison': comparison})
                row['passed'] = all(
                    check['status'] == 200 and check['comparison'].get('expected_match') is True
                    and check['comparison'].get('signed_proxy_assertion' if label == 'vercel' else 'render_edge_contract') is True
                    for check in row['checks']
                )
                # Only ordinary, bounded reads; no pressure test or media upload.
                row['smoke'] = {name: session.get(base + path).status_code for name, path in (
                    ('profile', '/auth/me'), ('courses', '/courses?page=1&page_size=20'),
                    ('calendar', '/calendar?limit=10&offset=0'), ('health', '/health'), ('ready', '/ready'),
                )}
                row['passed'] = row['passed'] and all(code == 200 for code in row['smoke'].values())
            finally:
                row['logout_status'] = session.post(base + '/auth/logout',
                    headers={'X-CSRF-Token': session.cookies.get('matgar_csrf', '')}).status_code
                row['passed'] = row['passed'] and row['logout_status'] == 204
    if args.login_guard and all(row['passed'] for row in report['hosts']):
        rows = []
        started = time.monotonic()
        with httpx.Client(timeout=15, trust_env=False) as probe:
            # One identity for the account+IP short retry bucket.
            email = 'reliability-' + uuid.uuid4().hex + '@example.invalid'
            for _ in range(5):
                r = probe.post(HOSTS[1][1] + '/auth/login', json={
                    'email': email, 'password': 'Deliberately-invalid-test-password!',
                    'institution_slug': args.institution,
                })
                rows.append({'status': r.status_code, 'retry_after': r.headers.get('Retry-After')})
        elapsed = time.monotonic() - started
        report['login_guard'] = {'attempts': rows, 'seconds': round(elapsed, 3),
            'passed': elapsed < 10 and [r['status'] for r in rows] == [401] * 4 + [429]
            and int(rows[-1]['retry_after'] or '0') > 0}
    report['passed'] = all(row['passed'] for row in report['hosts']) and (
        not args.login_guard or report.get('login_guard', {}).get('passed') is True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
