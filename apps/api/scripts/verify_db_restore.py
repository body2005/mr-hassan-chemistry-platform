"""Compare every public table's rows between a quiesced source and NEW restored DB."""
import hashlib
import json
import os
from pathlib import Path
import psycopg
from psycopg import sql

password = Path(os.environ["DB_PASSWORD_FILE"]).read_text().strip()
with psycopg.connect(host="postgres", dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"], password=password) as source, \
        psycopg.connect(host="postgres-restore", dbname="restored", user=os.environ["POSTGRES_USER"], password=password) as destination:
    tables = source.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
    other = destination.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
    assert tables == other, "Restored table names differ"
    rows = 0
    for (table,) in tables:
        query = sql.SQL("SELECT row_to_json(t)::text FROM {} t").format(sql.Identifier("public", table))
        left = sorted(row[0] for row in source.execute(query))
        right = sorted(row[0] for row in destination.execute(query))
        assert left == right, f"Restored rows differ in {table}"
        rows += len(left)
    print(json.dumps({"compared_tables": len(tables), "compared_rows": rows, "mismatches": 0}))
