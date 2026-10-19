import asyncio,json
import httpx
from stage_common import BASES,credentials,observation,write

async def main():
    rows=[]
    async with httpx.AsyncClient(timeout=15) as c:
        for i in range(22):
            r=await c.head(BASES[i%2]+'/users',headers=credentials(501))
            rows.append({'status':r.status_code,'retry_after':r.headers.get('Retry-After'),'proof':observation(r)})
    policies=[r['proof']['policies'][0] for r in rows]
    result={'rows':rows,'two_distinct_workers':len({r['proof']['worker'] for r in rows})==2,
        'two_distinct_instances':len({r['proof']['instance'] for r in rows})==2,
        'one_shared_key':len({p['key'] for p in policies})==1,
        'boundary_20_total_not_20_each':[r['status'] for r in rows]==[405]*20+[429]*2,
        'redis_only':all(p['backend']=='redis' for p in policies)}
    write('shared-two-instances.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
asyncio.run(main())
