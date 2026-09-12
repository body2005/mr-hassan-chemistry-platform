# Virtual-user load test

This Locust scenario creates concurrent **virtual users**. It does not require
real student accounts. By default it sends read-only requests and never uploads
files.

## Install

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Authenticate

Prefer a temporary test account. Set either a bearer token:

```bash
export LOAD_TEST_TOKEN="temporary-test-token"
```

or credentials (Locust logs in once per worker, not once per virtual user):

```bash
export LOAD_TEST_EMAIL="load-test@example.com"
export LOAD_TEST_PASSWORD="temporary-password"
export LOAD_TEST_INSTITUTION="demo"
```

## Run safely against Render

Start with 10 users, then 25, 50, and 100. Stop increasing when failures rise
above 1%, p95 latency exceeds 2 seconds for normal GET requests, or Render CPU,
memory,/database connections approach their limits.

```bash
locust -f tests/load/locustfile.py \
  --host https://mr-hassan-chemistry-platform.onrender.com \
  --headless -u 10 -r 2 -t 5m \
  --html load_test_10_users.html
```

`-u` is the virtual-user count and `-r` is the number started per second.

## Optional upload scenario

Do this only after the read-only test passes. It creates real small source
records and starts indexing, so use a dedicated test course and clean it up
afterward:

```bash
export LOAD_TEST_ENABLE_UPLOADS=1
export LOAD_TEST_COURSE_ID="test-course-uuid"
```

Never start with large 500 MiB files or hundreds of upload users on a free
Render instance. That measures the platform quota and can exhaust bandwidth or
disk before it measures application capacity.
