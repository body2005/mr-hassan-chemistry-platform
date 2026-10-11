"""Three new proxy diagnostics cases, isolated from application/data containers.

Run explicitly in the disposable qa-tests runner with Docker access,
QA_ISOLATED=true and QA_REPOSITORY=/repo (a read-only source mount).
No externally exposed ports, application credentials, or existing-service stops.
"""
import io
import json
import os
from pathlib import Path
import tarfile
import time
import unittest
import uuid

import docker


SERVER = '''
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/closed'):
            self.close_connection = True
            return
        self.send_response(503 if self.path.startswith('/api/unavailable') else 200)
        self.end_headers()
        self.wfile.write(b'fixture')
    def log_message(self, *args):
        pass
ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
'''


class ProxyDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('QA_ISOLATED') != 'true':
            raise RuntimeError('Explicit isolated QA runner required; no implicit skip')
        cls.client = docker.from_env()
        cls.containers = []
        cls.network = None
        cls.addClassCleanup(cls.cleanup)
        cls.prefix = 'qa-proxy-diagnostics-' + uuid.uuid4().hex[:12]
        cls.network = cls.client.networks.create(cls.prefix, internal=True)
        api_image = cls.client.containers.get('chemistryaudit2-api-1').image.id
        web_image = cls.client.containers.get('chemistryaudit2-web-1').image.id
        cls.server = cls.client.containers.create(
            api_image, ['-u', '-c', SERVER], entrypoint='python',
            name=cls.prefix + '-fixture', network=cls.network.name,
            mem_limit='128m', cap_drop=['ALL'], security_opt=['no-new-privileges'],
        )
        cls.containers.append(cls.server)
        cls.network.disconnect(cls.server)
        cls.network.connect(cls.server, aliases=['diagnostic-upstream'])
        cls.server.start()
        source = Path(os.environ['QA_REPOSITORY']) / 'apps/web/nginx.conf'
        config = source.read_text(encoding='utf-8').replace(
            'listen 80;', 'listen 8080;').replace(
            'set $api_upstream api;', 'set $api_upstream diagnostic-upstream;')
        config = 'pid /tmp/nginx.pid;\nevents {}\nhttp {\n' + config + '\n}\n'
        cls.proxy = cls.client.containers.create(
            web_image, ['-c', '/etc/nginx/nginx.conf', '-g', 'daemon off;'],
            entrypoint='nginx', user='101:101', name=cls.prefix + '-proxy',
            network=cls.network.name, mem_limit='128m', cap_drop=['ALL'],
            security_opt=['no-new-privileges'],
            tmpfs={'/tmp': 'rw,size=16m', '/var/cache/nginx': 'rw,size=16m,uid=101,gid=101'},
        )
        cls.containers.append(cls.proxy)
        data = config.encode()
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            info = tarfile.TarInfo('nginx.conf')
            info.size, info.mode = len(data), 0o644
            tar.addfile(info, io.BytesIO(data))
        cls.proxy.put_archive('/etc/nginx', archive.getvalue())
        cls.network.disconnect(cls.proxy)
        cls.network.connect(cls.proxy, aliases=['diagnostic-proxy'])
        cls.proxy.start()
        # Wait for TCP readiness without generating request/log evidence.
        probe = "import socket; socket.create_connection(('diagnostic-proxy',8080),1).close()"
        for attempt in range(30):
            if cls.server.exec_run(['python', '-c', probe]).exit_code == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('Diagnostic proxy did not become ready')

    @classmethod
    def cleanup(cls):
        # Only the exact UUID fixture objects created above. Never app volumes.
        for container in reversed(cls.containers):
            container.remove(force=True, v=False)
        if cls.network is not None:
            cls.network.remove()
        cls.client.close()

    def request_and_log(self, path, status):
        marker = 'PRIVATE_QA_' + uuid.uuid4().hex
        probe = '''
import json, urllib.request, urllib.error
req = urllib.request.Request(%r, headers={'Cookie': %r, 'Authorization': %r})
try:
    response = urllib.request.urlopen(req, timeout=5)
except urllib.error.HTTPError as error:
    response = error
print(json.dumps({'status': response.code}))
''' % ('http://diagnostic-proxy:8080' + path + '?token=' + marker,
       'session=' + marker, 'Bearer ' + marker)
        result = self.server.exec_run(['python', '-c', probe])
        self.assertEqual(result.exit_code, 0, result.output.decode())
        self.assertEqual(json.loads(result.output)['status'], status)
        logs = self.proxy.logs().decode()
        self.assertNotIn(marker, logs)
        line = next(line for line in logs.splitlines() if 'GET ' + path + ' ' in line)
        self.assertIn('upstream=' + str(status), line)
        for field in ('addr=', 'connect=', 'header=', 'response='):
            self.assertIn(field, line)
        return line

    def test_success_has_connect_header_response_without_credentials(self):
        self.assertNotIn('header=-', self.request_and_log('/api/ok', 200))

    def test_upstream_unavailable_preserves_503_not_success(self):
        self.assertNotIn('header=-', self.request_and_log('/api/unavailable', 503))

    def test_closed_upstream_reproduces_502_with_missing_header(self):
        self.assertIn('header=-', self.request_and_log('/api/closed', 502))


if __name__ == '__main__':
    unittest.main(verbosity=2)
