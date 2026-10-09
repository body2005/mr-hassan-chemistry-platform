"""Verify local demo credentials/roles at handoff, without printing tokens.

Run in qa-tests with the private QA network and the public QA CA mounted:
  QA_ISOLATED=true QA_CA_FILE=/qa-ca/cert.pem python /qa-tools/handoff_smoke.py
Does not reset accounts, alter content, or use another person's login session.
"""
import json
import os
from pathlib import Path

import requests


def main():
    if os.environ.get('QA_ISOLATED') != 'true':
        raise RuntimeError('Explicit disposable QA environment required')
    ca = os.environ['QA_CA_FILE']
    if not Path(ca).is_file():
        raise RuntimeError('Trusted QA CA required; TLS verification cannot be disabled')
    base = 'https://proxy/api/v1'
    results = []
    for role, email, password in (
        ('teacher', 'teacher@demo.com', 'qa-teacher-pass'),
        ('student', 'student01@demo.com', 'qa-student-pass'),
    ):
        with requests.Session() as session:
            session.verify = ca
            session.headers['Origin'] = 'https://localhost:18543'
            login = session.post(base + '/auth/login', json={
                'email': email, 'password': password, 'institution_slug': 'demo',
            }, timeout=15)
            assert login.status_code == 200, (role, 'login', login.status_code)
            identity = session.get(base + '/auth/me', timeout=15)
            assert identity.status_code == 200, (role, 'identity', identity.status_code)
            assert identity.json()['role'] == role, (role, 'wrong role')
            csrf = next((value for key, value in session.cookies.items() if 'csrf' in key), None)
            assert csrf, (role, 'CSRF cookie missing')
            logout = session.post(base + '/auth/logout', headers={'X-CSRF-Token': csrf}, timeout=15)
            assert logout.status_code == 204, (role, 'logout', logout.status_code)
            results.append({'role': role, 'login': 200, 'identity': 200, 'logout': 204})
    print(json.dumps({'purpose': 'local handoff credentials, not full journey rerun',
                      'tls_verified': True, 'results': results}, indent=2))


if __name__ == '__main__':
    main()
