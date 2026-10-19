import base64,hashlib,hmac,json,os,pathlib,time,uuid
from dotenv import dotenv_values
import jwt
OUT=pathlib.Path(os.getenv('RELIABILITY_OUTPUT_DIR') or pathlib.Path(__file__).resolve().parents[3]/'.qa/reliability-staging')
VALUES=dotenv_values(OUT/'staging.env')
if VALUES.get('APP_ENV')!='staging' or '@postgres:5432/staging' not in VALUES.get('DATABASE_URL',''):
    raise RuntimeError('Isolated staging environment required')
BASES=[os.getenv('STAGING_API_A','http://127.0.0.1:18121/api/v1'),os.getenv('STAGING_API_B','http://127.0.0.1:18122/api/v1')]
if BASES not in [
    ['http://127.0.0.1:18121/api/v1','http://127.0.0.1:18122/api/v1'],
    ['http://api-a:8000/api/v1','http://api-b:8000/api/v1']]:
    raise RuntimeError('Only isolated staging targets are permitted')
def identity(label):return uuid.uuid5(uuid.NAMESPACE_DNS,'chemistry-reliability-staging-'+label)
def credentials(number):
    now=int(time.time())
    token=jwt.encode({'sub':str(identity('user-'+str(number))),'institution_id':str(identity('institution')),
        'role':'teacher' if number==511 else 'student','type':'session','aud':'session',
        'iss':'mr-hassan-chemistry-platform','iat':now-30,'exp':now+1800,'jti':uuid.uuid4().hex,
        'family_id':str(identity('family-'+str(number)))},VALUES['SECRET_KEY'],algorithm='HS256')
    return {'Authorization':'Bearer '+token,**proof()}
def proof():
    audit=uuid.uuid4().hex;expiry=str(int(time.time())+600)
    mac=hmac.new(VALUES['SECRET_KEY'].encode(),f'rate-limit-proof-v1:{audit}.{expiry}'.encode(),hashlib.sha256).hexdigest()
    return {'X-RateLimit-Proof':f'{audit}.{expiry}.{mac}'}
def observation(r):
    value=r.headers.get('X-RateLimit-Proof')
    return json.loads(base64.urlsafe_b64decode(value)) if value else {}
def write(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
