# Three private preview students

The normal production guard still forbids the legacy demo seed (including its
teacher account) and password-reset flags. The student-only preview is a
separate explicit opt-in and grants no paid access or manager permissions.

After deploying this version, configure the backend environment:

```dotenv
SEED_PREVIEW_STUDENTS=true
INITIAL_INSTITUTION_SLUG=demo
DEMO_STUDENT_PASSWORD=<private password, at least 12 characters, stored only in Render>
ENABLE_DEMO_ACCOUNTS=false
RESET_DEMO_PASSWORDS=false
RESET_INITIAL_TEACHER_PASSWORD=false
```

Use the existing institution slug (the login form currently uses `demo`). Do
not copy the placeholder above as a password. The existing startup command
already runs `python scripts/seed_teacher.py` after migrations.

| Email / username | Grade |
| --- | --- |
| `student01@demo.com` / `student01` | Secondary 1 |
| `student02@demo.com` / `student02` | Secondary 2 |
| `student03@demo.com` / `student03` | Secondary 3 |

All three new accounts use the private `DEMO_STUDENT_PASSWORD`. Passwords are
hashed in the database and are never printed by the script. Existing accounts
and credentials are preserved; a conflicting identity stops the preview seed
instead of changing an account. No emails are sent. No real accounts are
deleted, and no enrollment or payment entitlement is added.

After the successful seed, set `SEED_PREVIEW_STUDENTS=false` and redeploy.
The three accounts remain available. To test credentials locally, the API
test `test_preview_students_are_opt_in_private_and_idempotent_in_production`
creates an isolated institution and verifies actual login for all three grades.
