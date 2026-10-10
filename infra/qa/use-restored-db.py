"""QA-only process wrapper: never print the restored database credentials."""
import os
from pathlib import Path
import sys
from urllib.parse import quote

if os.getenv("QA_ISOLATED") != "true" or os.getenv("QA_PROJECT") not in {"chemistryaudit2", "chemistryprodlocal", "chemistryrelease1010"}:
    raise SystemExit("Restored database wrapper requires an allowlisted isolated QA project")
if len(sys.argv) < 2:
    raise SystemExit("A child command is required")
password = Path(os.environ["DB_PASSWORD_FILE"]).read_text().strip()
os.environ["DATABASE_URL"] = "postgresql+psycopg://{}:{}@postgres-restore:5432/restored".format(
    quote(os.environ["POSTGRES_USER"], safe=""), quote(password, safe=""))
os.environ["S3_ENDPOINT_URL"] = "http://s3-restore:8333"
os.execvp(sys.argv[1], sys.argv[1:])
