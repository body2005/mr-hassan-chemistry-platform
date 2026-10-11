"""Explicit synthetic accounts for a disposable local project, never real users."""
import os
from seed_teacher import seed

if os.environ.get("QA_ISOLATED") != "true":
    raise RuntimeError("Set QA_ISOLATED=true only for the disposable local QA project")
os.environ.update(ENABLE_DEMO_ACCOUNTS="true", DEMO_TEACHER_PASSWORD="qa-teacher-pass",
                  DEMO_STUDENT_PASSWORD="qa-student-pass")
seed()
os.environ.update(INITIAL_TEACHER_EMAIL="teacher2@example.com", INITIAL_TEACHER_USERNAME="teacher2",
                  INITIAL_TEACHER_PASSWORD="qa-teacher2-pass", INITIAL_INSTITUTION_SLUG="demo")
seed()
