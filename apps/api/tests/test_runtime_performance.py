import asyncio,time
from types import SimpleNamespace
from concurrent.futures import Future
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException
import pytest


def test_slow_redis_does_not_block_event_loop(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'enforce_rate_limit',lambda *a,**k:time.sleep(.05))
    async def exercise():
        async def onward(request):return Response()
        r=Request({'type':'http','method':'GET','path':'/api/v1/nonexistent','query_string':b'',
                   'headers':[],'client':('127.0.0.1',1)})
        started=time.perf_counter()
        task=asyncio.create_task(main.security_middleware(r,onward))
        await asyncio.sleep(.005)
        observed=time.perf_counter()-started
        await task
        assert observed<.04, 'Synchronous Redis blocked the event loop'
    asyncio.run(exercise())


def test_slow_healthy_probe_uses_finite_budget_without_queuing(monkeypatch):
    from app.api.routes import health
    result=SimpleNamespace(status='ready')
    class Probe:
        def result(self,timeout):
            assert timeout==5
            return result
        def done(self):return True
    scheduled=[]
    monkeypatch.setattr(health,'get_settings',lambda:SimpleNamespace(app_env='staging',readiness_wait_seconds=5))
    monkeypatch.setattr(health,'_probe_cache',None)
    monkeypatch.setattr(health,'_probe_future',None)
    monkeypatch.setattr(health,'_probe_executor',SimpleNamespace(submit=lambda f:scheduled.append(1) or Probe()))
    assert health.readiness_check()=={'status':'ready'}
    assert health.readiness_check()=={'status':'ready'}
    assert scheduled==[1]


def test_dependency_failure_stays_closed_and_public_details_are_generic(monkeypatch):
    from app.api.routes import health
    future=Future();future.set_exception(HTTPException(503,{'dependencies':{'storage':'unavailable'}}))
    monkeypatch.setattr(health,'get_settings',lambda:SimpleNamespace(app_env='staging',readiness_wait_seconds=5))
    monkeypatch.setattr(health,'_probe_cache',None)
    monkeypatch.setattr(health,'_probe_future',future)
    with pytest.raises(HTTPException) as e:health.readiness_check()
    assert e.value.status_code==503 and e.value.detail=='Service is not ready'
