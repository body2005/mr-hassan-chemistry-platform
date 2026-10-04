"""Retire ONLY failed-run synthetic byte-boundary lessons via the real API.

Dry run by default; --execute is restricted to allowlisted local QA projects.
Never deletes objects/volumes directly, never touches another Docker project.
"""
import argparse
from sqlalchemy import text
from tests.integration.live_helpers import BASE, clear_auth, isolated, pg_engine, session


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    isolated()
    engine = pg_engine()
    with engine.connect() as db:
        rows = db.execute(text("""
            SELECT DISTINCT l.id, l.module_id FROM lessons l
            JOIN course_modules m ON m.id=l.module_id JOIN courses c ON c.id=m.course_id
            JOIN users u ON u.id=c.teacher_id LEFT JOIN lesson_assets a ON a.lesson_id=l.id
            WHERE u.email='teacher@demo.com' AND c.code LIKE 'QA%'
              AND c.title LIKE 'QA Integration %' AND m.title='QA Unit' AND l.title='QA Lesson'
              AND (a.filename='boundary.zip' OR l.video_asset_key LIKE '%boundary.webm')
        """)).all()
    engine.dispose()
    print({"execute": args.execute, "synthetic_lessons": [str(r.id) for r in rows]})
    if args.execute:
        clear_auth()
        with session() as teacher:
            for row in rows:
                response = teacher.delete(f"{BASE}/modules/{row.module_id}/lessons/{row.id}", timeout=30)
                assert response.status_code == 204, (row.id, response.status_code)
                print({"retired_lesson": str(row.id), "status": response.status_code})


if __name__ == "__main__":
    main()
