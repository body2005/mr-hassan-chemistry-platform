"""Repeated real HTTPS samples; numbers are not a universal side-channel proof."""
import json
import os
import random
import statistics
import uuid

import docker
from argon2 import PasswordHasher
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from .live_helpers import clear_auth, container, pg_engine, session


def test_existing_wrong_password_and_missing_user_have_same_contract_with_repeated_timings():
    clear_auth()  # Wait out real budgets, including reused Docker client IPs.
    pg = pg_engine()
    engine = docker.from_env()
    targets, addresses = [], []
    try:
        with session() as teacher:
            institution_id = uuid.UUID(teacher.get('https://proxy/api/v1/auth/me', timeout=10).json()['institution_id'])
        accounts = []
        api, proxy = container('api'), container('proxy')
        # The pytest process uses APP_ENV=test and deliberately cheap hashes.
        # Timing fixtures must instead match the actual running API, including
        # its missing-user dummy, or the comparison measures fixture cost only.
        parameters = api.exec_run(['/bin/sh', '/srv/entrypoint-prod.sh', 'python', '-c',
            'import json; from argon2 import extract_parameters; '
            'from app.core.security import password_hasher as h; '
            'from app.services.auth_service import _DUMMY_PASSWORD_HASH; '
            'p=extract_parameters(_DUMMY_PASSWORD_HASH); '
            'keys=("time_cost","memory_cost","parallelism","hash_len","salt_len"); '
            'runtime={k:getattr(h,k) for k in keys}; '
            'assert runtime=={k:getattr(p,k) for k in keys}; '
            'print(json.dumps(runtime))'])
        assert parameters.exit_code == 0, 'Cannot verify actual API and dummy hash costs'
        hash_costs = json.loads(parameters.output.decode().strip())
        assert hash_costs['memory_cost'] >= 65536 and hash_costs['time_cost'] >= 3
        synthetic_hash = PasswordHasher(**hash_costs).hash('Unused-synthetic-timing-2026!')
        with Session(pg) as db:
            for _ in range(30):
                key = uuid.uuid4().hex
                email = key + '@qa.example.com'
                db.add(User(institution_id=institution_id, role=UserRole.STUDENT,
                    username='timing-' + key, email=email, display_name='Synthetic timing QA',
                    password_hash=synthetic_hash))
                accounts.append(email)
            db.commit()
        network = next(iter(api.attrs['NetworkSettings']['Networks']))
        certificate = next(mount['Source'] for mount in proxy.attrs['Mounts']
                           if mount['Destination'] == '/run/secrets/tls_cert')
        for index in range(6):
            inputs = [('existing', email) for email in accounts[index * 5:index * 5 + 5]]
            inputs += [('missing', uuid.uuid4().hex + '@qa.example.com') for _ in range(5)]
            random.Random(index).shuffle(inputs)
            probe = f'inputs={inputs!r}\n' + '''
import json,time,requests,uuid
from pathlib import Path
# Keep all six IPs allocated until the controller has recorded them. Docker
# clears stopped-container addresses; never infer independence after exit.
gate=Path('/tmp/qa-timing-start')
deadline=time.monotonic()+60
while not gate.is_file():
    assert time.monotonic()<deadline, 'Timing controller did not release start gate'
    time.sleep(.05)
samples={'existing':[],'missing':[]}; bodies=[]; request_ids=[]
with requests.Session() as client:
    client.verify='/qa-ca.pem'
    for kind,email in inputs:
        started=time.perf_counter()
        result=client.post('https://proxy/api/v1/auth/login', json={
            'email':email,'password':'Incorrect-synthetic-2026!',
            'institution_slug':'demo'},timeout=15)
        samples[kind].append(round((time.perf_counter()-started)*1000,3))
        assert result.status_code==401, {'status':result.status_code,'retry_after':result.headers.get('Retry-After')}
        assert 'token' not in result.json()
        body=result.json()
        request_id=body.pop('request_id')
        assert str(uuid.UUID(request_id))==request_id
        assert result.headers.get('X-Request-ID')==request_id
        request_ids.append(request_id)
        bodies.append(body)
assert all(body==bodies[0] for body in bodies)
assert len(set(request_ids))==len(inputs)
print(json.dumps(samples),flush=True)
'''
            target = engine.containers.run(os.environ['QA_PROJECT'] + '-qa-tests',
                command=['-c', probe], entrypoint=['python'], network=network,
                volumes={certificate: {'bind': '/qa-ca.pem', 'mode': 'ro'}},
                name='qa-timing-' + uuid.uuid4().hex,
                labels={'qa.synthetic_timing_probe': 'true'}, detach=True)
            targets.append(target)
            target.reload()
            addresses.append(target.attrs['NetworkSettings']['Networks'][network]['IPAddress'])
        assert all(addresses) and len(set(addresses)) == 6
        for target in targets:
            opened = target.exec_run(['python', '-c',
                "from pathlib import Path; Path('/tmp/qa-timing-start').touch()"])
            assert opened.exit_code == 0
        samples = {'existing': [], 'missing': []}
        for target in targets:
            code = target.wait(timeout=120)['StatusCode']
            if code != 0:
                # Probe contains only synthetic data/statuses, never cookies.
                print(target.logs().decode())
            assert code == 0, 'HTTP timing probe failed'
            data = json.loads(target.logs().decode().strip())
            for kind in samples:
                samples[kind].extend(data[kind])
        assert all(len(values) == 30 for values in samples.values())
        rng = random.Random(20261006)
        differences = sorted(statistics.median(rng.choices(samples['existing'], k=30))
                             - statistics.median(rng.choices(samples['missing'], k=30)) for _ in range(2000))
        report = {kind: {'n': len(values), 'median_ms': statistics.median(values),
            'p95_ms': sorted(values)[28], 'raw_ms': values} for kind, values in samples.items()}
        report['median_difference_bootstrap_95_percent_ms'] = [differences[49], differences[1949]]
        report['verified_api_and_fixture_argon2_costs'] = hash_costs
        report['boundary'] = ('six concurrent real client IPs, thirty samples/class; identical401 contract; '
                              'local HTTP+CPU scheduling, not proof of timing indistinguishability in production')
        print(json.dumps(report))
    finally:
        for target in targets:
            target.reload()
            assert target.attrs['Config']['Labels'].get('qa.synthetic_timing_probe') == 'true'
            target.remove(force=True)
        engine.close()
        pg.dispose()
