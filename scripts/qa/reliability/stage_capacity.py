import argparse,asyncio,collections,json,os,random,time
from contextlib import AsyncExitStack
import httpx
from stage_common import BASES,OUT,credentials,observation,write

def pct(values,q):return round(sorted(values)[min(len(values)-1,int((len(values)-1)*q))],3) if values else None

async def main():
    parser=argparse.ArgumentParser(description='Bounded isolated staging browse/SSE workload')
    parser.add_argument('--arrival-per-second',type=float,default=1/.03)
    parser.add_argument('--output',default='capacity-staging.json')
    parser.add_argument('--client-pools',type=int,default=8)
    parser.add_argument('--stages',default='5,10,25,50,100,250,500',
        help='Increasing subset of the standard stages; diagnostic subsets are reported explicitly')
    args=parser.parse_args()
    if not .1<=args.arrival_per_second<=50:parser.error('arrival rate must be between .1 and50 students/second')
    if not 1<=args.client_pools<=16:parser.error('client pools must be between1 and16')
    try:stages=[int(n) for n in args.stages.split(',')]
    except ValueError:parser.error('stages must be comma-separated integers')
    if not stages or stages!=sorted(set(stages)) or not set(stages)<={5,10,25,50,100,250,500}:
        parser.error('stages must be an increasing subset of5,10,25,50,100,250,500')
    ramp=1/args.arrival_per_second
    report={'environment':os.getenv('STAGING_CAPACITY_PROFILE') or 'Isolated local Docker staging; two API containers each1CPU/768MB, shared PostgreSQL and Redis. Not proof of RenderFree capacity.',
        'workload':'Distinct students: bootstrap, courses/calendar every10sec, one SSE/student with bounded reconnect;500stage150sec includes stream recycle and lease renewal.',
        'arrival_per_second':args.arrival_per_second,
        'client_pools':args.client_pools,
        'requested_stages':stages,
        'transport':'Docker internal Linux' if os.getenv('STAGING_PUBLISH_LOCAL')=='true' else 'Windows Docker loopback',
        'stages':[]}
    # A single transport scans every active SSE connection on pool changes.
    # Shard independent virtual browsers while retaining <=900 total slots.
    async with AsyncExitStack() as stack:
        clients=[await stack.enter_async_context(httpx.AsyncClient(timeout=httpx.Timeout(20,connect=8),
            limits=httpx.Limits(max_connections=900//args.client_pools,max_keepalive_connections=900//args.client_pools,keepalive_expiry=2),
            trust_env=False)) for _ in range(args.client_pools)]
        client=clients[0]
        preflight=await client.get(BASES[0]+'/courses?page=1&page_size=100',headers=credentials(0))
        preflight.raise_for_status()
        lessons=[lesson for course in preflight.json()['items'] for module in course['modules'] for lesson in module['lessons']]
        if len(lessons)!=30:raise RuntimeError('Fixture must expose30 real lesson cards, not an empty catalogue')
        if not all(lesson['content'] is None and not lesson['has_video'] for lesson in lessons):
            raise RuntimeError('Paid content must remain locked')
        report['fixture_visible_locked_lessons']=len(lessons)
        for number in stages:
            stage={'target':number,'requests':[],'streams':[],'events':0,'control':[],'stop_reason':None}
            report['stages'].append(stage);stop=asyncio.Event();start=time.monotonic();seen=set()
            def abort(reason):
                if not stop.is_set():stage['stop_reason']=reason;stop.set()
            async def call(index,path,kind):
                t=time.monotonic()
                try:
                    r=await clients[index%len(clients)].get(BASES[index%2]+path,headers=credentials(index))
                    row={'status':r.status_code,'s':round(time.monotonic()-t,3),'kind':kind,'timings':observation(r).get('timings')}
                    if r.status_code!=200:abort(f'{kind} returned {r.status_code}')
                except httpx.HTTPError as e:
                    row={'status':0,'kind':kind,'s':round(time.monotonic()-t,3),'error_type':type(e).__name__};abort(f'{kind} {type(e).__name__}')
                return row
            async def stream(index):
                while not stop.is_set():
                    try:
                        async with clients[index%len(clients)].stream('GET',BASES[index%2]+'/realtime/stream',headers=credentials(index),timeout=httpx.Timeout(40,connect=8)) as r:
                            stage['streams'].append({'status':r.status_code,'student':index})
                            if r.status_code!=200:abort(f'SSE returned {r.status_code}');return
                            async for line in r.aiter_lines():
                                if line=='event: connected':seen.add(index)
                                if line=='event: calendar_updated':stage['events']+=1
                                if stop.is_set():break
                    except asyncio.CancelledError:raise
                    except httpx.HTTPError as e:abort('SSE '+type(e).__name__);return
                    if not stop.is_set():await asyncio.sleep(.1+random.random())
            async def user(index):
                await asyncio.sleep(index*ramp)
                if stop.is_set():return
                stage['requests'].append(await call(index,'/bootstrap','bootstrap'))
                if stop.is_set():return
                live=asyncio.create_task(stream(index))
                try:
                    while not stop.is_set():
                        for path,kind in [('/courses?page=1&page_size=100','courses'),('/calendar?limit=500&offset=0','calendar')]:
                            if stop.is_set():break
                            stage['requests'].append(await call(index,path,kind))
                            recent=[r['s'] for r in stage['requests'][-40:]]
                            if len(recent)>=40 and pct(recent,.95)>3:abort('Recent browse p95 >3seconds')
                        try:await asyncio.wait_for(stop.wait(),timeout=10+random.random())
                        except asyncio.TimeoutError:pass
                finally:
                    live.cancel();await asyncio.gather(live,return_exceptions=True)
            async def monitor():
                while not stop.is_set():
                    row=await call(510,'/auth/me','control');stage['control'].append(row)
                    if row['s']>5:abort('Control >5seconds')
                    try:await asyncio.wait_for(stop.wait(),timeout=3)
                    except asyncio.TimeoutError:pass
            async def broadcast():
                deadline=time.monotonic()+30+number*ramp
                while len(seen)<number and not stop.is_set() and time.monotonic()<deadline:await asyncio.sleep(.2)
                if len(seen)!=number or stop.is_set():return
                if os.getenv('STAGING_PUBLISH_LOCAL')=='true':
                    from stage_sse import publish
                    await publish('initial')
                    return
                proc=await asyncio.create_subprocess_exec('docker','compose','--env-file',str(OUT/'staging.env'),
                    '-f','infra/staging/compose.yml','exec','-T','api-a','python','/audit/stage_publish.py',
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                stdout,stderr=await proc.communicate()
                stage['broadcast_exit']=proc.returncode
                if proc.returncode:abort('Broadcast probe failed')
            tasks=[asyncio.create_task(user(i)) for i in range(number)]
            monitor_task=asyncio.create_task(monitor());broadcast_task=asyncio.create_task(broadcast())
            try:await asyncio.wait_for(stop.wait(),timeout=(150 if number==500 else 15)+number*ramp)
            except asyncio.TimeoutError:pass
            passed=not stop.is_set() and len(seen)==number and stage['events']>=number
            stop.set();outcomes=await asyncio.gather(*tasks,return_exceptions=True)
            for task in [monitor_task,broadcast_task]:task.cancel()
            await asyncio.gather(monitor_task,broadcast_task,return_exceptions=True)
            durations=[r['s'] for r in stage['requests']]
            server_times=[r['timings']['headers_ms']/1000 for r in stage['requests'] if r.get('timings',{}).get('headers_ms') is not None]
            passed=passed and len(durations)>=number*3 and all(r['status']==200 for r in stage['requests'])
            passed=passed and all(not isinstance(result,BaseException) for result in outcomes)
            passed=passed and all(r['status']==200 and r['s']<=5 for r in stage['control'])
            stage['summary']={'students':number,'passed':passed,'seconds':round(time.monotonic()-start,2),
                'requests':len(durations),'statuses':dict(collections.Counter(r['status'] for r in stage['requests'])),
                'p95':pct(durations,.95),'p99':pct(durations,.99),'sse_students':len(seen),'sse_connections':len(stage['streams']),
                'server_headers_p95':pct(server_times,.95),
                'broadcast_events_received':stage['events'],'stop_reason':stage['stop_reason']}
            write(args.output,report);print(json.dumps(stage['summary']),flush=True)
            if not passed:break
            await asyncio.sleep(5)
if __name__=='__main__':asyncio.run(main())
