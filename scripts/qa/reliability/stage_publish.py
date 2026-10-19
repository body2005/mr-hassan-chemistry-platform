import uuid,json,sys
from app.core.events import event_broker
tenant=uuid.uuid5(uuid.NAMESPACE_DNS,'chemistry-reliability-staging-institution')
if __import__('os').environ['APP_ENV']!='staging':
    raise RuntimeError('Only an isolated staging broker can be used')
count=event_broker.publish_event(tenant,'calendar_updated',{'staging_probe':sys.argv[1] if len(sys.argv)>1 else 'initial'})
print(json.dumps({'redis_pubsub_api_subscribers':count}))
