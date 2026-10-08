"""Repeated local reset measurements, not universal enumeration resistance."""
import json
import os
import random
import statistics
import time
import uuid

import docker
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mail_outbox import ResetMailOutbox
from app.models.user import PasswordResetToken
from .live_helpers import container, wait_until
from .test_remaining_security_live import synthetic_account


def test_repeated_reset_contract_and_durable_delivery_with_real_ip_isolation():
    pg, user_id, email, _password = synthetic_account()
    engine = docker.from_env()
    targets, addresses = [], []
    try:
        # Twelve clients * five requests respect the unchanged5/300s policy.
        # Wait out any previous use of Docker IPs; never flush live counters.
        with redis.Redis.from_url(os.environ["REDIS_URL"]) as store:
            remaining = max([store.pttl(key) for key in
                             store.scan_iter("rate-limit:password_reset_request:*")] + [0])
        assert remaining <= 301000
        if remaining > 0:
            time.sleep((remaining + 100) / 1000)
        with Session(pg) as db:
            previous = set(db.scalars(select(ResetMailOutbox.id).join(PasswordResetToken,
                PasswordResetToken.id == ResetMailOutbox.token_id).where(
                    PasswordResetToken.user_id == user_id)))
        api, proxy = container("api"), container("proxy")
        network = next(iter(api.attrs["NetworkSettings"]["Networks"]))
        certificate = next(mount["Source"] for mount in proxy.attrs["Mounts"]
                           if mount["Destination"] == "/run/secrets/tls_cert")
        for index in range(12):
            existing_count = 3 if index < 6 else 2
            inputs = [("existing", email)] * existing_count
            inputs += [("missing", uuid.uuid4().hex + "@qa.example.com")
                       for _ in range(5 - existing_count)]
            random.Random(index).shuffle(inputs)
            probe = f"inputs={inputs!r}\n" + '''
import json,time,requests
from pathlib import Path
deadline=time.monotonic()+90
while not Path('/tmp/qa-reset-timing-start').is_file():
    assert time.monotonic()<deadline, 'Reset timing controller did not release gate'
    time.sleep(.05)
samples={'existing':[],'missing':[]}; bodies=[]
with requests.Session() as client:
    client.verify='/qa-ca.pem'
    for kind,email in inputs:
        started=time.perf_counter()
        result=client.post('https://proxy/api/v1/auth/password-reset/request',
            json={'email':email,'institution_slug':'demo'},timeout=15)
        samples[kind].append(round((time.perf_counter()-started)*1000,3))
        assert result.status_code==200, {'status':result.status_code,
            'retry_after':result.headers.get('Retry-After')}
        assert result.json()=={'message':'If the account exists, reset instructions will be sent securely.'}
        bodies.append(result.json())
assert all(body==bodies[0] for body in bodies)
print(json.dumps(samples),flush=True)
'''
            target = engine.containers.run(os.environ["QA_PROJECT"] + "-qa-tests",
                command=["-c", probe], entrypoint=["python"], network=network,
                volumes={certificate: {"bind": "/qa-ca.pem", "mode": "ro"}},
                name="qa-reset-timing-" + uuid.uuid4().hex,
                labels={"qa.synthetic_reset_timing_probe": "true"}, detach=True,
                mem_limit="128m", nano_cpus=250_000_000, pids_limit=64,
                cap_drop=["ALL"], security_opt=["no-new-privileges:true"])
            targets.append(target)
            target.reload()
            addresses.append(target.attrs["NetworkSettings"]["Networks"][network]["IPAddress"])
        assert all(addresses) and len(set(addresses)) == 12
        for target in targets:
            opened = target.exec_run(["python", "-c",
                "from pathlib import Path; Path('/tmp/qa-reset-timing-start').touch()"])
            assert opened.exit_code == 0
        samples = {"existing": [], "missing": []}
        for target in targets:
            code = target.wait(timeout=120)["StatusCode"]
            output = target.logs().decode().strip()  # Synthetic timings/statuses only.
            assert code == 0, output
            for kind, values in json.loads(output).items():
                samples[kind].extend(values)
        assert all(len(values) == 30 for values in samples.values())
        rng = random.Random(20261007)
        differences = sorted(statistics.median(rng.choices(samples["existing"], k=30))
                             - statistics.median(rng.choices(samples["missing"], k=30))
                             for _ in range(2000))

        def complete():
            with Session(pg) as db:
                jobs = db.scalars(select(ResetMailOutbox).join(PasswordResetToken,
                    PasswordResetToken.id == ResetMailOutbox.token_id).where(
                        PasswordResetToken.user_id == user_id,
                        ResetMailOutbox.id.not_in(previous))).all()
                return len(jobs) == 30 and all(job.completed_at is not None
                    and job.encrypted_token is None for job in jobs)
        wait_until(complete, 90)
        report = {kind: {"n": len(values), "median_ms": statistics.median(values),
                        "p95_ms": sorted(values)[28], "raw_ms": values}
                  for kind, values in samples.items()}
        report["median_difference_bootstrap_95_percent_ms"] = [differences[49], differences[1949]]
        report["durable_jobs_completed_and_ciphertext_erased"] = 30
        report["boundary"] = ("twelve distinct real IPs, five requests/IP, thirty samples/class; "
            "local scheduling and DB cost, not proof of timing indistinguishability in production")
        print(json.dumps(report))
    finally:
        for target in targets:
            target.reload()
            assert target.attrs["Config"]["Labels"].get("qa.synthetic_reset_timing_probe") == "true"
            target.remove(force=True)
        engine.close()
        pg.dispose()
