"""Actual HTTPS SSE connections and producers routed to different API workers."""
import json
import os
import queue
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import redis
from .live_helpers import BASE, clear_auth, operational_logs, session, wait_until


class Stream:
    def __init__(self, client):
        self.response = client.get(BASE + '/realtime/stream', stream=True, timeout=(10, 25))
        assert self.response.status_code == 200, self.response.status_code
        self.events = queue.Queue()
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
        event = self.events.get(timeout=15)
        assert event.get('event') == 'connected', event
        self.sub_id = event['data']['sub_id']

    def read(self):
        event = {}
        try:
            for raw in self.response.iter_lines(chunk_size=1):
                line = raw.decode('utf-8')
                if not line:
                    if event: self.events.put(event)
                    event = {}; continue
                key, _, value = line.partition(':')
                if key == 'data': event[key] = json.loads(value.strip())
                elif key in {'id', 'event'}: event[key] = value.strip()
        except Exception:
            pass

    def close(self):
        # A socket shutdown unblocks the read before Response.close joins it.
        import socket
        try: self.response.raw._fp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except (AttributeError, OSError): pass
        self.response.close(); self.reader.join(timeout=3)


def worker_for(pattern):
    expression = re.compile(pattern + r'.*?worker_pid=(\d+)')
    logs = operational_logs('api', lambda value: expression.search(value.decode('utf-8', errors='replace'))).decode('utf-8', errors='replace')
    match = re.search(pattern + r'.*?worker_pid=(\d+)', logs)
    assert match, 'No operational worker evidence captured'
    return int(match.group(1))


def notify(teacher, recipient, title):
    response = teacher.post(BASE + '/notifications', json={'recipient_id': recipient, 'kind': 'system',
                                  'title': title, 'message': 'Synthetic distributed notification'}, timeout=15)
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_worker_delivery_and_offline_database_recovery():
    clear_auth()
    with session() as teacher, session('student04@demo.com', 'qa-student-pass') as student:
        recipient = student.get(BASE + '/auth/me', timeout=15).json()['id']
        stream = Stream(student)
        try:
            subscriber_worker = worker_for('sub_id=' + stream.sub_id)
            cross_worker = False
            # Serial requests can be repeatedly accepted by the same Uvicorn
            # worker. Independent overlapping HTTPS connections exercise
            # distribution instead of relying on accidental accept fairness.
            import requests
            barrier = threading.Barrier(16)
            titles = ['Distributed QA ' + uuid.uuid4().hex for _ in range(16)]
            def publish(title):
                with requests.Session() as producer:
                    producer.verify = teacher.verify
                    producer.headers.update(teacher.headers)
                    producer.cookies.update(teacher.cookies)
                    barrier.wait(timeout=10)
                    notify(producer, recipient, title)
            with ThreadPoolExecutor(max_workers=16) as producers:
                list(producers.map(publish, titles))
            received = set()
            for _ in titles:
                event = stream.events.get(timeout=15)
                assert event['event'] == 'notification_created' and event['data']['title'] in titles
                assert event['data']['title'] not in received, 'Duplicate realtime event'
                received.add(event['data']['title'])
                publisher_worker = worker_for('event_id=' + event['id'])
                if subscriber_worker != publisher_worker:
                    cross_worker = True
            assert received == set(titles), 'Missing realtime events'
            assert cross_worker, 'Same-process delivery does not prove Redis distribution'
            print(json.dumps({'subscriber_worker': subscriber_worker, 'publisher_worker': publisher_worker,
                              'different_processes': True}))
        finally:
            stream.close()
        offline = notify(teacher, recipient, 'Offline QA ' + uuid.uuid4().hex)
        again = Stream(student)
        try:
            persisted = student.get(BASE + '/notifications', timeout=15)
            assert persisted.status_code == 200
            assert offline['id'] in {item['id'] for item in persisted.json()}
        finally:
            again.close()


def test_distributed_sse_limit_reservation_survives_headers_and_disconnect():
    clear_auth()
    store = redis.Redis.from_url(os.environ['REDIS_URL'])
    with session('student05@demo.com', 'qa-student-pass') as student:
        user = student.get(BASE + '/auth/me', timeout=15).json()
        key = f"sse:user:{user['institution_id']}:{user['id']}"
        streams = []
        try:
            for _ in range(5): streams.append(Stream(student))
            assert store.zcard(key) == 5
            assert store.zcard('admission:client:user:' + user['id']) >= 5
            denied = student.get(BASE + '/realtime/stream', timeout=15)
            assert denied.status_code == 429
            streams.pop().close()
            wait_until(lambda: store.zcard(key) == 4, 20)
            replacement = Stream(student); streams.append(replacement)
            assert store.zcard(key) == 5
        finally:
            for stream in streams: stream.close()
        wait_until(lambda: store.zcard(key) == 0, 25)
        wait_until(lambda: store.zcard('admission:client:user:' + user['id']) == 0, 25)
