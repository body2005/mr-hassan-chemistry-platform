"""Persist the student visibility time of manually scheduled calendar entries."""
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa

revision = "g9d1e3f5a7b9"
down_revision = "g8c0d2e4f6a8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("calendar_events", sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True))
    # Preserve schedules already saved by the manual calendar wizard. Generated
    # content events keep their existing planning visibility rules.
    table = sa.table("calendar_events", sa.column("id", sa.Uuid()), sa.column("description", sa.Text()),
                     sa.column("request_key", sa.String()), sa.column("publish_at", sa.DateTime(timezone=True)))
    db = op.get_bind()
    for row in db.execute(sa.select(table.c.id, table.c.description, table.c.request_key)).all():
        if (row.request_key or '').startswith(('evt_assessment_', 'lesson-release:')):
            continue
        try:
            meta = json.loads(row.description or '{}')
            date, clock = meta['publishStartDate'], meta['publishStartTime']
            clock = clock.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
            match = re.fullmatch(r'(\d{1,2}):(\d{2})\s*(ص|م|am|pm)?', clock, re.I)
            if not match:
                continue
            hour, minute, marker = match.groups()
            hour = int(hour)
            if marker:
                if not 1 <= hour <= 12:
                    continue
                hour = hour % 12 + (12 if marker.lower() in ('م', 'pm') else 0)
            instant = datetime.fromisoformat(f'{date}T{hour:02}:{minute}:00').replace(
                tzinfo=ZoneInfo('Africa/Cairo')).astimezone(timezone.utc)
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        db.execute(table.update().where(table.c.id == row.id).values(publish_at=instant))


def downgrade():
    op.drop_column("calendar_events", "publish_at")
