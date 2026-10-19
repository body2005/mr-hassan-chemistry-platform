import asyncio,uuid
from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock
import pytest
from starlette.requests import Request
from app.api.dependencies import session_is_current
from app.core.config import get_settings
from app.core.security import create_session_token
from app.models.institution import Institution
from app.models.user import User,UserRole
from app.models.platform import RefreshSession,RevokedSession

@pytest.mark.parametrize('change',['none','revoked_jti','revoked_family','inactive','deleted','role','expired_family'])
def test_sse_single_query_revalidation_keeps_all_security_checks(db,change):
    now=datetime.now(timezone.utc)
    inst=Institution(name='Test',slug='sse-test');db.add(inst);db.flush()
    user=User(institution_id=inst.id,username='test',email='test@example.com',display_name='Test',
              role=UserRole.STUDENT,password_hash='unused');db.add(user);db.flush()
    family=uuid.uuid4()
    session=RefreshSession(user_id=user.id,family_id=family,jti=uuid.uuid4().hex,token_hash=uuid.uuid4().hex,
                           expires_at=now+timedelta(hours=1))
    db.add(session);db.commit()
    token=create_session_token(user,family_id=family)
    from app.core.security import decode_session_token
    claims=decode_session_token(token)
    if change=='revoked_jti':db.add(RevokedSession(user_id=user.id,jti=claims['jti'],expires_at=now+timedelta(hours=1)))
    elif change=='revoked_family':session.revoked_at=now
    elif change=='inactive':user.is_active=False
    elif change=='deleted':user.deleted_at=now
    elif change=='role':user.role=UserRole.TEACHER
    elif change=='expired_family':session.expires_at=now-timedelta(seconds=1)
    db.commit()
    r=Request({'type':'http','method':'GET','path':'/api/v1/realtime/stream',
               'headers':[(b'authorization',('Bearer '+token).encode())]})
    from sqlalchemy import event
    statements=[]
    def count(*args):statements.append(1)
    event.listen(db.bind,'before_cursor_execute',count)
    try:
        assert session_is_current(r,db)==(change=='none')
        assert len(statements)==1
    finally:
        event.remove(db.bind,'before_cursor_execute',count)

def test_slow_consumer_is_closed_for_durable_reload_and_process_limit_is_finite(monkeypatch):
    from app.core import events
    async def run():
        broker=events.RealTimeEventBroker()
        monkeypatch.setattr(broker,'start',AsyncMock())
        monkeypatch.setattr(events.ResourceLease,'acquire',AsyncMock(return_value=False))
        monkeypatch.setattr(get_settings(),'sse_queue_size',4)
        monkeypatch.setattr(get_settings(),'sse_process_limit',5)
        tenant=uuid.uuid4()
        first=await broker.register(tenant,uuid.uuid4(),'student')
        for _ in range(5):
            broker._deliver({'institution_id':str(tenant),'payload':{'type':'notification_created','data':{}}})
        assert first.queue.qsize()==1 and await first.queue.get() is None
        for _ in range(4):await broker.register(tenant,uuid.uuid4(),'student')
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:await broker.register(tenant,uuid.uuid4(),'student')
        assert e.value.status_code==503
    asyncio.run(run())


def test_stream_releases_database_before_waiting_for_redis_registration(monkeypatch):
    from app.api.routes import realtime
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    db=MagicMock()
    async def register(**kwargs):
        db.close.assert_called_once()
        raise RuntimeError('Stop after checking acquisition order')
    monkeypatch.setattr(realtime.event_broker,'register',register)
    user=SimpleNamespace(id=uuid.uuid4(),institution_id=uuid.uuid4(),role=UserRole.STUDENT)
    with pytest.raises(RuntimeError):
        asyncio.run(realtime.realtime_event_stream(user,Request({'type':'http','headers':[]}),db))
