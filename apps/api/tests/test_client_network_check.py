import hashlib
import hmac
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.main import app

PATH='/api/v1/operations/client-network'


def test_network_check_requires_authentication():
    with TestClient(app) as client:
        response=client.get(PATH,headers={'X-Expected-Client-IP':'198.51.100.42'})
    assert response.status_code==401


def test_network_check_compares_but_never_trusts_or_discloses_expected_ip(monkeypatch):
    key='isolated-network-check-test-key-of-at-least-32-characters'
    monkeypatch.setattr(get_settings(),'proxy_assertion_secret',SecretStr(key))
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace()
    stamp=str(int(time.time()))
    mac=hmac.new(key.encode(),f'client-ip-v1\n{stamp}\nGET\n{PATH}\n198.51.100.42'.encode(),hashlib.sha256).hexdigest()
    headers={'X-Expected-Client-IP':'198.51.100.42','X-Chemistry-Client-IP':'198.51.100.42',
             'X-Chemistry-Client-Time':stamp,'X-Chemistry-Client-Signature':mac}
    try:
        with TestClient(app) as client:
            response=client.get(PATH,headers=headers)
            assert response.status_code==200
            assert response.json()=={'expected_match':True,'signed_proxy_assertion':True,'render_edge_contract':False}
            assert '198.51.100.42' not in response.text and key not in response.text
            assert response.headers['Cache-Control']=='private, no-store'
            # Changing the expectation cannot change the limiter's identity.
            response=client.get(PATH,headers={**headers,'X-Expected-Client-IP':'203.0.113.8'})
            assert response.json()['expected_match'] is False
            assert client.get(PATH,headers={'X-Expected-Client-IP':'bad-ip'}).status_code==400
    finally:
        app.dependency_overrides.pop(get_current_user,None)
