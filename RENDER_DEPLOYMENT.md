# Render + Vercel deployment checklist

## Required Render environment values

The updated `render.yaml` provisions PostgreSQL and connects the API through
`DATABASE_URL`. Set these secret values in the Render dashboard before deploy:

- `INITIAL_TEACHER_PASSWORD`: a new strong password; never commit it.
- `SECRET_KEY`: keep the generated Render value stable between deploys.

The initial teacher email is `teacher@hassanshaban.com`. The seed is
idempotent and does not change an existing account or print its password unless
the explicit one-time recovery switch below is enabled.

If the teacher exists but login returns `401 Invalid credentials`:

1. Set `RESET_INITIAL_TEACHER_PASSWORD=true` in the Render dashboard.
2. Confirm `INITIAL_TEACHER_PASSWORD` contains the intended new password.
3. redeploy the API and verify teacher login.
4. Set `RESET_INITIAL_TEACHER_PASSWORD=false` and redeploy again, so later
   application password changes are not overwritten.

After the first deployment, sign in again once. Old tokens that point to the
former ephemeral SQLite database are intentionally rejected and cleared by the
web client.

## Optional isolated demo accounts

The uploaded local SQLite database is not the production PostgreSQL database.
Create or repair the two demo accounts directly in production by setting these
values on the Render web service:

- `ENABLE_DEMO_ACCOUNTS=true`
- `DEMO_INSTITUTION_SLUG=demo`
- `DEMO_TEACHER_EMAIL=teacher@demo.com`
- `DEMO_TEACHER_PASSWORD=<secret value>`
- `DEMO_STUDENT_EMAIL=student@demo.com`
- `DEMO_STUDENT_PASSWORD=<secret value>`
- `RESET_DEMO_PASSWORDS=true`

Deploy once and verify both logins. Then set `RESET_DEMO_PASSWORDS=false` and
deploy again so future password changes are not overwritten. Never commit the
two passwords to Git. A publicly known teacher password grants write access to
the demo tenant and can consume upload and AI quotas.

## File persistence

PostgreSQL makes users, courses, and source metadata persistent. Uploaded book
files are still local files. A free Render web service has ephemeral storage,
so production uploads require one of these before relying on them:

1. Attach a paid Render Persistent Disk and set `STORAGE_DIR` to a directory
   under its mount path; or
2. Move source storage to an S3-compatible object store.

Do not point `STORAGE_DIR` at `/var/data` unless a disk is actually attached.

## Capacity testing

Use `apps/api/tests/load/locustfile.py`. Start read-only at 10 virtual users and
increase in steps. The free Render tier is suitable for functional checks, not
for establishing production capacity: it has limited CPU/RAM and can sleep.

For a real capacity result, test a paid instance with the same size intended
for production and watch Render CPU, RAM, response p95, error rate, and
PostgreSQL connections. Keep uploads disabled until the read-only test is
stable.
