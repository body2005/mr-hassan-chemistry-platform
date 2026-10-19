import pathlib,secrets
root=pathlib.Path(__file__).resolve().parents[3]
target=root/'.qa/reliability-staging/staging.env'
target.parent.mkdir(parents=True,exist_ok=True)
if target.exists():raise FileExistsError('Do not rotate a running staging key accidentally')
db=secrets.token_hex(24);s3=secrets.token_hex(24)
env=dict(STAGING_SOURCE_ROOT=root.as_posix(),STAGING_ENV_FILE=target.as_posix(),STAGING_RESULTS_DIR=target.parent.as_posix(),
    STAGING_API_IMAGE='sha256:ed37f2b020b9f1fd208bb61bc2629744cdc0c012720011d92bf3c0bf94e40588',
    STAGING_DB_PASSWORD=db,STAGING_S3_PASSWORD=s3,APP_ENV='staging',SECRET_KEY=secrets.token_hex(32),
    PROXY_ASSERTION_SECRET=secrets.token_hex(32),SSE_INSTITUTION_LIMIT='600',REQUEST_TIMING_LOGS='true',
    DATABASE_URL=f'postgresql+psycopg://staging:{db}@postgres:5432/staging',REDIS_URL='redis://redis:6379/0',
    REDIS_REQUIRED='true',STORAGE_BACKEND='s3',S3_ENDPOINT_URL='http://s3:8333',S3_BUCKET_NAME='staging',
    S3_ACCESS_KEY_ID='staging',S3_SECRET_ACCESS_KEY=s3,S3_REGION='us-east-1',
    FRONTEND_ORIGINS='https://staging.invalid',PUBLIC_FRONTEND_URL='https://staging.invalid',
    PAYMENT_BANK_DETAILS='Isolated synthetic staging only',INGESTION_BACKEND='disabled',EMAIL_ENABLED='false',
    DB_POOL_SIZE='5',DB_MAX_OVERFLOW='5',STORAGE_DIR='/srv/uploads',PYTHONDONTWRITEBYTECODE='1')
target.write_text('\n'.join(k+'='+v for k,v in env.items())+'\n',encoding='utf-8')
print('Staging-only environment generated; no production credentials used')
