"""Opt-in bounded timings. No query text, parameters, URLs or identities."""
import contextvars
import logging
import os
import time
from contextlib import contextmanager

_current = contextvars.ContextVar('request_timings', default=None)
logger = logging.getLogger('uvicorn.error.performance')


@contextmanager
def measure(name):
    timings = _current.get()
    if timings is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        # Names are fixed instrumentation labels, never supplied by a client.
        timings[name] = timings.get(name, 0.0) + elapsed
        timings[name + '_count'] = timings.get(name + '_count', 0) + 1


def install_sql_timings(engine):
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    @event.listens_for(engine, 'before_cursor_execute')
    def before(conn, cursor, statement, parameters, context, executemany):
        context._timing_started = time.perf_counter() if _current.get() is not None else None

    @event.listens_for(engine, 'after_cursor_execute')
    def after(conn, cursor, statement, parameters, context, executemany):
        timings = _current.get()
        started = getattr(context, '_timing_started', None)
        if timings is not None and started is not None:
            timings['db_sql_ms'] = timings.get('db_sql_ms', 0.0) + (time.perf_counter()-started)*1000
            timings['db_sql_count'] = timings.get('db_sql_count', 0) + 1

    @event.listens_for(Session, 'do_orm_execute', retval=True)
    def orm(execute_state):
        # Includes acquisition, compilation and execution, not hydration after
        # the result is returned. Do not label ORM-minus-SQL as pure pool wait.
        with measure('db_orm_ms'):
            return execute_state.invoke_statement()


class PerformanceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        state = scope.setdefault('state', {})
        enabled = os.getenv('REQUEST_TIMING_LOGS', '').lower() in {'1', 'true'}
        if not enabled and not isinstance(state.get('rate_limit_proof'), dict):
            return await self.app(scope, receive, send)
        timings = {}
        state['request_timings'] = timings
        token = _current.set(timings)
        start = time.perf_counter()
        status = None

        async def timed_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                timings['headers_ms'] = (time.perf_counter()-start)*1000
            await send(message)
        try:
            return await self.app(scope, receive, timed_send)
        finally:
            _current.reset(token)
            if enabled:
                # Use a matched route template, never a concrete URL/query.
                route = getattr(scope.get('route'), 'path', '/unmatched')
                safe = {k: round(v, 2) for k, v in timings.items()}
                logger.info('request_timing method=%s route=%s status=%s total_ms=%.2f timings=%s',
                            scope['method'], route, status, (time.perf_counter()-start)*1000, safe)
