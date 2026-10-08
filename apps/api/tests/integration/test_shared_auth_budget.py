"""Real HTTPS/Redis evidence: refresh cannot bypass the shared auth ceiling."""
import json
import os
import time
import uuid

import docker
import redis

from .live_helpers import clear_auth, container


def test_refresh_and_other_auth_mutations_share_original_production_budget():
    clear_auth()  # Wait out real windows; do not delete live counters.
    engine = docker.from_env()
    target = None
    try:
        api, proxy = container("api"), container("proxy")
        parameters = api.exec_run([
            "/bin/sh", "/srv/entrypoint-prod.sh", "python", "-c",
            'import json; from app.core.config import get_settings; '
            's=get_settings(); assert s.deployment_environment; '
            'print(json.dumps({"limit":s.rate_limit_login,"window":s.rate_limit_window_seconds}))',
        ])
        assert parameters.exit_code == 0
        policy = json.loads(parameters.output.decode().strip())
        assert policy == {"limit": 15, "window": 60}, policy
        network = next(iter(api.attrs["NetworkSettings"]["Networks"]))
        certificate = next(mount["Source"] for mount in proxy.attrs["Mounts"]
                           if mount["Destination"] == "/run/secrets/tls_cert")
        probe = '''
import json,time,requests
from pathlib import Path
deadline=time.monotonic()+90
while not Path('/tmp/qa-shared-auth-start').is_file():
    assert time.monotonic()<deadline, 'Shared-budget controller did not release start gate'
    time.sleep(.05)
with requests.Session() as client:
    client.verify='/qa-ca.pem'
    # No forged XFF, cookie, Bearer token or different identity between calls.
    statuses=[]
    for number in range(15):
        path='refresh' if number%2==0 else 'logout'
        response=client.post('https://proxy/api/v1/auth/'+path,timeout=10)
        expected=401 if path=='refresh' else 204
        assert response.status_code==expected, {'number':number,'status':response.status_code}
        statuses.append(response.status_code)
    blocked=client.post('https://proxy/api/v1/auth/refresh',timeout=10)
    assert blocked.status_code==429, {'sixteenth_status':blocked.status_code}
    retry=int(blocked.headers['Retry-After'])
    assert 1<=retry<=60
    other=client.post('https://proxy/api/v1/auth/change-password',json={},timeout=10)
    assert other.status_code==429, {'other_mutation_status':other.status_code}
    read=client.get('https://proxy/api/v1/auth/me',timeout=10)
    assert read.status_code==401, {'anonymous_profile_status':read.status_code}
    # Real expiry, no Redis delete/flush, no production sleep or limit change.
    time.sleep(retry+.25)
    recovered=client.post('https://proxy/api/v1/auth/refresh',timeout=10)
    assert recovered.status_code==401, {'after_expiry_status':recovered.status_code}
print(json.dumps({'limit':15,'window':60,'first_15':statuses,'sixteenth':429,
    'other_mutation':429,'profile_read':401,'retry_after':retry,'after_expiry':401}))
'''
        target = engine.containers.run(
            os.environ["QA_PROJECT"] + "-qa-tests",
            command=["-c", probe], entrypoint=["python"], network=network,
            volumes={certificate: {"bind": "/qa-ca.pem", "mode": "ro"}},
            name="qa-shared-auth-" + uuid.uuid4().hex,
            labels={"qa.synthetic_shared_auth_probe": "true"}, detach=True,
            mem_limit="128m", nano_cpus=500_000_000, pids_limit=64,
            cap_drop=["ALL"], security_opt=["no-new-privileges:true"],
        )
        target.reload()
        address = target.attrs["NetworkSettings"]["Networks"][network]["IPAddress"]
        assert address
        # Docker may reuse a previous probe's IP. Wait for that exact real
        # identity's existing window instead of assuming a newly named
        # container starts with empty counters or deleting its Redis key.
        with redis.Redis.from_url(os.environ["REDIS_URL"]) as store:
            prior_ttl = store.pttl(f"rate-limit:auth:ip:{address}:15:60")
        assert prior_ttl <= 61000
        if prior_ttl > 0:
            time.sleep((prior_ttl + 100) / 1000)
        opened = target.exec_run(["python", "-c",
            "from pathlib import Path; Path('/tmp/qa-shared-auth-start').touch()"])
        assert opened.exit_code == 0
        code = target.wait(timeout=100)["StatusCode"]
        output = target.logs().decode().strip()  # Synthetic statuses only.
        assert code == 0, output
        report = json.loads(output)
        assert report["sixteenth"] == 429 and report["after_expiry"] == 401
        print(json.dumps(report))
    finally:
        if target is not None:
            target.reload()
            assert target.attrs["Config"]["Labels"].get("qa.synthetic_shared_auth_probe") == "true"
            target.remove(force=True)
        engine.close()
