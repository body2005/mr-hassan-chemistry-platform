"""Read-only identity checks plus a disposable staging file; no secrets logged."""
import os
from pathlib import Path
import tempfile


def main():
    assert os.getuid() == os.geteuid() == 10001, 'Runtime must not be root'
    assert os.getgid() == 10001, 'Runtime group must be restricted'
    assert not os.access('/srv/app/main.py', os.W_OK), 'Application source must be read-only'
    assert not os.access('/srv/app', os.W_OK), 'Application directory must be read-only'
    assert os.environ.get('STORAGE_DIR') == '/srv/uploads', 'Staging must use the dedicated writable directory'
    status = Path('/proc/self/status').read_text()
    assert 'NoNewPrivs:\t1' in status, 'Privilege escalation must be disabled'
    cap = next(line for line in status.splitlines() if line.startswith('CapEff:')).split()[1]
    assert int(cap, 16) == 0, 'Runtime must not retain effective capabilities'
    for name in ('DB_PASSWORD_FILE', 'SECRET_KEY_FILE', 'S3_SECRET_KEY_FILE', 'SMTP_PASSWORD_FILE'):
        path = Path(os.environ[name])
        with path.open('rb') as secret:
            assert secret.read(1), 'Mounted secret must be readable'
        assert not os.access(path, os.W_OK), 'Mounted secret must not be writable'
    with tempfile.TemporaryFile(dir='/srv/uploads', prefix='qa-permissions-') as probe:
        probe.write(b'synthetic runtime permission probe'); probe.flush()
    print('uid=10001 gid=10001 cap_eff=0 no_new_privs=1 source=read-only secrets=read-only staging=writable')


if __name__ == '__main__':
    main()
