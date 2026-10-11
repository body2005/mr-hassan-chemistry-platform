"""Two real Docker clients behind the actual HTTPS proxy; no XFF mocks."""
import json
import os
import uuid

import docker

from .live_helpers import clear_auth, container, isolated, wait_until
from .test_remaining_security_live import synthetic_account


def test_two_clients_cannot_spoof_forwarded_headers_to_bypass_login_ip_budget():
    isolated()
    clear_auth()  # Docker may reassign an IP used by the timing probe.
    engine = docker.from_env()
    api, proxy = container('api'), container('proxy')
    networks = list(api.attrs['NetworkSettings']['Networks'])
    assert len(networks) == 1, 'Probe requires the isolated private API network'
    certificate = next(mount['Source'] for mount in proxy.attrs['Mounts']
                       if mount['Destination'] == '/run/secrets/tls_cert')
    image = os.environ['QA_PROJECT'] + '-qa-tests'
    probe = '''
import json, requests, uuid
root='https://proxy/api/v1'
identity=uuid.uuid4().hex
codes=[]; retries=[]; hsts=[]
with requests.Session() as client:
    client.verify='/qa-ca.pem'
    for index in range(14):
        result=client.post(root+'/auth/login', json={
            'email':f'unknown-{identity}-{index}@qa.example.com',
            'password':'Incorrect-QA-Password-2026!', 'institution_slug':'demo'},
            headers={'X-Forwarded-For':f'198.51.100.{index+1}',
                     'X-Forwarded-Proto':'http'}, timeout=15)
        codes.append(result.status_code)
        retries.append(result.headers.get('Retry-After'))
        hsts.append(bool(result.headers.get('Strict-Transport-Security')))
print(json.dumps({'codes':codes,'retry_after':retries,'hsts':hsts}))
'''
    probes, addresses = [], []
    try:
        for _ in range(2):
            target = engine.containers.run(image, command=['-c', probe], entrypoint=['python'],
                network=networks[0], volumes={certificate: {'bind': '/qa-ca.pem', 'mode': 'ro'}},
                name='qa-proxy-probe-' + uuid.uuid4().hex,
                labels={'qa.synthetic_proxy_probe': 'true'}, detach=True)
            probes.append(target)
            target.reload()
            addresses.append(target.attrs['NetworkSettings']['Networks'][networks[0]]['IPAddress'])
        assert addresses[0] and addresses[1] and addresses[0] != addresses[1]
        for target in probes:
            assert target.wait(timeout=90)['StatusCode'] == 0, 'HTTPS probe failed'
            evidence = json.loads(target.logs().decode().strip())
            assert evidence['codes'] == [401] * 12 + [429] * 2, evidence
            assert all(int(value) > 0 for value in evidence['retry_after'][-2:])
            assert all(evidence['hsts']), 'Forged forwarded proto must not downgrade HTTPS headers'
    finally:
        for target in probes:
            # Only these newly created, labelled probes are removed; never
            # Compose services, named volumes, user content or prior containers.
            target.reload()
            assert target.attrs['Config']['Labels'].get('qa.synthetic_proxy_probe') == 'true'
            target.remove(force=True)
        engine.close()


def test_short_login_backoff_is_shared_bounded_and_does_not_lock_a_second_client():
    pg, _user_id, email, password = synthetic_account()
    engine = docker.from_env()
    api, proxy = container('api'), container('proxy')
    network = next(iter(api.attrs['NetworkSettings']['Networks']))
    certificate = next(mount['Source'] for mount in proxy.attrs['Mounts']
                       if mount['Destination'] == '/run/secrets/tls_cert')
    targets = []
    try:
        prefix = "import requests,json,time\nclient=requests.Session(); client.verify='/qa-ca.pem'\n"
        prefix += f"url='https://proxy/api/v1/auth/login'\nemail={email!r}\npassword={password!r}\n"
        first = prefix + '''
codes=[]
for index in range(4):
    response=client.post(url,json={'email':email.upper() if index%2 else email,
        'password':'Synthetic-incorrect-2026!', 'institution_slug':'demo'},timeout=15)
    codes.append(response.status_code)
started=time.perf_counter()
response=client.post(url,json={'email':email,'password':password,'institution_slug':'demo'},timeout=15)
retry=int(response.headers.get('Retry-After','0'))
print(json.dumps({'phase':'blocked','codes':codes,'blocked':response.status_code,
    'retry_after':retry,'blocked_ms':round((time.perf_counter()-started)*1000,3)}),flush=True)
assert codes==[401]*4 and response.status_code==429 and 1<=retry<=10
time.sleep(retry+1)
response=client.post(url,json={'email':email,'password':password,'institution_slug':'demo'},timeout=15)
assert response.status_code==200
csrf=client.cookies.get('matgar_csrf')
assert client.post(url.replace('/login','/logout'),headers={'X-CSRF-Token':csrf},timeout=15).status_code==204
print(json.dumps({'phase':'recovered','status':200}),flush=True)
'''
        def start(code):
            target = engine.containers.run(os.environ['QA_PROJECT'] + '-qa-tests',
                command=['-c', code], entrypoint=['python'], network=network,
                volumes={certificate: {'bind': '/qa-ca.pem', 'mode': 'ro'}},
                name='qa-login-backoff-' + uuid.uuid4().hex,
                labels={'qa.synthetic_backoff_probe': 'true'}, detach=True)
            targets.append(target)
            return target
        origin = start(first)
        wait_until(lambda: b'"phase": "blocked"' in origin.logs(), 30)
        # Correct password from another real IP succeeds during origin cooldown.
        second = start(prefix + '''
response=client.post(url,json={'email':email,'password':password,'institution_slug':'demo'},timeout=15)
assert response.status_code==200
assert client.post(url.replace('/login','/logout'),headers={
    'X-CSRF-Token':client.cookies.get('matgar_csrf')},timeout=15).status_code==204
print(json.dumps({'second_client_status':200}),flush=True)
''')
        origin.reload(); second.reload()
        assert origin.attrs['NetworkSettings']['Networks'][network]['IPAddress'] != second.attrs['NetworkSettings']['Networks'][network]['IPAddress']
        assert second.wait(timeout=30)['StatusCode'] == 0
        assert origin.wait(timeout=40)['StatusCode'] == 0
        evidence = [json.loads(line) for line in origin.logs().decode().splitlines()]
        assert evidence[-1] == {'phase': 'recovered', 'status': 200}
        print(json.dumps({'origin': evidence, 'second_client_status': 200,
                         'counter_reset': False, 'server_sleep': False}))
    finally:
        for target in targets:
            target.reload()
            assert target.attrs['Config']['Labels'].get('qa.synthetic_backoff_probe') == 'true'
            target.remove(force=True)
        engine.close()
        pg.dispose()
