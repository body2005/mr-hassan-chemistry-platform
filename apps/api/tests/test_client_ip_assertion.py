import hashlib,hmac,time
from types import SimpleNamespace
from pydantic import SecretStr
from starlette.requests import Request
import pytest
from app.core.client_ip import asserted_client_ip,render_client_ip

KEY='isolated-proxy-only-test-key-length-48-characters'
def request(ip='2001:db8::9', stamp=None, method='GET', path='/api/v1/courses', query=b'page=1', signature=None):
    stamp=str(stamp or int(time.time()))
    target=path+('?' + query.decode() if query else '')
    mac=hmac.new(KEY.encode(),f'client-ip-v1\n{stamp}\n{method}\n{target}\n{ip}'.encode(),hashlib.sha256).hexdigest()
    return Request({'type':'http','method':method,'path':path,'raw_path':path.encode(),'query_string':query,
        'client':('203.0.113.2',1),'headers':[(b'x-chemistry-client-ip',ip.encode()),
        (b'x-chemistry-client-time',stamp.encode()),(b'x-chemistry-client-signature',(signature or mac).encode())]})

def test_valid_assertion_ipv6_normalized_and_bound_to_request():
    settings=SimpleNamespace(proxy_assertion_secret=SecretStr(KEY))
    r=request(ip='2001:db8:0:0:0:0:0:9')
    assert asserted_client_ip(r,settings)=='2001:db8::9'
    r.scope['method']='POST'
    assert asserted_client_ip(r,settings) is None
    r=request();r.scope['query_string']=b'page=2'
    assert asserted_client_ip(r,settings) is None

@pytest.mark.parametrize('kwargs',[{'stamp':int(time.time())-61},{'stamp':int(time.time())+60},
    {'ip':'8.8.8.8, 1.1.1.1'},{'signature':'0'*64},{'signature':'a'*1000}])
def test_untrusted_assertions_do_not_supply_identity(kwargs):
    assert asserted_client_ip(request(**kwargs),SimpleNamespace(proxy_assertion_secret=SecretStr(KEY))) is None

def test_render_contract_requires_explicit_mode_runtime_and_loopback(monkeypatch):
    r=request();r.scope['headers']=[(b'cf-connecting-ip',b'198.51.100.42')]
    settings=SimpleNamespace(client_ip_mode='render')
    monkeypatch.setenv('RENDER','true')
    assert render_client_ip(r,settings) is None
    r.scope['client']=('127.0.0.1',2)
    assert render_client_ip(r,settings)=='198.51.100.42'
    monkeypatch.delenv('RENDER')
    assert render_client_ip(r,settings) is None
