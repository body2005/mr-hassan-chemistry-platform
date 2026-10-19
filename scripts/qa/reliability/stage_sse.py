"""SSE-only capacity: deliberately separate from the browsing workload."""
import asyncio
import argparse
import collections
import json
import os
import random
import time

import httpx

from stage_common import BASES, OUT, credentials, identity, observation, write


async def publish(marker):
    if os.getenv('STAGING_PUBLISH_LOCAL')=='true':
        from app.core.config import get_settings
        from app.core.events import event_broker
        if get_settings().app_env!='staging' or '@postgres:5432/staging' not in get_settings().database_url:
            raise RuntimeError('Only an isolated staging broker can be used')
        count=await asyncio.to_thread(event_broker.publish_event,identity('institution'),'calendar_updated',{'staging_probe':marker})
        if count<2:raise RuntimeError('Both API pub/sub listeners must be present')
        return
    proc = await asyncio.create_subprocess_exec(
        'docker', 'compose', '--env-file', str(OUT/'staging.env'),
        '-f', 'infra/staging/compose.yml', 'exec', '-T', 'api-a',
        'python', '/audit/stage_publish.py', marker,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode:
        raise RuntimeError('Staging broadcast probe failed')


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--students',type=int,choices=[5,10,25,50,100,250,500])
    parser.add_argument('--output',default='sse-capacity.json')
    args=parser.parse_args()
    report = {'scope': 'Isolated local staging, SSE only; does not prove browsing or production capacity',
              'transport': 'Docker internal Linux' if os.getenv('STAGING_PUBLISH_LOCAL')=='true' else 'Windows Docker loopback', 'stages': []}
    # Control polls are3s apart; retire idle HTTP/1 connections before the
    # server's5s keepalive timer. Long-lived active SSE streams are unaffected.
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=650,keepalive_expiry=2), timeout=20,trust_env=False) as client:
        for count in ([args.students] if args.students else [5, 10, 25, 50, 100, 250, 500]):
            start = time.monotonic()
            row = {'students': count, 'statuses': [], 'errors': [], 'deliveries': {}, 'control': [], 'stop_reason': None,
                   'max_client_loop_lag_ms': 0}
            report['stages'].append(row)
            seen, active = set(), set()
            delivered = collections.defaultdict(set)
            stop = asyncio.Event()

            async def observe_client_loop():
                while not stop.is_set():
                    before=time.monotonic()
                    await asyncio.sleep(.1)
                    row['max_client_loop_lag_ms']=round(max(row['max_client_loop_lag_ms'],(time.monotonic()-before-.1)*1000),2)

            def independent_control(headers):
                before=time.monotonic()
                try:
                    r=httpx.get(BASES[0]+'/auth/me',headers=headers,timeout=10,trust_env=False)
                    return {'status':r.status_code,'seconds':round(time.monotonic()-before,3),
                            'timings':observation(r).get('timings')}
                except httpx.HTTPError as exc:
                    return {'status':0,'seconds':round(time.monotonic()-before,3),'error_type':type(exc).__name__}

            async def stream(index):
                await asyncio.sleep(index*.03)
                while not stop.is_set():
                    try:
                        async with client.stream('GET', BASES[index%2]+'/realtime/stream', headers=credentials(index),
                                timeout=httpx.Timeout(25, connect=8)) as response:
                            row['statuses'].append(response.status_code)
                            if response.status_code != 200:
                                row['stop_reason'] = 'Unexpected SSE status'; stop.set(); return
                            event = ''
                            async for line in response.aiter_lines():
                                if line == 'event: connected': seen.add(index); active.add(index)
                                if line.startswith('event: '): event = line[7:]
                                if event == 'calendar_updated' and line.startswith('data: '):
                                    marker = json.loads(line[6:]).get('staging_probe')
                                    delivered[str(marker)].add(index)
                    except asyncio.CancelledError:
                        raise
                    except httpx.HTTPError as exc:
                        row['errors'].append(type(exc).__name__)
                        row['stop_reason'] = 'SSE network timeout/error'; stop.set(); return
                    finally:
                        active.discard(index)
                    if not stop.is_set(): await asyncio.sleep(.1+random.random())

            tasks = [asyncio.create_task(stream(i)) for i in range(count)]
            lag_task=asyncio.create_task(observe_client_loop())
            try:
                deadline = time.monotonic()+count*.03+25
                while len(active)<count and not stop.is_set() and time.monotonic()<deadline:
                    await asyncio.sleep(.1)
                if len(active)!=count:
                    row['stop_reason'] = row['stop_reason'] or 'Not all students connected'
                else:
                    await publish('initial')
                    until = time.monotonic()+(145 if count==500 else 5)
                    while time.monotonic()<until and not stop.is_set():
                        t = time.monotonic()
                        separate=asyncio.create_task(asyncio.to_thread(independent_control,credentials(510)))
                        response = await client.get(BASES[0]+'/auth/me', headers=credentials(510))
                        elapsed = time.monotonic()-t
                        row['control'].append({'status': response.status_code, 'seconds': round(elapsed,3),
                                               'timings': observation(response).get('timings'),
                                               'independent':await separate})
                        write(args.output,report)
                        if len(row['control'])%5==0:
                            print(json.dumps({'elapsed':round(time.monotonic()-start,1),'active':len(active),
                                'shared_control_s':round(elapsed,3),'independent_control_s':row['control'][-1]['independent']['seconds'],
                                'client_loop_lag_ms':row['max_client_loop_lag_ms']}),flush=True)
                        if response.status_code!=200 or elapsed>5:
                            row['stop_reason'] = 'Control status or latency failure'; stop.set()
                        await asyncio.sleep(3)
                    if not stop.is_set():
                        await publish('after_recycle' if count==500 else 'final')
                        await asyncio.sleep(3)
            except (httpx.HTTPError, RuntimeError) as exc:
                row['stop_reason'] = type(exc).__name__
            finally:
                row['active_at_finish'] = len(active)
                row['distinct_students'] = len(seen)
                row['deliveries'] = {k: len(v) for k,v in delivered.items()}
                row['seconds'] = round(time.monotonic()-start,2)
                expected = ['initial', 'after_recycle' if count==500 else 'final']
                row['passed'] = not row['stop_reason'] and len(active)==count and all(len(delivered[k])==count for k in expected)
                stop.set()
                lag_task.cancel()
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks,lag_task, return_exceptions=True)
                write(args.output, report)
                print(json.dumps({k:v for k,v in row.items() if k not in {'statuses','control'}}), flush=True)
            if not row['passed']: break
            await asyncio.sleep(5)


if __name__ == '__main__':
    asyncio.run(main())
